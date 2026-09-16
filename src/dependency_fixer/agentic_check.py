import logging
from typing import Literal

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider

from .diagnostics import AnalysisContext, Category, DataDependencyFix, Diagnostic, DiagnosticSink, Severity
from .graph import Node, to_agent_json

logger = logging.getLogger(__name__)

ReasoningEffort = Literal["minimal", "low", "medium", "high"]

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

Only report findings you are reasonably confident about. When you are done, reply
with a one-line summary of how many findings you reported.
""".strip()


class AgenticCheck:
    """DiagnosticProvider that delegates to an LLM (over AWS Bedrock) to find
    dependency problems that aren't mechanically formalizable — the counterpart to
    RedundantDependsOnCheck. The tool the model calls to report findings, and the
    shape of what it can report, are fixed; only the model and its connection/
    sampling parameters are configurable per instance."""

    def __init__(
        self,
        model_name: str,
        *,
        effort: ReasoningEffort | None = None,
        temperature: float | None = None,
        api_key: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._effort = effort
        self._temperature = temperature
        self._api_key = api_key
        self._region_name = region_name

    @property
    def name(self) -> str:
        return f"agentic-check:{self._model_name}"

    def run(self, context: AnalysisContext, sink: DiagnosticSink) -> None:
        provider = (
            BedrockProvider(api_key=self._api_key, region_name=self._region_name)
            if self._api_key is not None
            else BedrockProvider(region_name=self._region_name)
        )
        model = BedrockConverseModel(self._model_name, provider=provider)

        settings: BedrockModelSettings = {}
        if self._temperature is not None:
            settings["temperature"] = self._temperature
        if self._effort is not None:
            settings["thinking"] = self._effort

        agent: Agent[None, str] = Agent(
            model,
            system_prompt=_SYSTEM_PROMPT,
            model_settings=settings or None,
        )

        valid_nodes = context.graph.nodes

        @agent.tool_plain
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

        result = agent.run_sync(self._build_prompt(context))

        usage = result.usage
        logger.info(
            "%s: run complete — requests=%d tool_calls=%d input_tokens=%d output_tokens=%d",
            self.name, usage.requests, usage.tool_calls, usage.input_tokens, usage.output_tokens,
        )

    def _build_prompt(self, context: AnalysisContext) -> str:
        sources = "\n\n".join(f"# {path}\n{text}" for path, text in context.source_files())
        return (
            f"Dependency graph (JSON):\n{to_agent_json(context.graph)}\n\n"
            f"Project source files:\n{sources}"
        )
