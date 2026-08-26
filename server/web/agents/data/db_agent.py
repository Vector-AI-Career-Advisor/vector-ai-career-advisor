"""SQL Agent — handles all structured DB queries and job searches."""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from server.web.agents.data.db_tools import DB_TOOLS
from server.web.agents.data.prompt import PROMPT
from server.db.postgres import get_job_count_cached

load_dotenv()

log = logging.getLogger("agents.db_agent")

class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_db_agent():
    base = ChatAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ANTHROPIC_MODEL"),
        max_tokens=400,
    )
    llm_force = base.bind_tools(DB_TOOLS, tool_choice="any")
    llm_auto  = base.bind_tools(DB_TOOLS)

    def assistant(state: State):
        has_results = any(isinstance(m, ToolMessage) for m in state["messages"])
        llm = llm_auto if has_results else llm_force
        prompt = PROMPT.format(
            today=date.today().strftime("%B %d, %Y"),
            job_count=get_job_count_cached(),
        )
        messages = [SystemMessage(content=prompt)] + state["messages"]
        return {"messages": [llm.invoke(messages)]}

    def route(state: State):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            for call in last.tool_calls:
                log.info("[TOOL] %s | args=%s", call["name"], call["args"])
            return "tools"
        return END

    graph = StateGraph(State)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(DB_TOOLS))
    graph.set_entry_point("assistant")
    graph.add_conditional_edges("assistant", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")

    return graph.compile()


# Singleton — built once and reused by the orchestrator tool wrapper.
_db_agent = None


def get_db_agent():
    global _db_agent
    if _db_agent is None:
        _db_agent = build_db_agent()
    return _db_agent


def run_db_agent(query: str, history: list | None = None) -> str:
    """Entry point called by the orchestrator tool wrapper."""
    agent = get_db_agent()
    messages = list(history) if history else []
    messages.append(HumanMessage(content=query))
    result = agent.invoke({"messages": messages})
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)
