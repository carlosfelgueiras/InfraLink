from .diagnostics import AnalysisContext, Diagnostic, DiagnosticSink
from .graph import Node


class RedundantDependsOnCheck:
    """Flags `depends_on` entries whose target is already reachable through
    ordinary attribute references alone — i.e. no `depends_on` anywhere in the
    chain is needed to establish the dependency, so the explicit one is redundant."""

    name = "redundant-depends-on-check"

    def run(self, context: AnalysisContext, sink: DiagnosticSink) -> None:
        graph = context.graph
        reachable_cache: dict[Node, set[Node]] = {}

        def implicit_reachable(start: Node) -> set[Node]:
            if start in reachable_cache:
                return reachable_cache[start]
            seen: set[Node] = set()
            stack = list(graph.implicit_edges.get(start, ()))
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(graph.implicit_edges.get(current, ()))
            reachable_cache[start] = seen
            return seen

        for node, targets in graph.depends_on_edges.items():
            reachable = implicit_reachable(node)
            for target in sorted(targets):
                if target in reachable:
                    sink.push(Diagnostic(
                        category="redundant",
                        severity="warning",
                        message=(
                            f"{node}: explicit depends_on of {target} is redundant — "
                            "already implied by attribute references"
                        ),
                        nodes=(node, target),
                    ))
