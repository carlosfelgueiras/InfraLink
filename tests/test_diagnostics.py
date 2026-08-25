import shutil
import tempfile
from pathlib import Path

from dependency_fixer.checks import RedundantDependsOnCheck
from dependency_fixer.diagnostics import AnalysisContext, Diagnostic, run_diagnostics
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
    assert diagnostics[0].nodes == (":resource.aws_instance.example", ":resource.aws_vpc.main")


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
