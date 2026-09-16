import argparse
import logging
import sys

from dotenv import load_dotenv

from .agentic_check import AgenticCheck, ReasoningEffort
from .checks import RedundantDependsOnCheck
from .diagnostics import AnalysisContext, DiagnosticProvider, run_diagnostics
from .graph import DependencyGraph, to_dot
from .parser import TerraformProject

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


class _Args(argparse.Namespace):
    path: str
    graph: bool
    agentic_model: str | None
    agentic_effort: ReasoningEffort | None
    agentic_temperature: float | None
    agentic_region: str | None
    log_level: str


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Print the dependency graph as DOT and exit — skips all diagnostic "
        "checks, mechanical and agentic.",
    )
    parser.add_argument(
        "--agentic-model",
        help="Bedrock model id (e.g. anthropic.claude-sonnet-4-5-20250929-v1:0). "
        "If set, also runs the LLM-based check alongside the mechanical ones.",
    )
    parser.add_argument("--agentic-effort", choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--agentic-temperature", type=float)
    parser.add_argument("--agentic-region", help="AWS region; falls back to AWS_DEFAULT_REGION.")
    parser.add_argument(
        "--log-level",
        choices=_LOG_LEVELS,
        default="WARNING",
        help="Logging verbosity for dependency_fixer's own logger (tool calls, token usage, ...).",
    )
    args = parser.parse_args(namespace=_Args())

    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")

    project = TerraformProject(args.path)
    graph = DependencyGraph(project)

    if args.graph:
        print(to_dot(graph))
        return

    providers: list[DiagnosticProvider] = [RedundantDependsOnCheck()]
    if args.agentic_model:
        providers.append(AgenticCheck(
            args.agentic_model,
            effort=args.agentic_effort,
            temperature=args.agentic_temperature,
            region_name=args.agentic_region,
        ))

    context = AnalysisContext(project=project, graph=graph)
    for diagnostic in run_diagnostics(context, providers):
        print(
            f"[{diagnostic.severity}] ({diagnostic.origin}) {diagnostic.category} "
            f"{diagnostic.node} -> {diagnostic.target}: {diagnostic.message}",
            file=sys.stderr,
        )
        if diagnostic.fix is not None:
            print(
                f"    suggested fix: set `{diagnostic.fix.field}` on {diagnostic.node} to: "
                f"{diagnostic.fix.expression}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
