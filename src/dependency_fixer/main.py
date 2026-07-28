from .parser import TerraformProject
from .graph import DependencyGraph, to_dot
import sys

def main() -> None:
    mod = TerraformProject(sys.argv[1])
    print(to_dot(DependencyGraph(mod)))


if __name__ == "__main__":
    main()
