"""CLI chat — mirrors the /agents/chat endpoint behaviour exactly."""
from __future__ import annotations

import getpass
import json
import os
import re
import sys
import threading

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _project_root)

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from server.web.agents.orchestrator import build_orchestrator, conversation_history
from server.web.agents.resume.resume_tools import set_current_user
from server.web.agents.eval.evaluator_agent import EvaluationInput, run_evaluator_agent
from server.web.core.logging import set_session_user
from server.db.postgres import get_connection, insert_evaluation

load_dotenv()


# ── Auth ───────────────────────────────────────────────────────────────────────

def _authenticate(email: str, password: str) -> int | None:
    """Verify credentials; return user_id or None."""
    from server.web.core.security import verify_password

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
        if not row:
            return None
        user_id, hashed = row
        if not hashed or not verify_password(password, hashed):
            return None
        return user_id
    finally:
        conn.close()


# ── Evaluator ──────────────────────────────────────────────────────────────────

def _fire_evaluation(
    user_message: str,
    reply_text: str,
    agents_used: list[str],
    raw_output: str,
    agent_outputs: dict = None,
) -> None:
    """Run the evaluator and persist the result in a background thread."""
    def _run():
        try:
            result = run_evaluator_agent(EvaluationInput(
                user_message=user_message,
                final_response=reply_text,
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
                    agent_response=reply_text,
                    score=result.score,
                    passed=result.passed,
                    dimensions=result.dimensions,
                    critique=result.critique,
                    suggested_response=result.suggested_response,
                )
            finally:
                conn.close()
        except Exception as exc:
            print(f"  [evaluator error: {exc}]")

    threading.Thread(target=_run, daemon=True).start()


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _parse_response(raw_content) -> tuple[str, list[str]]:
    """Parse orchestrator JSON output into (message_text, job_ids).

    Handles:
    - Anthropic list content blocks: [{"type": "text", "text": "..."}]
    - Markdown code fences: ```json ... ```
    - JSON embedded inside surrounding prose
    """
    # Normalise list content blocks to a plain string
    if isinstance(raw_content, list):
        parts = [
            b["text"] for b in raw_content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        raw_content = "".join(parts)

    if not isinstance(raw_content, str):
        return str(raw_content), []

    raw = raw_content.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    # Try parsing the whole string, then fall back to finding embedded {...}
    def _try_parse(s: str) -> tuple[str, list[str]] | None:
        try:
            parsed = json.loads(s)
            message = parsed.get("message", raw_content)
            ids = parsed.get("job_ids", [])
            return message, ids if isinstance(ids, list) else []
        except (json.JSONDecodeError, AttributeError):
            return None

    result = _try_parse(raw)
    if result:
        return result

    # Model added prose before/after the JSON — find the outermost {...}
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        result = _try_parse(match.group())
        if result:
            return result

    return raw_content, []


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    orchestrator = build_orchestrator()

    print("\nVector Career Assistant\n" + "─" * 40)

    # ── Login ──────────────────────────────────────────────────────────────
    user_id: int | None = None
    while True:
        email = input("Email: ").strip()
        if not email:
            print("Running without a user session — resume tools will be unavailable.\n")
            break
        password = getpass.getpass("Password: ")
        user_id = _authenticate(email, password)
        if user_id is None:
            print("Invalid email or password. Try again.\n")
        else:
            set_current_user(user_id)
            set_session_user(user_id)
            print(f"Signed in as {email}.\n")
            break

    print('Type your question, or use:  /upload <path/to/resume.pdf>  |  exit\n')

    lc_history: list = []

    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped.lower() == "exit":
            break

        # ── /upload shortcut ───────────────────────────────────────────────
        if stripped.lower().startswith("/upload "):
            if not user_id:
                print("Error: not signed in. Resume tools require an account.\n")
                continue
            path = stripped[len("/upload "):]
            from server.web.agents.resume.resume_tools import upload_resume
            result = upload_resume.invoke({"path": path})
            print(result.get("message") or result.get("error"), "\n")
            continue

        lc_history.append(HumanMessage(content=stripped))

        # ── Stream the orchestrator (identical to router logic) ────────────
        agents_used: list[str] = []
        agent_outputs: dict = {}
        final_content = ""

        token = conversation_history.set(lc_history[:-1])
        try:
            for chunk in orchestrator.stream({"messages": lc_history}, stream_mode="updates"):
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
                        for tc in msg.tool_calls:
                            name = tc.get("name")
                            if name and name not in agents_used:
                                agents_used.append(name)
                    elif msg.content:
                        final_content = msg.content
        finally:
            conversation_history.reset(token)

        # ── Parse JSON output ──────────────────────────────────────────────
        message, job_ids = _parse_response(final_content)

        # Store clean text in history (not raw JSON)
        lc_history.append(AIMessage(content=message))

        # ── Print reply ────────────────────────────────────────────────────
        print(f"\nAssistant: {message}")
        for jid in job_ids:
            print(f"  {jid}")
        print()

        # ── Fire evaluator in background ───────────────────────────────────
        if final_content:
            raw_output = json.dumps({"message": message, "job_ids": job_ids})
            _fire_evaluation(stripped, message, agents_used, raw_output, agent_outputs)


if __name__ == "__main__":
    main()
