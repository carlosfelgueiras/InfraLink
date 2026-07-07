from os import scandir
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Literal, cast
import re
import hcl2

Expression = str
Config = dict[str, Expression | list[Expression] | bool]


_INTERP_PATTERN = re.compile(r'\$\{([^}]+)\}')
_REF_PATTERN = re.compile(r'\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)')


def extract_references(expr: Expression) -> list[list[str]]:
    refs: list[list[str]] = []
    for interp in cast(list[str], _INTERP_PATTERN.findall(expr)):
        refs.extend(m.split(".") for m in cast(list[str], _REF_PATTERN.findall(interp)))
    return refs


def _unquote(s: str) -> str:
    """Strip surrounding HCL double-quotes from a label or string literal."""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


@dataclass
class TerraformResource:
    type: str
    name: str
    config: Config
    kind: Literal["resource"] = field(default="resource", init=False)


@dataclass
class TerraformVariable:
    name: str
    config: Config
    kind: Literal["variable"] = field(default="variable", init=False)


@dataclass
class TerraformOutput:
    name: str
    config: Config
    kind: Literal["output"] = field(default="output", init=False)


@dataclass
class TerraformModuleCall:
    name: str
    source: str
    config: Config
    kind: Literal["module"] = field(default="module", init=False)


@dataclass
class TerraformData:
    type: str
    name: str
    config: Config
    kind: Literal["data"] = field(default="data", init=False)


@dataclass
class TerraformProvider:
    name: str
    config: Config
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
            raw: dict[str, Any] = hcl2.load(f)
        self.declarations = (
            self._parse_resources(raw.get("resource", []))
            + self._parse_variables(raw.get("variable", []))
            + self._parse_outputs(raw.get("output", []))
            + self._parse_module_calls(raw.get("module", []))
            + self._parse_data(raw.get("data", []))
            + self._parse_providers(raw.get("provider", []))
        )

    def _parse_resources(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for rtype, instances in block.items():
                for rname, config in instances.items():
                    result.append(TerraformResource(type=_unquote(rtype), name=_unquote(rname), config=config))
        return result

    def _parse_variables(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for name, config in block.items():
                result.append(TerraformVariable(name=_unquote(name), config=config))
        return result

    def _parse_outputs(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for name, config in block.items():
                result.append(TerraformOutput(name=_unquote(name), config=config))
        return result

    def _parse_module_calls(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for name, config in block.items():
                source = _unquote(cast(str, config.get("source", "")))
                result.append(TerraformModuleCall(name=_unquote(name), source=source, config=config))
        return result

    def _parse_data(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for dtype, instances in block.items():
                for dname, config in instances.items():
                    result.append(TerraformData(type=_unquote(dtype), name=_unquote(dname), config=config))
        return result

    def _parse_providers(self, raw: list[Any]) -> list[TerraformDeclaration]:
        result: list[TerraformDeclaration] = []
        for block in raw:
            for name, config in block.items():
                result.append(TerraformProvider(name=_unquote(name), config=config))
        return result


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
