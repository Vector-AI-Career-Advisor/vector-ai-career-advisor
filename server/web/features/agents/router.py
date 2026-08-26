from __future__ import annotations
import asyncio
import json
import logging
import re
import threading
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from server.web.core.security import get_current_user
from server.web.core.logging import set_session_user, clear_session_user
from server.web.agents.orchestrator import build_orchestrator, conversation_history
from server.web.agents.resume.resume_tools import set_current_user
from server.web.agents.tools.mcp_client import set_current_user as set_mcp_user, reset_current_user as reset_mcp_user
from server.web.agents.eval.evaluator_agent import run_evaluator_agent, EvaluationInput
from server.db.postgres import get_connection, insert_evaluation

# Use the "agents" namespace so this module's logs flow into the session log file.
log = logging.getLogger("agents.router")

router = APIRouter()


# ── Evaluation ────────────────────────────────────────────────────────────

def _fire_orchestrator_evaluation(user_message: str, final_reply: str, agents_used: List[str], raw_output: str = "", agent_outputs: dict = None) -> None:
    """Evaluate the orchestrator's full response in a background thread.
    ContextVar is copied at thread start so the session log is inherited."""
    def _run():
        try:
            result = run_evaluator_agent(EvaluationInput(
                user_message=user_message,
                final_response=final_reply,
                agents_used=agents_used,
                raw_output=raw_output,
                agent_outputs=agent_outputs or {},
            ))
            conn = get_connection()
            try:
                insert_evaluation(
                    conn,
                    agent_type="orchestrator",
                    user_message=user_message,
                    agent_response=final_reply,
                    score=result.score,
                    passed=result.passed,
                    dimensions=result.dimensions,
                    critique=result.critique,
                    suggested_response=result.suggested_response,
                )
            finally:
                conn.close()
        except Exception:
            log.exception("[EVALUATOR] Orchestrator evaluation failed")

    threading.Thread(target=_run, daemon=True).start()


# ── Orchestrator singleton ─────────────────────────────────────────────────

_orchestrator = None

def _get_agent():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_orchestrator()
    return _orchestrator


# ── Schemas ────────────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    role: str   # "user" | "agents"
    text: str

class ChatRequest(BaseModel):
    message: str
    history: List[HistoryItem] = []
    job_id: Optional[str] = None


# ── Endpoint ───────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(req: ChatRequest, user_id: str = Depends(get_current_user)):
    set_current_user(int(user_id))
    agent = _get_agent()

    lc_history: list = []
    for item in req.history:
        if item.role == "user":
            lc_history.append(HumanMessage(content=item.text))
        elif item.role == "agents":
            lc_history.append(AIMessage(content=item.text))

    message = req.message
    if req.job_id:
        message = f"[The user currently has job ID '{req.job_id}' open.]\n{message}"
    lc_history.append(HumanMessage(content=message))

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def run_agent():
            """
            Runs the entire agent.stream() in one dedicated thread.
            conversation_history.set() and .reset() both happen here,
            so the token is always in the same Context — no ValueError.
            Results are pushed to the asyncio queue via call_soon_threadsafe.
            """
            set_session_user(int(user_id))
            mcp_token = set_mcp_user(int(user_id))
            agents_used: List[str] = []
            agent_steps: List[dict] = []   # [{name, description}, ...] for the UI
            agent_outputs: dict = {}        # {agent_name: raw_output} for evaluator
            final_reply = ""
            try:
                token = conversation_history.set(lc_history[:-1])
            except Exception:
                log.exception("Failed to initialise conversation context for user %s", user_id)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    f"data: {json.dumps({'type': 'error', 'detail': 'Agent failed to process the request'})}\n\n",
                )
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return
            try:
                for chunk in agent.stream({"messages": lc_history}, stream_mode="updates"):
                    if "tools" in chunk:
                        for msg in chunk["tools"].get("messages", []):
                            if isinstance(msg, ToolMessage) and msg.name:
                                agent_outputs[msg.name] = str(msg.content)
                    if "coordinator" not in chunk:
                        continue
                    for msg in chunk["coordinator"].get("messages", []):
                        if not isinstance(msg, AIMessage):
                            continue
                        if getattr(msg, "tool_calls", None):
                            new_steps = [
                                {
                                    "name": tc["name"],
                                    "description": tc.get("args", {}).get("query", ""),
                                }
                                for tc in msg.tool_calls
                                if tc.get("name") and tc["name"] not in agents_used
                            ]
                            if new_steps:
                                agents_used.extend(s["name"] for s in new_steps)
                                agent_steps.extend(new_steps)
                                loop.call_soon_threadsafe(
                                    queue.put_nowait,
                                    f"data: {json.dumps({'type': 'planning', 'agents': agent_steps})}\n\n",
                                )
                        elif msg.content:
                            final_reply = msg.content

                # Parse structured JSON response from orchestrator.
                # Strip markdown code fences the model sometimes adds.
                reply_text = final_reply
                reply_job_ids: list = []
                if final_reply:
                    def _try_parse(s: str):
                        try:
                            parsed = json.loads(s)
                            return parsed.get("message", final_reply), parsed.get("job_ids", [])
                        except (json.JSONDecodeError, AttributeError):
                            return None

                    raw = final_reply.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[-1]
                        raw = raw.rsplit("```", 1)[0].strip()

                    result = _try_parse(raw)
                    if result is None:
                        match = re.search(r'\{.*\}', raw, re.DOTALL)
                        if match:
                            result = _try_parse(match.group())

                    if result is not None:
                        reply_text, ids = result
                        reply_job_ids = ids if isinstance(ids, list) else []

                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    f"data: {json.dumps({'type': 'reply', 'reply': reply_text, 'job_ids': reply_job_ids, 'agents_used': agent_steps})}\n\n",
                )
                if reply_text:
                    raw_output = json.dumps({"message": reply_text, "job_ids": reply_job_ids})
                    _fire_orchestrator_evaluation(req.message, reply_text, agents_used, raw_output, agent_outputs)
            except Exception:
                log.exception("Agent streaming failed for user %s", user_id)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    f"data: {json.dumps({'type': 'error', 'detail': 'Agent failed to process the request'})}\n\n",
                )
            finally:
                conversation_history.reset(token)
                reset_mcp_user(mcp_token)
                clear_session_user()
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        threading.Thread(target=run_agent, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generate(), media_type="text/event-stream")
