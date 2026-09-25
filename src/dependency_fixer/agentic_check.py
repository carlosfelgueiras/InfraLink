import logging
from collections.abc import AsyncIterable

import httpx
from pydantic_ai import (
    Agent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRetry,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    RunContext,
)
from pydantic_ai.messages import AgentStreamEvent, TextPartDelta, ThinkingPartDelta, ToolCallPartDelta

from .diagnostics import AnalysisContext, Category, DataDependencyFix, Diagnostic, DiagnosticSink, Severity
from .graph import Node, to_agent_json
from .providers import PROFILES, ReasoningEffort
from .registry_docs import ProviderDocNotFound, fetch_resource_doc

logger = logging.getLogger(__name__)


def _describe_stream_event(event: AgentStreamEvent) -> str:
    match event:
        case PartStartEvent(index=index, part=part):
            return f"part_start[{index}]: {part.part_kind}"
        case PartEndEvent(index=index, part=part):
            return f"part_end[{index}]: {part.part_kind}"
        case PartDeltaEvent(index=index, delta=TextPartDelta(content_delta=text)):
            return f"part_delta[{index}]: text {text!r}"
        case PartDeltaEvent(index=index, delta=ThinkingPartDelta(content_delta=text)):
            return f"part_delta[{index}]: thinking {text!r}"
        case PartDeltaEvent(index=index, delta=ToolCallPartDelta(tool_name_delta=name, args_delta=args)):
            return f"part_delta[{index}]: tool_call name_delta={name!r} args_delta={args!r}"
        case FunctionToolCallEvent(part=part):
            return f"function_tool_call: {part.tool_name}(args={part.args})"
        case FunctionToolResultEvent(part=part, content=content):
            return f"function_tool_result: {part.tool_name} -> {content!r}"
        case FinalResultEvent(tool_name=tool_name):
            return f"final_result: tool_name={tool_name}"
        case _:
            return event.event_kind

_SYSTEM_PROMPT = """
You are a Terraform dependency auditor. You are given a project's dependency graph
as JSON — `{"nodes": [...]}`, where each node object has:
  - "id": the node's address, Terraform's own resource-addressing scheme, e.g.
    ":resource.aws_instance.example" or "module.foo:resource.aws_instance.bar".
  - "kind": one of "resource", "data", "module", "var", "output", "provider".
  - "module": the module instance this node belongs to ("" for the root module).
  - "implicit_deps": node ids this node depends on via an ordinary attribute reference.
  - "depends_on_deps": node ids this node depends on via an explicit `depends_on`.
— and the full source of every .tf file in the project.

The graph already captures every dependency implied by attribute references and by
explicit `depends_on` (that's exactly what "implicit_deps"/"depends_on_deps" are).
Your job is to find dependency problems that this mechanical analysis cannot see:

- "missing": `node` should depend on `target` (real-world/operational ordering that
  no attribute reference or `depends_on` expresses), but currently doesn't.
- "redundant": `node` has an explicit `depends_on` on `target` that duplicates a
  dependency already established some other way.

For every problem you find, call `report_diagnostic` once with the exact `node` and
`target` addresses implicated, copied verbatim from the graph's "id" fields. `node`
is the resource that has (or should have) the dependency; `target` is the resource
it depends on (or should depend on).

For a "missing" finding, if — and only if — there's a clean way to establish the
dependency as an actual data reference instead of a bare `depends_on`, also pass
`fix`: set `fix.field` to an attribute name on `node` and `fix.expression` to an HCL
expression for that field which references `target` at least once, so assigning
`field = expression` on `node` would make Terraform infer the ordering implicitly.
Omit `fix` if no such data-dependency fix exists — a bare `depends_on` is still a
valid way to close a "missing" finding, `fix` is only for when something more
idiomatic is possible.

If you're not sure whether a resource or data source type has real-world lifecycle
behavior that would justify a "missing" finding (e.g. asynchronous provisioning,
eventual consistency, a readiness delay after creation), call `fetch_provider_doc`
to pull its official Terraform Registry documentation rather than guessing from
memory alone.

Only report findings you are reasonably confident about. When you are done, reply
with a one-line summary of how many findings you reported.
""".strip()


class UnknownProfile(ValueError):
    """The requested agentic-check profile isn't in the PROFILES registry."""


class AgenticCheck:
    """DiagnosticProvider that delegates to an LLM to find dependency problems
    that aren't mechanically formalizable — the counterpart to
    RedundantDependsOnCheck. `profile` selects a backend (Bedrock, OpenRouter,
    a generic OpenAI-compatible server, ...) from the `PROFILES` registry in
    `providers.py`; the tool the model calls to report findings, and the shape
    of what it can report, are fixed — only the backend and sampling
    parameters are configurable per instance."""

    def __init__(
        self,
        profile: str,
        *,
        effort: ReasoningEffort | None = None,
        temperature: float | None = None,
    ) -> None:
        self._profile = profile
        self._effort = effort
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"agentic-check:{self._profile}"

    def run(self, context: AnalysisContext, sink: DiagnosticSink) -> None:
        backend = PROFILES.get(self._profile)
        if backend is None:
            raise UnknownProfile(f"unknown agentic profile {self._profile!r} — known profiles: {sorted(PROFILES)}")

        model = backend.build_model()
        settings = backend.build_settings(effort=self._effort, temperature=self._temperature)

        agent: Agent[None, str] = Agent(
            model,
            system_prompt=_SYSTEM_PROMPT,
            model_settings=settings or None,
        )

        stream_debug = logger.isEnabledFor(logging.DEBUG)

        async def log_stream_events(_ctx: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
            async for event in events:
                logger.debug("%s: %s", self.name, _describe_stream_event(event))

        valid_nodes = context.graph.nodes

        @agent.tool_plain(retries=3)
        def report_diagnostic(
            category: Category,
            severity: Severity,
            message: str,
            node: Node,
            target: Node,
            fix: DataDependencyFix | None = None,
        ) -> str:
            """Report one dependency diagnostic finding.

            Args:
                category: "redundant" (an explicit depends_on from `node` to
                    `target` is redundant) or "missing" (`node` should depend on
                    `target` but doesn't).
                severity: "error", "warning", or "info".
                message: human-readable explanation, referencing `node` and `target`.
                node: the resource that has (or should have) the dependency,
                    verbatim as it appears as a node "id" in the graph (e.g.
                    ":resource.aws_instance.example").
                target: the resource `node` depends on (or should depend on),
                    same format as `node`.
                fix: only for category="missing". An optional, more idiomatic
                    alternative to a bare `depends_on`: set `field` (an attribute
                    name on `node`) to `expression` (an HCL expression that must
                    reference `target` at least once). Omit if no clean
                    data-dependency fix exists.
            """
            unknown = [n for n in (node, target) if n not in valid_nodes]
            if unknown:
                logger.warning(
                    "%s: tool call report_diagnostic rejected — unknown node(s) %r",
                    self.name, unknown,
                )
                raise ModelRetry(
                    f"Unknown node address(es) {unknown!r} — use addresses exactly "
                    "as they appear as node \"id\" fields in the graph."
                )
            if fix is not None and category != "missing":
                logger.warning(
                    "%s: tool call report_diagnostic rejected — fix given for category=%r",
                    self.name, category,
                )
                raise ModelRetry("`fix` is only valid when category is 'missing'.")
            logger.info(
                "%s: tool call report_diagnostic(category=%r, severity=%r, node=%r, target=%r, fix=%r): %s",
                self.name, category, severity, node, target, fix, message,
            )
            sink.push(Diagnostic(
                category=category,
                severity=severity,
                message=message,
                node=node,
                target=target,
                fix=fix,
            ))
            return "recorded"

        @agent.tool_plain
        def fetch_provider_doc(provider: str, resource_type: str, namespace: str = "hashicorp") -> str:
            """Fetch the official Terraform Registry documentation for a resource
            or data source type, as markdown. Use this to check a type's real
            lifecycle behavior (async provisioning, eventual consistency, readiness
            delays) instead of guessing.

            Args:
                provider: the provider's short name, e.g. "aws", "azurerm", "google".
                resource_type: the full type, e.g. "aws_db_instance". The
                    provider's own prefix is stripped automatically.
                namespace: the registry namespace publishing this provider.
                    Default "hashicorp" is correct for the major official cloud
                    providers; pass a different one for a community provider.
            """
            logger.info(
                "%s: tool call fetch_provider_doc(namespace=%r, provider=%r, resource_type=%r)",
                self.name, namespace, provider, resource_type,
            )
            try:
                return fetch_resource_doc(namespace, provider, resource_type)
            except ProviderDocNotFound as exc:
                logger.warning("%s: fetch_provider_doc found nothing: %s", self.name, exc)
                return str(exc)
            except httpx.HTTPError as exc:
                logger.warning("%s: fetch_provider_doc request failed: %s", self.name, exc)
                return f"Failed to fetch documentation: {exc}"

        result = agent.run_sync(
            self._build_prompt(context),
            event_stream_handler=log_stream_events if stream_debug else None,
        )

        usage = result.usage
        logger.info(
            "%s: run complete — requests=%d tool_calls=%d input_tokens=%d output_tokens=%d",
            self.name, usage.requests, usage.tool_calls, usage.input_tokens, usage.output_tokens,
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("%s: full chat trajectory: %s", self.name, result.all_messages_json().decode())

    def _build_prompt(self, context: AnalysisContext) -> str:
        sources = "\n\n".join(f"# {path}\n{text}" for path, text in context.source_files())
        return (
            f"Dependency graph (JSON):\n{to_agent_json(context.graph)}\n\n"
            f"Project source files:\n{sources}"
        )
