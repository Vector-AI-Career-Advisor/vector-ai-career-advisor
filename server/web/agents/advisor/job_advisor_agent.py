"""Job Advisor Agent — conversational career coaching and course recommendations."""
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

log = logging.getLogger("agents.job_advisor_agent")

from server.web.agents.advisor.advisor_tools import ADVISOR_TOOLS
from server.web.agents.advisor.prompt import PROMPT

load_dotenv()


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_job_advisor_agent():
    base = ChatAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ANTHROPIC_MODEL"),
        max_tokens=800,
    )
    llm_force = base.bind_tools(ADVISOR_TOOLS, tool_choice="any")
    llm_auto  = base.bind_tools(ADVISOR_TOOLS)

    def assistant(state: State):
        has_results = any(isinstance(m, ToolMessage) for m in state["messages"])
        llm = llm_auto if has_results else llm_force
        prompt = PROMPT.format(today=date.today().strftime("%B %d, %Y"))
        messages = [SystemMessage(content=prompt)] + state["messages"]
        return {"messages": [llm.invoke(messages)]}

    def route(state: State):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            # High-visibility logging for sub-agent tool execution
            for call in last.tool_calls:
                log.info("[TOOL] %s | args=%s", call["name"], call["args"])
            return "tools"
        return END

    graph = StateGraph(State)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(ADVISOR_TOOLS))
    graph.set_entry_point("assistant")
    graph.add_conditional_edges("assistant", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")

    return graph.compile()


_advisor_agent = None


def get_job_advisor_agent():
    global _advisor_agent
    if _advisor_agent is None:
        _advisor_agent = build_job_advisor_agent()
    return _advisor_agent


def run_job_advisor_agent(query: str, history: list | None = None) -> str:
    """Entry point called by the orchestrator tool wrapper."""
    agent = get_job_advisor_agent()
    messages = list(history) if history else []
    messages.append(HumanMessage(content=query))
    result = agent.invoke({"messages": messages})
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)