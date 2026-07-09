from collections import defaultdict
from typing import assert_never

from .parser import (
    ModuleInstance,
    Reference,
    TerraformData,
    TerraformDeclaration,
    TerraformModuleCall,
    TerraformModule,
    TerraformOutput,
    TerraformProject,
    TerraformProvider,
    TerraformResource,
    TerraformVariable,
)

Node = str
SymbolTable = dict[str, Node]


def _node_id(call_chain: tuple[str, ...], decl: TerraformDeclaration) -> Node:
    prefix = ".".join(f"module.{name}" for name in call_chain)
    match decl:
        case TerraformResource(type=t, name=n):
            local = f"resource.{t}.{n}"
        case TerraformVariable(name=n):
            local = f"var.{n}"
        case TerraformOutput(name=n):
            local = f"output.{n}"
        case TerraformModuleCall(name=n):
            local = f"module.{n}"
        case TerraformData(type=t, name=n):
            local = f"data.{t}.{n}"
        case TerraformProvider(name=n):
            local = f"provider.{n}"
        case _ as unreachable:
            assert_never(unreachable)
    return f"{prefix}:{local}"


def _build_symbol_table(call_chain: tuple[str, ...], module: TerraformModule) -> SymbolTable:
    table: SymbolTable = {}
    for decl in module.declarations:
        node = _node_id(call_chain, decl)
        match decl:
            case TerraformResource(type=t, name=n):
                table[f"{t}.{n}"] = node
            case TerraformVariable(name=n):
                table[f"var.{n}"] = node
            case TerraformOutput(name=n):
                table[f"output.{n}"] = node
            case TerraformModuleCall(name=n):
                table[f"module.{n}"] = node
            case TerraformData(type=t, name=n):
                table[f"data.{t}.{n}"] = node
            case TerraformProvider(name=n):
                table[f"provider.{n}"] = node
    return table


def _resolve(path: list[str], table: SymbolTable) -> Node | None:
    for i in range(len(path), 0, -1):
        key = ".".join(path[:i])
        if key in table:
            return table[key]
    return None


def _resolve_refs(refs: list[Reference], table: SymbolTable) -> list[Node]:
    return [target for ref in refs for target in [_resolve(ref, table)] if target is not None]


class DependencyGraph:
    nodes: set[Node]
    edges: dict[Node, set[Node]]  # node -> set of nodes it depends on

    def __init__(self, project: TerraformProject):
        self.nodes = set()
        self.edges = {}
        self._process_instance(project.root)

    def _add_edge(self, node: Node, target: Node) -> None:
        if target != node:
            self.edges.setdefault(node, set()).add(target)

    def _process_instance(self, instance: ModuleInstance) -> SymbolTable:
        call_chain, module = instance.call_chain, instance.module
        table = _build_symbol_table(call_chain, module)

        # Expose each child's outputs to this module's table as module.<call_name>.<output>,
        # so references crossing into a child module resolve to the specific output node
        # (falling back to the module-call node itself when no such output is referenced).
        for call_name, child in instance.children.items():
            child_table = self._process_instance(child)
            for key, node in child_table.items():
                if key.startswith("output."):
                    table[f"module.{call_name}.{key.removeprefix('output.')}"] = node

        for decl in module.declarations:
            node = _node_id(call_chain, decl)
            self.nodes.add(node)
            self.edges.setdefault(node, set())
            for target in _resolve_refs(decl.references, table):
                self._add_edge(node, target)

        # Wire each child's variables back to whatever the module call passes in for them,
        # resolved against this (parent) module's table.
        module_calls = {d.name: d for d in module.declarations if isinstance(d, TerraformModuleCall)}
        for call_name, child in instance.children.items():
            call_decl = module_calls.get(call_name)
            if call_decl is None:
                continue
            for var_decl in child.module.declarations:
                if not isinstance(var_decl, TerraformVariable) or var_decl.name not in call_decl.attributes:
                    continue
                var_node = _node_id(child.call_chain, var_decl)
                for target in _resolve_refs(call_decl.attributes[var_decl.name], table):
                    self._add_edge(var_node, target)

        return table

    def __str__(self) -> str:
        lines = ["DependencyGraph"]
        for node in sorted(self.nodes):
            deps = sorted(self.edges.get(node, set()))
            lines.append(f"  {node}")
            for dep in deps:
                lines.append(f"    -> {dep}")
        return "\n".join(lines)


_NODE_STYLE: dict[str, str] = {
    "resource": 'shape=box style=filled fillcolor="#dae8fc"',
    "var":      'shape=ellipse style=filled fillcolor="#d5e8d4"',
    "output":   'shape=ellipse style=filled fillcolor="#ffe6cc"',
    "module":   'shape=box style=filled fillcolor="#e1d5e7"',
    "data":     'shape=box style=filled fillcolor="#fff2cc"',
    "provider": 'shape=ellipse style=filled fillcolor="#f8cecc"',
}


def _addr(node: Node) -> str:
    return node.split(":", 1)[1]


def _kind(node: Node) -> str:
    return _addr(node).split(".")[0]


def _parent_prefix(prefix: str) -> str:
    """The prefix of the module instance that instantiated this one (each call_chain
    segment is two "." separated tokens: "module", "<call_name>")."""
    if not prefix:
        return prefix
    return ".".join(prefix.split(".")[:-2])


def to_dot(graph: DependencyGraph) -> str:
    by_module: defaultdict[str, list[Node]] = defaultdict(list)
    for node in graph.nodes:
        by_module[node.split(":", 1)[0]].append(node)
    by_module.setdefault("", [])  # the root cluster is always rendered, even if empty

    children_of: defaultdict[str, list[str]] = defaultdict(list)
    for prefix in by_module:
        if prefix:
            children_of[_parent_prefix(prefix)].append(prefix)

    cluster_ids = {prefix: i for i, prefix in enumerate(sorted(by_module))}

    def render_cluster(prefix: str, indent: str) -> list[str]:
        label = prefix if prefix else "root"
        lines = [
            f'{indent}subgraph cluster_{cluster_ids[prefix]} {{',
            f'{indent}  label="{label}"',
            f"{indent}  style=rounded",
        ]
        for node in sorted(by_module[prefix]):
            style = _NODE_STYLE.get(_kind(node), "")
            lines.append(f'{indent}  "{node}" [label="{_addr(node)}" {style}]')
        for child_prefix in sorted(children_of[prefix]):
            lines.extend(render_cluster(child_prefix, indent + "  "))
        lines.append(f"{indent}}}")
        return lines

    lines = ["digraph {", "  rankdir=LR", "  node [fontname=monospace]", ""]
    lines.extend(render_cluster("", "  "))
    lines.append("")

    for source in sorted(graph.edges):
        for target in sorted(graph.edges[source]):
            lines.append(f'  "{source}" -> "{target}"')

    lines.append("}")
    return "\n".join(lines)
