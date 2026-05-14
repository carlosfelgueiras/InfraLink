import pytest
from src.parser import extract_references


@pytest.mark.parametrize("expr, expected", [
    ("${aws_vpc.main.id}",           [["aws_vpc", "main", "id"]]),
    ("${var.vpc_id}",                [["var", "vpc_id"]]),
    ("${module.dependency.output}",  [["module", "dependency", "output"]]),
    ("${data.aws_ami.example.id}",   [["data", "aws_ami", "example", "id"]]),
    ('"10.0.0.0/16"',                []),
    ("aws_vpc.main.id",              []),
    ("${substr(var.name, 0, 5)}",    [["var", "name"]]),
    ("${var.a || var.b}",            [["var", "a"], ["var", "b"]]),
])
def test_extract_references(expr, expected):
    assert extract_references(expr) == expected
