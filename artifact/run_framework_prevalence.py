#!/usr/bin/env python3
"""Probe failure-atomic tool admission in pinned agent frameworks.

Each adapter uses the framework's released execution surface with fake local
effects and no network model call. The injected response contains one valid
call followed by one structurally malformed call. Results distinguish a
vulnerable partial admission from a malformed state that cannot be represented
at the tested core boundary.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import sys
import time
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


def _source_binding(obj: Any) -> dict[str, Any]:
    path_text = inspect.getsourcefile(obj) or inspect.getfile(obj)
    path = Path(path_text).resolve()
    parts = path.parts
    if "site-packages" in parts:
        index = parts.index("site-packages")
        portable_path = str(Path(*parts[index + 1 :]))
    else:
        portable_path = path.name
    return {
        "package_relative_path": portable_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _version(distribution: str) -> str:
    return importlib.metadata.version(distribution)


def _result(
    *,
    framework: str,
    versions: dict[str, str],
    classification: str,
    call_1_executed: bool,
    malformed_in_history: bool | None,
    source: dict[str, Any],
    tested_surface: str,
    notes: list[str],
) -> dict[str, Any]:
    return {
        "framework": framework,
        "versions": versions,
        "classification": classification,
        "call_1_executed": call_1_executed,
        "malformed_in_history": malformed_in_history,
        "tested_surface": tested_surface,
        "source_binding": source,
        "notes": notes,
    }


def probe_langchain_langgraph() -> dict[str, Any]:
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool
    from langgraph.prebuilt import ToolNode
    from langgraph.runtime import Runtime

    effects: list[tuple[str, str]] = []

    @tool
    def write_a(path: str, content: str) -> str:
        """Record one isolated test effect."""
        effects.append((path, content))
        return "ok"

    message = AIMessage(
        content="",
        tool_calls=[{
            "name": "write_a",
            "args": {"path": "a", "content": "A"},
            "id": "valid",
            "type": "tool_call",
        }],
        invalid_tool_calls=[{
            "name": "write_a",
            "args": '{"path":"bad',
            "id": "bad",
            "error": "truncated",
            "type": "invalid_tool_call",
        }],
    )
    node = ToolNode([write_a])
    node._func([message], {}, Runtime())
    return _result(
        framework="LangChain/LangGraph",
        versions={
            "langchain": _version("langchain"),
            "langgraph": _version("langgraph"),
        },
        classification="vulnerable_partial_admission",
        call_1_executed=effects == [("a", "A")],
        malformed_in_history=bool(message.invalid_tool_calls),
        source=_source_binding(ToolNode._func),
        tested_surface="langgraph.prebuilt.ToolNode._func",
        notes=[
            "The provider-normalized AIMessage contained one valid tool_call and one invalid_tool_call.",
            "ToolNode executed the valid list without rejecting the response-level invalid sibling.",
        ],
    )


def probe_autogen() -> dict[str, Any]:
    from autogen_core import AgentId, CancellationToken, FunctionCall
    from autogen_core.models import UserMessage
    from autogen_core.tool_agent import ToolAgent, tool_agent_caller_loop
    from autogen_core.tools import FunctionTool

    effects: list[tuple[str, str]] = []

    def write_a(path: str, content: str) -> str:
        effects.append((path, content))
        return "ok"

    tool = FunctionTool(write_a, description="Record one isolated test effect.")
    tool_agent = ToolAgent("test", [tool])

    class Caller:
        async def send_message(
            self,
            message: Any,
            recipient: Any,
            cancellation_token: Any = None,
        ) -> Any:
            del recipient
            context = SimpleNamespace(
                cancellation_token=cancellation_token or CancellationToken()
            )
            return await tool_agent.handle_function_call(message, context)

    class Model:
        def __init__(self) -> None:
            self.calls = 0

        async def create(self, *args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(content=[
                    FunctionCall(
                        id="valid",
                        name="write_a",
                        arguments='{"path":"a","content":"A"}',
                    ),
                    FunctionCall(
                        id="bad",
                        name="write_a",
                        arguments='{"path":"bad',
                    ),
                ])
            return SimpleNamespace(content="done")

    generated = asyncio.run(tool_agent_caller_loop(
        Caller(),
        AgentId("tool", "default"),
        Model(),
        [UserMessage(content="go", source="user")],
        [tool],
    ))
    malformed_in_history = (
        len(generated) >= 1
        and isinstance(generated[0].content, list)
        and any(call.id == "bad" for call in generated[0].content)
    )
    return _result(
        framework="AutoGen",
        versions={
            "autogen-agentchat": _version("autogen-agentchat"),
            "autogen-core": _version("autogen-core"),
        },
        classification="vulnerable_partial_admission",
        call_1_executed=effects == [("a", "A")],
        malformed_in_history=malformed_in_history,
        source=_source_binding(tool_agent_caller_loop),
        tested_surface="autogen_core.tool_agent.tool_agent_caller_loop",
        notes=[
            "The caller loop appended the two-call AssistantMessage before dispatch.",
            "asyncio.gather executed the valid call while the malformed call became a FunctionExecutionResult error.",
        ],
    )


def probe_llamaindex() -> dict[str, Any]:
    from llama_index.core.agent.workflow import ToolCall
    from pydantic import ValidationError

    effects: list[str] = []
    rejected = False
    try:
        ToolCall(
            tool_name="write_a",
            tool_kwargs='{"path":"bad',
            tool_id="bad",
        )
    except ValidationError:
        rejected = True
    if not rejected:
        effects.append("unexpectedly_represented")
    return _result(
        framework="LlamaIndex",
        versions={"llama-index-core": _version("llama-index-core")},
        classification=(
            "core_boundary_structural_rejection"
            if rejected
            else "harness_unexpected_representation"
        ),
        call_1_executed=bool(effects),
        malformed_in_history=False if rejected else None,
        source=_source_binding(ToolCall),
        tested_surface="llama_index.core.agent.workflow.ToolCall validation",
        notes=[
            "The core ToolCall event requires tool_kwargs to be a dictionary.",
            "Provider adapters parse raw argument strings before this boundary; their batch-wide behavior is not established by this core-only probe.",
        ],
    )


def probe_openai_agents() -> dict[str, Any]:
    from agents import Agent, RunConfig, function_tool
    from agents._run_impl import RunImpl
    from agents.items import ModelResponse
    from agents.lifecycle import RunHooks
    from agents.run_context import RunContextWrapper
    from agents.usage import InputTokensDetails, OutputTokensDetails, Usage
    from openai.types.responses import ResponseFunctionToolCall

    effects: list[tuple[str, str]] = []

    @function_tool
    def write_a(path: str, content: str) -> str:
        effects.append((path, content))
        return "ok"

    agent = Agent(name="test", instructions="test", tools=[write_a])
    calls = [
        ResponseFunctionToolCall(
            arguments='{"path":"a","content":"A"}',
            call_id="valid",
            name="write_a",
            type="function_call",
        ),
        ResponseFunctionToolCall(
            arguments='{"path":"bad',
            call_id="bad",
            name="write_a",
            type="function_call",
        ),
    ]
    usage = Usage(
        input_tokens_details=InputTokensDetails(
            cache_write_tokens=0,
            cached_tokens=0,
        ),
        output_tokens_details=OutputTokensDetails(reasoning_tokens=0),
    )
    response = ModelResponse(output=calls, usage=usage, response_id=None)
    processed = RunImpl.process_model_response(
        agent=agent,
        all_tools=[write_a],
        response=response,
        output_schema=None,
        handoffs=[],
    )
    asyncio.run(RunImpl.execute_function_tool_calls(
        agent=agent,
        tool_runs=processed.functions,
        hooks=RunHooks(),
        context_wrapper=RunContextWrapper(context=None, usage=usage),
        config=RunConfig(tracing_disabled=True),
    ))
    return _result(
        framework="OpenAI Agents SDK",
        versions={
            "openai-agents": _version("openai-agents"),
            "openai": _version("openai"),
        },
        classification="vulnerable_partial_admission",
        call_1_executed=effects == [("a", "A")],
        malformed_in_history=any(
            getattr(item.raw_item, "call_id", None) == "bad"
            for item in processed.new_items
        ),
        source=_source_binding(RunImpl.execute_function_tool_calls),
        tested_surface=(
            "agents._run_impl.RunImpl.process_model_response + "
            "execute_function_tool_calls"
        ),
        notes=[
            "Both calls became run items before execution.",
            "Concurrent execution committed the valid call while malformed JSON became a handled tool error.",
        ],
    )


def probe_crewai() -> dict[str, Any]:
    from crewai.agents.crew_agent_executor import CrewAgentExecutor
    from crewai.tools import tool

    effects: list[tuple[str, str]] = []

    @tool("write_a")
    def write_a(path: str, content: str) -> str:
        """Record one isolated test effect."""
        effects.append((path, content))
        return "ok"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        executor = CrewAgentExecutor(original_tools=[write_a])
    executor._tool_name_mapping = {"write_a": write_a}
    calls = [
        SimpleNamespace(
            id="valid",
            function=SimpleNamespace(
                name="write_a",
                arguments='{"path":"a","content":"A"}',
            ),
        ),
        SimpleNamespace(
            id="bad",
            function=SimpleNamespace(
                name="write_a",
                arguments='{"path":"bad',
            ),
        ),
    ]
    executor._handle_native_tool_calls(calls, {"write_a": write_a.run})
    malformed_in_history = any(
        message.get("role") == "assistant"
        and any(
            call.get("id") == "bad"
            for call in message.get("tool_calls", [])
        )
        for message in executor.messages
    )
    return _result(
        framework="CrewAI",
        versions={"crewai": _version("crewai")},
        classification="vulnerable_partial_admission",
        call_1_executed=effects == [("a", "A")],
        malformed_in_history=malformed_in_history,
        source=_source_binding(CrewAgentExecutor._handle_native_tool_calls),
        tested_surface="crewai.agents.CrewAgentExecutor._handle_native_tool_calls",
        notes=[
            "The tested released path is deprecated but remains shipped in CrewAI 1.15.9.",
            "It appended the complete raw batch, executed the valid call, and stored an error result for malformed JSON.",
        ],
    )


def probe_smolagents() -> dict[str, Any]:
    from smolagents import Tool, ToolCallingAgent
    from smolagents.memory import ActionStep
    from smolagents.models import (
        ChatMessage,
        ChatMessageToolCall,
        ChatMessageToolCallFunction,
        MessageRole,
        Model,
    )
    from smolagents.monitoring import Timing

    effects: list[tuple[str, str]] = []

    class WriteTool(Tool):
        name = "write_a"
        description = "Record one isolated test effect."
        inputs = {
            "path": {"type": "string", "description": "target"},
            "content": {"type": "string", "description": "content"},
        }
        output_type = "string"

        def forward(self, path: str, content: str) -> str:
            effects.append((path, content))
            return "ok"

    class ModelStub(Model):
        def __init__(self, message: ChatMessage) -> None:
            super().__init__(model_id="prevalence-stub")
            self.message = message

        def generate(self, *args: Any, **kwargs: Any) -> ChatMessage:
            del args, kwargs
            return self.message

    message = ChatMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=[
            ChatMessageToolCall(
                id="valid",
                type="function",
                function=ChatMessageToolCallFunction(
                    name="write_a",
                    arguments='{"path":"a","content":"A"}',
                ),
            ),
            ChatMessageToolCall(
                id="bad",
                type="function",
                function=ChatMessageToolCallFunction(
                    name="write_a",
                    arguments='{"path":"bad',
                ),
            ),
        ],
    )
    model = ModelStub(message)
    agent = ToolCallingAgent(
        tools=[WriteTool()],
        model=model,
        max_tool_threads=2,
    )
    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=time.time()),
    )
    error_type = None
    try:
        list(agent._step_stream(step))
    except Exception as exc:
        error_type = type(exc).__name__
    malformed_in_history = bool(
        step.model_output_message
        and step.model_output_message.tool_calls
        and any(call.id == "bad" for call in step.model_output_message.tool_calls)
    )
    return _result(
        framework="smolagents",
        versions={"smolagents": _version("smolagents")},
        classification="vulnerable_partial_admission",
        call_1_executed=effects == [("a", "A")],
        malformed_in_history=malformed_in_history,
        source=_source_binding(ToolCallingAgent._step_stream),
        tested_surface="smolagents.ToolCallingAgent._step_stream",
        notes=[
            f"The valid call committed before the malformed sibling raised {error_type}.",
            "The raw model output was assigned to the ActionStep before argument parsing and execution.",
        ],
    )


PROBES: list[Callable[[], dict[str, Any]]] = [
    probe_langchain_langgraph,
    probe_autogen,
    probe_llamaindex,
    probe_openai_agents,
    probe_crewai,
    probe_smolagents,
]


def run() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for probe in PROBES:
        try:
            results.append(probe())
        except Exception as exc:
            results.append({
                "framework": probe.__name__.removeprefix("probe_"),
                "classification": "harness_error",
                "call_1_executed": None,
                "malformed_in_history": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
    vulnerable = [
        result
        for result in results
        if result["classification"] == "vulnerable_partial_admission"
        and result["call_1_executed"]
    ]
    return {
        "format": "tool_admission_framework_prevalence/v1",
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "injection": "valid_call_then_truncated_json_call",
        "framework_surfaces": len(results),
        "vulnerable_partial_admission_count": len(vulnerable),
        "structural_rejection_count": sum(
            result["classification"] == "core_boundary_structural_rejection"
            for result in results
        ),
        "harness_error_count": sum(
            result["classification"] == "harness_error"
            for result in results
        ),
        "claim_boundary": (
            "Pinned released Python surfaces only. LlamaIndex provider adapters "
            "remain unresolved because the tested core event requires parsed dict arguments."
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "results"
            / "framework_prevalence.json"
        ),
    )
    args = parser.parse_args()
    payload = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: payload[key]
        for key in (
            "framework_surfaces",
            "vulnerable_partial_admission_count",
            "structural_rejection_count",
            "harness_error_count",
        )
    }, indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0 if payload["harness_error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
