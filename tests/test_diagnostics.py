import shutil
import tempfile
from pathlib import Path

import pytest

from dependency_fixer.checks import RedundantDependsOnCheck
from dependency_fixer.diagnostics import AnalysisContext, DataDependencyFix, Diagnostic, run_diagnostics
from dependency_fixer.graph import DependencyGraph
from dependency_fixer.parser import TerraformProject


def _write_project(files: dict[str, str]) -> str:
    root = tempfile.mkdtemp()
    for name, content in files.items():
        Path(root, name).write_text(content)
    return root


def _diagnostics(root: str) -> tuple[Diagnostic, ...]:
    project = TerraformProject(root)
    graph = DependencyGraph(project)
    context = AnalysisContext(project=project, graph=graph)
    return run_diagnostics(context, [RedundantDependsOnCheck()])


def test_redundant_depends_on_detected() -> None:
    root = _write_project({
        "main.tf": '''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
}

resource "aws_instance" "example" {
  subnet_id  = aws_subnet.public.id
  depends_on = [aws_vpc.main]
}
''',
    })
    try:
        diagnostics = _diagnostics(root)
    finally:
        shutil.rmtree(root)

    assert len(diagnostics) == 1
    assert diagnostics[0].category == "redundant"
    assert diagnostics[0].node == ":resource.aws_instance.example"
    assert diagnostics[0].target == ":resource.aws_vpc.main"
    assert diagnostics[0].fix is None
    assert diagnostics[0].origin == "redundant-depends-on-check"


def test_non_redundant_depends_on_not_flagged() -> None:
    root = _write_project({
        "main.tf": '''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_instance" "example" {
  depends_on = [aws_vpc.main]
}
''',
    })
    try:
        diagnostics = _diagnostics(root)
    finally:
        shutil.rmtree(root)

    assert diagnostics == ()


def test_missing_diagnostic_accepts_a_data_dependency_fix() -> None:
    Diagnostic(
        category="missing",
        severity="error",
        message="node should depend on target",
        node=":resource.aws_instance.example",
        target=":resource.aws_db_instance.main",
        fix=DataDependencyFix(field="db_address", expression="aws_db_instance.main.address"),
    )


def test_fix_rejected_on_a_non_missing_diagnostic() -> None:
    with pytest.raises(ValueError, match="fix"):
        Diagnostic(
            category="redundant",
            severity="warning",
            message="not applicable",
            node=":resource.aws_instance.example",
            target=":resource.aws_vpc.main",
            fix=DataDependencyFix(field="db_address", expression="aws_db_instance.main.address"),
        )
