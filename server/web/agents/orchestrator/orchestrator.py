"""Orchestrator Agent — classifies intent and delegates to specialist agents via tool wrappers."""
from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar
from datetime import date
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from server.web.agents.data.db_agent import run_db_agent
from server.web.agents.resume.resume_agent import run_resume_agent
from server.web.agents.advisor.job_advisor_agent import run_job_advisor_agent
from server.web.agents.interview.interview_agent import run_interview_agent
from .prompt import PROMPT

load_dotenv()
sys.dont_write_bytecode = True

log = logging.getLogger("agents.orchestrator")

# Stores the conversation history for the current request so tool wrappers
# and the evaluator can access it without threading it through every call.
# Set by router.py before each agent.invoke(); reset in a finally block.
conversation_history: ContextVar[list] = ContextVar("conversation_history", default=[])


# ── Tool wrappers around each specialist agent ────────────────────────────

@tool
def db_agent(query: str) -> str:
    """Delegate to the SQL Agent for any job database queries.
    Use for: job searches, statistics, skill trends, company rankings, listings.
    Do NOT use for course or learning recommendations.
    Pass the user's full request as `query`.
    """
    log.info("[AGENT] dispatching → db_agent | query=%r", query)
    history = conversation_history.get([])
    return run_db_agent(query, history=history)


@tool
def resume_agent(query: str) -> str:
    """Delegate to the Resume Agent for resume-related tasks.
    Use for: tailoring a resume, generating a cover letter, uploading a resume, gap analysis.
    Pass the user's full request (including any job IDs) as `query`.
    """
    log.info("[AGENT] dispatching → resume_agent | query=%r", query)
    history = conversation_history.get([])
    return run_resume_agent(query, history=history)


@tool
def job_advisor_agent(query: str) -> str:
    """Delegate to the Job Advisor Agent for career coaching and upskilling advice.
    Use for: interview prep advice, salary negotiation, role fit, application strategy,
    and ANY requests for course recommendations, tutorials, study plans, or learning paths.
    Pass the user's full request verbatim as `query`.
    """
    log.info("[AGENT] dispatching → job_advisor_agent | query=%r", query)
    history = conversation_history.get([])
    return run_job_advisor_agent(query, history=history)


@tool
def interview_agent(query: str) -> str:
    """Delegate to the Interview Agent for real past interview questions and practice generation.
    Use for: finding what questions are asked at a company, generating practice questions,
    or building an interview prep guide for a specific company and role.
    Always include the fully resolved company name and role in the query — never pronouns.
    Pass the user's full request verbatim as `query`.
    """
    history = conversation_history.get([])
    return run_interview_agent(query, history=history)


ORCHESTRATOR_TOOLS = [db_agent, resume_agent, job_advisor_agent, interview_agent]


# ── Orchestrator graph ────────────────────────────────────────────────────

class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_orchestrator():
    llm = ChatAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ORCHESTRATOR_MODEL"),
    ).bind_tools(ORCHESTRATOR_TOOLS)

    def coordinator(state: State):
        prompt = PROMPT.format(today=date.today().strftime("%B %d, %Y"))
        messages = [SystemMessage(content=prompt)] + state["messages"]
        try:
            response = llm.invoke(messages)
            return {"messages": [response]}
        except Exception as e:
            log.error("LLM invocation error: %s", e)
            raise

    def route(state: State):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(State)
    graph.add_node("coordinator", coordinator)
    graph.add_node("tools", ToolNode(ORCHESTRATOR_TOOLS))
    graph.set_entry_point("coordinator")
    graph.add_conditional_edges("coordinator", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "coordinator")

    return graph.compile()