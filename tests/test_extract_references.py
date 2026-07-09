import os
import tempfile

import hcl2
import pytest
from hcl2.rules.base import AttributeRule

from dependency_fixer.parser import (
    Reference,
    TerraformDeclaration,
    TerraformFile,
    TerraformModuleCall,
    _references_in,
)


def _expr(text: str) -> object:
    tree = hcl2.parses(f"x = {text}\n")
    attr = next(c for c in tree.body.children if isinstance(c, AttributeRule))
    return attr.expression


@pytest.mark.parametrize("expr, expected", [
    ("aws_vpc.main.id",                          [["aws_vpc", "main", "id"]]),
    ("var.vpc_id",                                [["var", "vpc_id"]]),
    ("module.dependency.output",                  [["module", "dependency", "output"]]),
    ("data.aws_ami.example.id",                   [["data", "aws_ami", "example", "id"]]),
    ('"10.0.0.0/16"',                             []),
    ('"${aws_vpc.main.id}"',                      [["aws_vpc", "main", "id"]]),
    ('"prefix-${var.name}-suffix"',               [["var", "name"]]),
    ("substr(var.name, 0, 5)",                    [["var", "name"]]),
    ("var.a || var.b",                            [["var", "a"], ["var", "b"]]),
    ("aws_instance.foo[0].id",                    [["aws_instance", "foo", "id"]]),
    ("aws_instance.foo[var.idx].id",              [["aws_instance", "foo", "id"], ["var", "idx"]]),
    (
        "var.enabled ? aws_vpc.a.id : aws_vpc.b.id",
        [["var", "enabled"], ["aws_vpc", "a", "id"], ["aws_vpc", "b", "id"]],
    ),
    ("[for s in var.list : s.id]",                [["var", "list"]]),
    ("{for k, v in var.map : k => v.upper}",      [["var", "map"]]),
])
def test_references_in(expr: str, expected: list[Reference]) -> None:
    assert _references_in(_expr(expr)) == expected


def _parse(text: str) -> list[TerraformDeclaration]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return TerraformFile(path).declarations
    finally:
        os.unlink(path)


def test_nested_block_references_are_collected() -> None:
    decls = _parse('''
resource "aws_security_group" "sg" {
  vpc_id = aws_vpc.main.id
  ingress {
    cidr_blocks = [aws_subnet.public.cidr_block]
  }
}
''')
    assert decls[0].references == [["aws_vpc", "main", "id"], ["aws_subnet", "public", "cidr_block"]]


def test_module_source_and_attributes() -> None:
    decls = _parse('''
module "net" {
  source = "./net"
  vpc_id = aws_vpc.main.id
}
''')
    module_call = decls[0]
    assert isinstance(module_call, TerraformModuleCall)
    assert module_call.source == "./net"
    assert module_call.attributes["vpc_id"] == [["aws_vpc", "main", "id"]]


def test_heredoc_interpolation_fallback() -> None:
    decls = _parse('''
resource "aws_instance" "x" {
  user_data = <<-EOT
    name=${var.name}
  EOT
}
''')
    assert decls[0].references == [["var", "name"]]
