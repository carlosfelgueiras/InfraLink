import argparse
import logging

from dotenv import load_dotenv

from .agentic_check import AgenticCheck
from .checks import RedundantDependsOnCheck
from .diagnostics import AnalysisContext, DiagnosticProvider, run_diagnostics
from .graph import DependencyGraph, to_dot
from .parser import TerraformProject
from .providers import PROFILES, ReasoningEffort
from .report import render_diagnostics, render_diagnostics_json

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


class _Args(argparse.Namespace):
    path: str
    graph: bool
    json: bool
    agentic_profile: str | None
    agentic_effort: ReasoningEffort | None
    agentic_temperature: float | None
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
        "--json",
        action="store_true",
        help="Print diagnostics as a single JSON document instead of the "
        "human-readable report.",
    )
    parser.add_argument(
        "--agentic-profile",
        choices=sorted(PROFILES),
        help="Backend/model profile from providers.py's PROFILES registry. "
        "If set, also runs the LLM-based check alongside the mechanical ones.",
    )
    parser.add_argument("--agentic-effort", choices=["minimal", "low", "medium", "high"], default="low")
    parser.add_argument("--agentic-temperature", type=float)
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
    if args.agentic_profile:
        providers.append(AgenticCheck(
            args.agentic_profile,
            effort=args.agentic_effort,
            temperature=args.agentic_temperature,
        ))

    context = AnalysisContext(project=project, graph=graph)
    diagnostics = run_diagnostics(context, providers)
    if args.json:
        render_diagnostics_json(diagnostics)
    else:
        render_diagnostics(diagnostics)


if __name__ == "__main__":
    main()
