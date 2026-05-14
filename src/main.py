from src.parser import TerraformProject


def main() -> None:
    mod = TerraformProject("../ie-laas")
    print(mod)


if __name__ == "__main__":
    main()
