from typing import Literal

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider

from .diagnostics import AnalysisContext, Category, Diagnostic, DiagnosticSink, Severity
from .graph import Node, to_dot

ReasoningEffort = Literal["minimal", "low", "medium", "high"]

_SYSTEM_PROMPT = """
You are a Terraform dependency auditor. You are given a project's dependency graph
(as DOT) and the full source of every .tf file in the project. Each graph node's
address follows Terraform's own resource-addressing scheme, e.g.
":resource.aws_instance.example" or "module.foo.resource.aws_instance.bar".

The graph already captures every dependency implied by attribute references and by
explicit `depends_on`. Your job is to find dependency problems that this mechanical
analysis cannot see: missing dependencies implied by real-world/operational ordering
that no attribute reference or `depends_on` expresses, and redundant dependencies
that duplicate a relationship already established some other way.

For every problem you find, call `report_diagnostic` once with the exact node
addresses implicated, copied verbatim from the DOT graph. Only report findings you
are reasonably confident about. When you are done, reply with a one-line summary of
how many findings you reported.
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
        origin = f"agentic-check:{self._model_name}"

        @agent.tool_plain
        def report_diagnostic(
            category: Category,
            severity: Severity,
            message: str,
            nodes: list[Node],
        ) -> str:
            """Report one dependency diagnostic finding.

            Args:
                category: "redundant" or "missing".
                severity: "error", "warning", or "info".
                message: human-readable explanation, referencing the implicated nodes.
                nodes: graph node addresses implicated, verbatim as they appear in
                    the DOT graph (e.g. ":resource.aws_instance.example").
            """
            unknown = [n for n in nodes if n not in valid_nodes]
            if unknown:
                raise ModelRetry(
                    f"Unknown node address(es) {unknown!r} — use addresses exactly "
                    "as they appear in the DOT graph."
                )
            sink.push(Diagnostic(
                category=category,
                severity=severity,
                message=message,
                nodes=tuple(nodes),
                origin=origin,
            ))
            return "recorded"

        agent.run_sync(self._build_prompt(context))

    def _build_prompt(self, context: AnalysisContext) -> str:
        sources = "\n\n".join(f"# {path}\n{text}" for path, text in context.source_files())
        return (
            f"Dependency graph (DOT):\n{to_dot(context.graph)}\n\n"
            f"Project source files:\n{sources}"
        )
