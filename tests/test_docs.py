"""T5: README examples are executed; documented outputs must be real outputs."""
import doctest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_examples():
    res = doctest.testfile(str(ROOT / "README.md"), module_relative=False,
                           optionflags=doctest.NORMALIZE_WHITESPACE)
    assert res.attempted >= 6
    assert res.failed == 0


def test_example_script_runs():
    import runpy
    runpy.run_path(str(ROOT / "example_usage.py"), run_name="__main__")
