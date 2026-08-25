from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from .graph import DependencyGraph, Node
from .parser import TerraformProject

Severity = Literal["error", "warning", "info"]
Category = Literal["redundant", "missing"]


@dataclass(frozen=True)
class Diagnostic:
    category: Category
    severity: Severity
    message: str
    nodes: tuple[Node, ...]
    origin: str  # name of the provider that raised this diagnostic


class DiagnosticSink(Protocol):
    def push(self, diagnostic: Diagnostic) -> None: ...


class DiagnosticCollector:
    """In-memory sink. A provider (mechanical or agentic) pushes findings into
    this as it works; the final result is read back once it's done."""

    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []

    def push(self, diagnostic: Diagnostic) -> None:
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)


@dataclass(frozen=True)
class AnalysisContext:
    """Everything a diagnostic provider needs: the resolved dependency graph and
    the project's file tree (for a provider — especially an LLM-based one — that
    wants to see the original source alongside the graph)."""

    project: TerraformProject
    graph: DependencyGraph

    def source_files(self) -> Iterator[tuple[str, str]]:
        seen: set[str] = set()
        for module in self.project.modules.values():
            for tf_file in module.files:
                if tf_file.path not in seen:
                    seen.add(tf_file.path)
                    yield tf_file.path, Path(tf_file.path).read_text()


class DiagnosticProvider(Protocol):
    def run(self, context: AnalysisContext, sink: DiagnosticSink) -> None: ...


def run_diagnostics(context: AnalysisContext, providers: Sequence[DiagnosticProvider]) -> tuple[Diagnostic, ...]:
    collector = DiagnosticCollector()
    for provider in providers:
        provider.run(context, collector)
    return collector.diagnostics
