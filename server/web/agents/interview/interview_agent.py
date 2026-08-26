"""Interview Agent — finds real past interview questions and generates practice questions."""
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

from server.web.agents.interview.interview_tools import INTERVIEW_TOOLS
from server.web.agents.interview.prompt import PROMPT

load_dotenv()

log = logging.getLogger("agents.interview_agent")


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_interview_agent():
    base = ChatAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ANTHROPIC_MODEL"),
        max_tokens=1200,
    )
    llm_force = base.bind_tools(INTERVIEW_TOOLS, tool_choice="any")
    llm_auto  = base.bind_tools(INTERVIEW_TOOLS)

    def assistant(state: State):
        has_results = any(isinstance(m, ToolMessage) for m in state["messages"])
        llm = llm_auto if has_results else llm_force
        prompt = PROMPT.format(today=date.today().strftime("%B %d, %Y"))
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
    graph.add_node("tools", ToolNode(INTERVIEW_TOOLS))
    graph.set_entry_point("assistant")
    graph.add_conditional_edges("assistant", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")

    return graph.compile()


_interview_agent = None


def get_interview_agent():
    global _interview_agent
    if _interview_agent is None:
        _interview_agent = build_interview_agent()
    return _interview_agent


def run_interview_agent(query: str, history: list | None = None) -> str:
    """Entry point called by the orchestrator tool wrapper."""
    agent = get_interview_agent()
    messages = list(history) if history else []
    messages.append(HumanMessage(content=query))
    result = agent.invoke({"messages": messages})
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)