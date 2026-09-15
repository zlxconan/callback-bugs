from importlib import import_module


def test_package_is_importable() -> None:
    package = import_module("ops_agent")

    assert package.__name__ == "ops_agent"
