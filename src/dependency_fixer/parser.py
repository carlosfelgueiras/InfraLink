from os import scandir
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal
import re

import hcl2
from hcl2.rules.base import BodyRule, BlockRule, AttributeRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import (
    StringRule,
    InterpolationRule,
    HeredocTemplateRule,
    HeredocTrimTemplateRule,
)
from hcl2.rules.expressions import ExprTermRule, ConditionalRule, BinaryOpRule, UnaryOpRule
from hcl2.rules.indexing import (
    GetAttrExprTermRule,
    IndexExprTermRule,
    SqbIndexRule,
    AttrSplatExprTermRule,
    FullSplatExprTermRule,
)
from hcl2.rules.functions import FunctionCallRule
from hcl2.rules.containers import TupleRule, ObjectRule, ObjectElemKeyExpressionRule
from hcl2.rules.for_expressions import ForTupleExprRule, ForObjectExprRule

# A dotted reference chain found in an expression, e.g. "aws_vpc.main.id" -> ["aws_vpc", "main", "id"].
Reference = list[str]
Attributes = dict[str, list[Reference]]

# HCL's grammar captures heredoc bodies as a single opaque token rather than a parsed
# expression tree, so interpolations inside them can't be walked structurally. Fall back
# to a text scan for just that content.
_INTERP_PATTERN = re.compile(r'\$\{([^}]+)\}')
_REF_PATTERN = re.compile(r'\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)')


def _references_in_text(text: str) -> list[Reference]:
    return [m.split(".") for interp in _INTERP_PATTERN.findall(text) for m in _REF_PATTERN.findall(interp)]


def _literal_string(rule: object) -> str | None:
    """Best-effort literal text of a block label or plain string attribute value
    (e.g. a module's "source"). Returns None if the value isn't a plain literal
    (e.g. it contains interpolation)."""
    if isinstance(rule, ExprTermRule):
        return _literal_string(rule.expression)
    if isinstance(rule, IdentifierRule):
        return str(rule.token.value)
    if isinstance(rule, StringRule):
        chars: list[str] = []
        for part in rule.string_parts:
            if isinstance(part.content, InterpolationRule):
                return None
            chars.append(str(part.content.value))
        return "".join(chars)
    return None


def _flatten_get_attr_chain(expr: object, bound: frozenset[str], side: list[Reference]) -> Reference | None:
    """If `expr` is an identifier / get-attr / index / splat chain rooted at a
    non-bound name, return its dotted path (indices and splats don't change which
    declaration is referenced, only which instance/attribute of it, so they're
    dropped from the path but any references *inside* an index expression are
    appended to `side`). Returns None if `expr` isn't such a chain at all, or its
    root is a bound (for-expression loop) variable."""
    if isinstance(expr, ExprTermRule):
        return _flatten_get_attr_chain(expr.expression, bound, side)
    if isinstance(expr, IdentifierRule):
        name = str(expr.token.value)
        return None if name in bound else [name]
    if isinstance(expr, GetAttrExprTermRule):
        base = _flatten_get_attr_chain(expr.expr_term, bound, side)
        return None if base is None else [*base, str(expr.get_attr.identifier.token.value)]
    if isinstance(expr, IndexExprTermRule):
        base = _flatten_get_attr_chain(expr.children[0], bound, side)
        index = expr.children[1]
        if isinstance(index, SqbIndexRule):
            side.extend(_references_in(index.index_expression, bound))
        return base
    if isinstance(expr, (AttrSplatExprTermRule, FullSplatExprTermRule)):
        return _flatten_get_attr_chain(expr.expr_term, bound, side)
    return None


def _references_in(expr: object, bound: frozenset[str] = frozenset()) -> list[Reference]:
    """Find every reference chain anywhere within an expression (the "name
    resolution" pass): plain get-attr chains, references nested inside string
    interpolations, function call arguments, collection literals, conditionals,
    binary/unary operators, and for-expressions (whose bound loop variables are
    excluded from the result)."""
    if isinstance(expr, ExprTermRule):
        return _references_in(expr.expression, bound)

    if isinstance(
        expr, (IdentifierRule, GetAttrExprTermRule, IndexExprTermRule, AttrSplatExprTermRule, FullSplatExprTermRule)
    ):
        side: list[Reference] = []
        chain = _flatten_get_attr_chain(expr, bound, side)
        return [*([chain] if chain is not None and len(chain) >= 2 else []), *side]

    if isinstance(expr, StringRule):
        return [
            ref
            for part in expr.string_parts
            if isinstance(part.content, InterpolationRule)
            for ref in _references_in(part.content.expression, bound)
        ]

    if isinstance(expr, (HeredocTemplateRule, HeredocTrimTemplateRule)):
        return _references_in_text(str(expr.heredoc.value))

    if isinstance(expr, TupleRule):
        return [ref for el in expr.elements for ref in _references_in(el, bound)]

    if isinstance(expr, ObjectRule):
        refs: list[Reference] = []
        for elem in expr.elements:
            if isinstance(elem.key, ObjectElemKeyExpressionRule):
                refs.extend(_references_in(elem.key.expression, bound))
            refs.extend(_references_in(elem.expression, bound))
        return refs

    if isinstance(expr, FunctionCallRule):
        args = expr.arguments
        return [] if args is None else [ref for arg in args.arguments for ref in _references_in(arg, bound)]

    if isinstance(expr, ConditionalRule):
        return [
            *_references_in(expr.condition, bound),
            *_references_in(expr.if_true, bound),
            *_references_in(expr.if_false, bound),
        ]

    if isinstance(expr, BinaryOpRule):
        return [
            *_references_in(expr.expr_term, bound),
            *_references_in(expr.binary_term.expr_term, bound),
        ]

    if isinstance(expr, UnaryOpRule):
        return _references_in(expr.expr_term, bound)

    if isinstance(expr, (ForTupleExprRule, ForObjectExprRule)):
        intro = expr.for_intro
        inner_bound = bound | {str(intro.first_iterator.token.value)}
        if intro.second_iterator is not None:
            inner_bound = inner_bound | {str(intro.second_iterator.token.value)}
        refs = list(_references_in(intro.iterable, bound))
        if isinstance(expr, ForTupleExprRule):
            refs.extend(_references_in(expr.value_expr, inner_bound))
        else:
            refs.extend(_references_in(expr.key_expr, inner_bound))
            refs.extend(_references_in(expr.value_expr, inner_bound))
        if expr.condition is not None:
            refs.extend(_references_in(expr.condition.condition_expr, inner_bound))
        return refs

    return []


def _walk_body(body: BodyRule) -> tuple[Attributes, list[Reference]]:
    """Return (top-level attribute name -> its references, all references found
    anywhere in this body including nested sub-blocks like `ingress { ... }`)."""
    attributes: Attributes = {}
    all_refs: list[Reference] = []
    for child in body.children:
        if isinstance(child, AttributeRule):
            refs = _references_in(child.expression)
            attributes[str(child.identifier.token.value)] = refs
            all_refs.extend(refs)
        elif isinstance(child, BlockRule):
            _, nested_refs = _walk_body(child.body)
            all_refs.extend(nested_refs)
    return attributes, all_refs


@dataclass
class TerraformResource:
    type: str
    name: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["resource"] = field(default="resource", init=False)


@dataclass
class TerraformVariable:
    name: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["variable"] = field(default="variable", init=False)


@dataclass
class TerraformOutput:
    name: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["output"] = field(default="output", init=False)


@dataclass
class TerraformModuleCall:
    name: str
    source: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["module"] = field(default="module", init=False)


@dataclass
class TerraformData:
    type: str
    name: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["data"] = field(default="data", init=False)


@dataclass
class TerraformProvider:
    name: str
    attributes: Attributes
    references: list[Reference]
    kind: Literal["provider"] = field(default="provider", init=False)


TerraformDeclaration = (
    TerraformResource
    | TerraformVariable
    | TerraformOutput
    | TerraformModuleCall
    | TerraformData
    | TerraformProvider
)


class TerraformFile:
    path: str
    declarations: list[TerraformDeclaration]

    def __init__(self, path: str):
        self.path = path
        with open(path) as f:
            tree = hcl2.parse(f)
        self.declarations = [
            decl for child in tree.body.children if isinstance(child, BlockRule) for decl in self._parse_block(child)
        ]

    def _parse_block(self, block: BlockRule) -> list[TerraformDeclaration]:
        labels = block.labels
        kind = _literal_string(labels[0])
        names = [_literal_string(label) or "" for label in labels[1:]]
        attributes, references = _walk_body(block.body)

        if kind == "resource" and len(names) >= 2:
            return [TerraformResource(type=names[0], name=names[1], attributes=attributes, references=references)]
        if kind == "data" and len(names) >= 2:
            return [TerraformData(type=names[0], name=names[1], attributes=attributes, references=references)]
        if kind == "variable" and len(names) >= 1:
            return [TerraformVariable(name=names[0], attributes=attributes, references=references)]
        if kind == "output" and len(names) >= 1:
            return [TerraformOutput(name=names[0], attributes=attributes, references=references)]
        if kind == "provider" and len(names) >= 1:
            return [TerraformProvider(name=names[0], attributes=attributes, references=references)]
        if kind == "module" and len(names) >= 1:
            source_attr = next(
                (c for c in block.body.children if isinstance(c, AttributeRule) and str(c.identifier.token.value) == "source"),
                None,
            )
            source = (_literal_string(source_attr.expression) if source_attr is not None else None) or ""
            return [
                TerraformModuleCall(name=names[0], source=source, attributes=attributes, references=references)
            ]
        return []


class TerraformModule:
    path: str
    files: list[TerraformFile]
    declarations: list[TerraformDeclaration]

    def __init__(self, path: str):
        self.path = path
        self.files = self._load_files()
        self.declarations = [d for f in self.files for d in f.declarations]

    def _load_files(self) -> list[TerraformFile]:
        return [
            TerraformFile(entry.path)
            for entry in scandir(self.path)
            if entry.is_file() and entry.name.endswith(".tf")
        ]

    def __str__(self) -> str:
        resources = [d for d in self.declarations if isinstance(d, TerraformResource)]
        variables = [d for d in self.declarations if isinstance(d, TerraformVariable)]
        outputs = [d for d in self.declarations if isinstance(d, TerraformOutput)]
        module_calls = [d for d in self.declarations if isinstance(d, TerraformModuleCall)]
        data_sources = [d for d in self.declarations if isinstance(d, TerraformData)]
        providers = [d for d in self.declarations if isinstance(d, TerraformProvider)]

        lines = [f"TerraformModule({self.path})"]
        if resources:
            lines.append(f"  resources:    {[f'{r.type}.{r.name}' for r in resources]}")
        if variables:
            lines.append(f"  variables:    {[v.name for v in variables]}")
        if outputs:
            lines.append(f"  outputs:      {[o.name for o in outputs]}")
        if module_calls:
            lines.append(f"  module_calls: {[m.name for m in module_calls]}")
        if data_sources:
            lines.append(f"  data_sources: {[f'{d.type}.{d.name}' for d in data_sources]}")
        if providers:
            lines.append(f"  providers:    {[p.name for p in providers]}")
        return "\n".join(lines)


@dataclass
class ModuleInstance:
    """One call-site instantiation of a module. Distinct instantiations of the same
    physical module share the same parsed `module` content but occupy different
    positions in the call tree, since each instantiation gets its own global names."""
    call_chain: tuple[str, ...]
    module: TerraformModule
    children: dict[str, "ModuleInstance"] = field(default_factory=dict)


class TerraformProject:
    modules: dict[str, TerraformModule]  # abs path -> parsed content, parsed once per path
    root: ModuleInstance                  # call tree, one node per instantiation

    def __init__(self, main_module_path: str):
        self.modules = {}
        self.root = self._instantiate((), str(Path(main_module_path).resolve()), frozenset())

    def _load_content(self, abs_path: str) -> TerraformModule:
        if abs_path not in self.modules:
            self.modules[abs_path] = TerraformModule(abs_path)
        return self.modules[abs_path]

    def _instantiate(
        self, call_chain: tuple[str, ...], abs_path: str, ancestry: frozenset[str]
    ) -> ModuleInstance:
        if abs_path in ancestry:
            raise ValueError(f"Cycle in module dependencies: {' -> '.join((*ancestry, abs_path))}")
        module = self._load_content(abs_path)
        ancestry = ancestry | {abs_path}
        children: dict[str, ModuleInstance] = {}
        for decl in module.declarations:
            if isinstance(decl, TerraformModuleCall) and self._is_local_source(decl.source):
                child_path = str((Path(abs_path) / decl.source).resolve())
                children[decl.name] = self._instantiate(call_chain + (decl.name,), child_path, ancestry)
        return ModuleInstance(call_chain=call_chain, module=module, children=children)

    @staticmethod
    def _is_local_source(source: str) -> bool:
        return source.startswith("./") or source.startswith("../")

    def __str__(self) -> str:
        lines = ["TerraformProject"]

        def walk(instance: ModuleInstance) -> None:
            label = ".".join(f"module.{n}" for n in instance.call_chain) or "<root>"
            lines.append(f"-- {label} --")
            lines.append(str(instance.module))
            for child in instance.children.values():
                walk(child)

        walk(self.root)
        return "\n".join(lines)
