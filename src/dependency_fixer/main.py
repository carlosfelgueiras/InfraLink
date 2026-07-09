from .parser import TerraformProject
from .graph import DependencyGraph, to_dot

def main() -> None:
    mod = TerraformProject("example")
    print(to_dot(DependencyGraph(mod)))


if __name__ == "__main__":
    main()
