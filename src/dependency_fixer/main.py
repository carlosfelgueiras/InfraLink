import argparse
import sys

from .agentic_check import AgenticCheck, ReasoningEffort
from .checks import RedundantDependsOnCheck
from .diagnostics import AnalysisContext, DiagnosticProvider, run_diagnostics
from .graph import DependencyGraph
from .parser import TerraformProject


class _Args(argparse.Namespace):
    path: str
    agentic_model: str | None
    agentic_effort: ReasoningEffort | None
    agentic_temperature: float | None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument(
        "--agentic-model",
        help="OpenRouter model id (e.g. anthropic/claude-sonnet-4.5). "
        "If set, also runs the LLM-based check alongside the mechanical ones.",
    )
    parser.add_argument("--agentic-effort", choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--agentic-temperature", type=float)
    args = parser.parse_args(namespace=_Args())

    project = TerraformProject(args.path)
    graph = DependencyGraph(project)

    providers: list[DiagnosticProvider] = [RedundantDependsOnCheck()]
    if args.agentic_model:
        providers.append(AgenticCheck(
            args.agentic_model,
            effort=args.agentic_effort,
            temperature=args.agentic_temperature,
        ))

    context = AnalysisContext(project=project, graph=graph)
    for diagnostic in run_diagnostics(context, providers):
        print(f"[{diagnostic.severity}] {diagnostic.category}: {diagnostic.message}", file=sys.stderr)


if __name__ == "__main__":
    main()
