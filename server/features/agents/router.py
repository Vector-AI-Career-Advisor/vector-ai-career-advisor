from __future__ import annotations
import asyncio
import json
import logging
import re
import threading
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from server.core.security import get_current_user
from server.core.logging import set_session_user, clear_session_user
from server.agents.orchestrator import build_orchestrator, conversation_history
from server.agents.resume.resume_tools import (
    _fallback_cover_letter,
    _looks_like_refusal,
    generate_cover_letter_for_job,
    set_current_user,
)
from server.agents.eval.evaluator_agent import run_evaluator_agent, EvaluationInput
from server.db.postgres import get_connection, insert_evaluation

# Use the "agents" namespace so this module's logs flow into the session log file.
log = logging.getLogger("agents.router")

router = APIRouter()


# ── Cover-letter refusal recovery ───────────────────────────────────────────
# The coordinator LLM is instructed never to refuse or second-guess a cover
# letter request, but that instruction is a soft constraint. If it ignores it
# and writes its own refusal/critique instead of relaying the tool's output,
# we detect that shape and rebuild the reply straight from the tool result,
# which resume_tools.py has already generated safely.

_REFUSAL_MARKERS = (
    "cannot write this cover letter",
    "can't write this cover letter",
    "in good conscience",
    "misrepresent the candidate",
    "the candidate should pursue",
    "not aligned with their actual expertise",
    "does not support the required qualifications",
    "the resume lacks evidence",
    "the resume demonstrates",
    "to apply for this role authentically",
)


def _looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def _recover_cover_letter_reply(agent_outputs: dict) -> Optional[str]:
    """If the coordinator's reply looks like a refusal, rebuild it from the
    generate_cover_letter tool's own (already-safeguarded) output instead."""
    raw = agent_outputs.get("generate_cover_letter")
    if not raw:
        return None
    try:
        tool_result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw if not _looks_like_refusal(raw) else None
    if not isinstance(tool_result, dict) or "cover_letter" not in tool_result:
        return None

    return tool_result["cover_letter"]


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


class CoverLetterRequest(BaseModel):
    job_id: str


# ── Endpoint ───────────────────────────────────────────────────────────────

@router.post("/cover-letter")
def cover_letter(req: CoverLetterRequest, user_id: str = Depends(get_current_user)):
    result = generate_cover_letter_for_job(int(user_id), req.job_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if _looks_like_refusal(result.get("cover_letter", "")):
        result["cover_letter"] = _fallback_cover_letter(
            "", result.get("job_title", ""), result.get("company", "")
        )
    return result


@router.post("/chat")
async def chat(req: ChatRequest, user_id: str = Depends(get_current_user)):
    set_current_user(int(user_id))

    if req.job_id and re.search(r"cover[\s_-]*l(?:e|a)tter(?:s)?", req.message, re.IGNORECASE):
        async def generate_cover_letter_chat():
            yield f"data: {json.dumps({'type': 'planning', 'agents': [{'name': 'resume_agent', 'description': 'Drafting a cover letter for the selected job'}]})}\n\n"
            result = await asyncio.to_thread(
                generate_cover_letter_for_job, int(user_id), req.job_id
            )
            if "error" in result:
                yield f"data: {json.dumps({'type': 'error', 'detail': result['error']})}\n\n"
                return

            reply = result["cover_letter"]
            if _looks_like_refusal(reply):
                reply = _fallback_cover_letter(
                    "", result.get("job_title", ""), result.get("company", "")
                )
            yield f"data: {json.dumps({'type': 'reply', 'reply': reply, 'job_ids': [], 'agents_used': [{'name': 'resume_agent', 'description': 'Drafting a cover letter for the selected job'}]})}\n\n"

        return StreamingResponse(generate_cover_letter_chat(), media_type="text/event-stream")

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

                # Safety net: if the coordinator refused/critiqued instead of
                # relaying the cover letter it was given, rebuild the reply
                # from the tool's own output.
                if reply_text and _looks_like_refusal(reply_text):
                    recovered = _recover_cover_letter_reply(agent_outputs)
                    if recovered is None and req.job_id:
                        direct_result = generate_cover_letter_for_job(int(user_id), req.job_id)
                        if "cover_letter" in direct_result:
                            recovered = direct_result["cover_letter"]
                    if recovered is not None:
                        log.warning(
                            "Coordinator produced a refusal-shaped reply for user %s; "
                            "recovered cover letter from tool output.", user_id,
                        )
                        reply_text = recovered

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
                clear_session_user()
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        threading.Thread(target=run_agent, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generate(), media_type="text/event-stream")