"""Evaluator Agent — judges the orchestrator's final response and routing decisions."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict

from server.web.agents.eval.prompt import PROMPT

load_dotenv()


# ── Domain types ──────────────────────────────────────────────────────────────

@dataclass
class EvaluationInput:
    user_message: str           # the user's original request
    final_response: str         # extracted message text (for logging/storage)
    agents_used: list[str]      # routing path, e.g. ["db_agent", "job_advisor_agent"]
    raw_output: str = ""        # full JSON string {"message": "...", "job_ids": [...]}
    agent_outputs: dict = None  # {agent_name: raw_output_string} for each specialist called


@dataclass
class EvaluationResult:
    score: int              # 0–100
    passed: bool            # score >= 70
    dimensions: dict        # {routing, completeness, accuracy, synthesis, tone} → {score, reason}
    critique: str           # what the orchestrator did wrong or could improve
    suggested_response: str # better version, or "N/A"
    latency_ms: int | None = None


# ── Graph ─────────────────────────────────────────────────────────────────────

class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_evaluator_agent():
    llm = ChatAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("EVALUATION_MODEL"),
        temperature=0,
    )

    def evaluator(state: State):
        prompt = PROMPT.format(today=date.today().strftime("%B %d, %Y"))
        messages = [SystemMessage(content=prompt)] + state["messages"]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(State)
    graph.add_node("evaluator", evaluator)
    graph.set_entry_point("evaluator")
    graph.add_edge("evaluator", END)

    return graph.compile()


_evaluator_agent = None


def get_evaluator_agent():
    global _evaluator_agent
    if _evaluator_agent is None:
        _evaluator_agent = build_evaluator_agent()
    return _evaluator_agent


def run_evaluator_agent(evaluation_input: EvaluationInput) -> EvaluationResult:
    """Evaluate the orchestrator's response and return a structured EvaluationResult."""
    routing_path = " → ".join(evaluation_input.agents_used) if evaluation_input.agents_used else "none"
    orchestrator_output = evaluation_input.raw_output or evaluation_input.final_response
    agent_outputs = evaluation_input.agent_outputs or {}

    agent_outputs_section = ""
    if agent_outputs:
        lines = []
        for name, output in agent_outputs.items():
            lines.append(f"  [{name}]:\n  {output}")
        agent_outputs_section = "\nSpecialist agent outputs:\n" + "\n".join(lines) + "\n"

    query = (
        f"User request: {evaluation_input.user_message}\n"
        f"Agents invoked: {routing_path}\n"
        f"{agent_outputs_section}"
        f"Orchestrator JSON output: {orchestrator_output}\n"
    )

    agent = get_evaluator_agent()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    raw = result["messages"][-1].content.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    return EvaluationResult(
        score=data["score"],
        passed=data["passed"],
        dimensions=data["dimensions"],
        critique=data["critique"],
        suggested_response=data.get("suggested_response", ""),
    )