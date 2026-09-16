from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol

from .graph import DependencyGraph, Node
from .parser import TerraformProject

Severity = Literal["error", "warning", "info"]
Category = Literal["redundant", "missing"]


@dataclass(frozen=True)
class DataDependencyFix:
    """A suggested way to fix a "missing" diagnostic by wiring an actual data
    reference into the dependent resource, instead of just adding a bare
    `depends_on`. Setting `field = expression` on the dependent resource
    (`Diagnostic.node`) should make Terraform infer the same ordering
    implicitly, more idiomatically than an explicit `depends_on` would.
    `expression` must reference `Diagnostic.target` at least once."""

    field: str
    expression: str


@dataclass(frozen=True)
class Diagnostic:
    category: Category
    severity: Severity
    message: str
    node: Node  # the resource that has (or should have) the dependency
    target: Node  # the resource it depends on (or is missing a dependency on)
    fix: DataDependencyFix | None = None  # only meaningful when category == "missing"
    origin: str = ""  # name of the provider that raised this; stamped by run_diagnostics

    def __post_init__(self) -> None:
        if self.fix is not None and self.category != "missing":
            raise ValueError("Diagnostic.fix is only valid when category is 'missing'")


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
    @property
    def name(self) -> str: ...

    def run(self, context: AnalysisContext, sink: DiagnosticSink) -> None: ...


class _TaggingSink:
    """Wraps a sink so every diagnostic a provider pushes is stamped with that
    provider's name, regardless of what (if anything) the provider set itself."""

    def __init__(self, sink: DiagnosticSink, origin: str) -> None:
        self._sink = sink
        self._origin = origin

    def push(self, diagnostic: Diagnostic) -> None:
        self._sink.push(replace(diagnostic, origin=self._origin))


def run_diagnostics(context: AnalysisContext, providers: Sequence[DiagnosticProvider]) -> tuple[Diagnostic, ...]:
    collector = DiagnosticCollector()
    for provider in providers:
        provider.run(context, _TaggingSink(collector, provider.name))
    return collector.diagnostics
