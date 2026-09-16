import os
import shutil
import sys
from collections.abc import Sequence
from typing import TextIO

from .diagnostics import Diagnostic, Severity

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_SEVERITY_COLOR: dict[Severity, str] = {
    "error": "\033[1;31m",
    "warning": "\033[1;33m",
    "info": "\033[1;36m",
}
_SEVERITY_ORDER: tuple[Severity, ...] = ("error", "warning", "info")


def _supports_color(stream: TextIO) -> bool:
    return stream.isatty() and os.environ.get("NO_COLOR") is None


def _style(text: str, code: str, *, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def render_diagnostics(diagnostics: Sequence[Diagnostic], stream: TextIO = sys.stdout) -> None:
    """Prints a human-readable diagnostics report to `stream` (stdout by
    default) — kept separate from `dependency_fixer`'s own logging (which stays
    on stderr) so the actual result of a run doesn't get lost in tool-call/token
    log noise when --log-level is raised."""
    color = _supports_color(stream)
    width = max(40, min(shutil.get_terminal_size(fallback=(80, 24)).columns, 100))
    rule = _style("─" * width, _DIM, color=color)

    if not diagnostics:
        print("No diagnostics found.", file=stream)
        return

    for diagnostic in diagnostics:
        print(rule, file=stream)
        tag = _style(f"[{diagnostic.severity.upper()}]", _SEVERITY_COLOR[diagnostic.severity], color=color)
        category = _style(diagnostic.category, _BOLD, color=color)
        origin = _style(diagnostic.origin, _DIM, color=color)
        print(f"{tag} {category}  {origin}", file=stream)
        print(f"  {diagnostic.node} → {diagnostic.target}", file=stream)
        print(file=stream)
        print(f"  {diagnostic.message}", file=stream)
        if diagnostic.fix is not None:
            print(file=stream)
            print(f"  {_style('fix:', _BOLD, color=color)} set `{diagnostic.fix.field}` to:", file=stream)
            print(f"      {diagnostic.fix.expression}", file=stream)
        print(file=stream)

    print(rule, file=stream)
    print(_style(_summary(diagnostics), _BOLD, color=color), file=stream)


def _summary(diagnostics: Sequence[Diagnostic]) -> str:
    counts: dict[Severity, int] = {}
    for diagnostic in diagnostics:
        counts[diagnostic.severity] = counts.get(diagnostic.severity, 0) + 1
    parts = [f"{counts[s]} {s}{'s' if counts[s] != 1 else ''}" for s in _SEVERITY_ORDER if s in counts]
    plural = "s" if len(diagnostics) != 1 else ""
    return f"{len(diagnostics)} diagnostic{plural} ({', '.join(parts)})"
