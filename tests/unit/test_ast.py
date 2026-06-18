'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:34:00
@Description：AST 阶段契约测试 — 覆盖顶层函数、类方法、装饰器、import 表
              与别名 / 点号 import 场景。
'''
from pathlib import Path

from pyknp.pipeline.ast import run


def test_ast_extracts_top_level_function(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def foo(x, y):\n"
        "    return x + y\n"
    )

    functions, imports = run(tmp_path)

    assert len(functions) == 1
    fn = functions[0]
    assert fn.ref_id == "demo.mod.foo"
    assert fn.qualified_name_in_file == "foo"
    assert fn.file == "demo/mod.py"
    assert fn.start_line == 1
    assert fn.end_line == 2
    assert fn.parameters == ["x", "y"]
    assert fn.decorators == []
    assert fn.location_id is None
    assert fn.source_hash  # non-empty


def test_ast_extracts_method(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "class Foo:\n"
        "    def bar(self):\n"
        "        return 1\n"
    )

    functions, imports = run(tmp_path)

    assert len(functions) == 1
    fn = functions[0]
    assert fn.ref_id == "demo.mod.Foo.bar"
    assert fn.qualified_name_in_file == "Foo.bar"


def test_ast_captures_decorators(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "@property\n"
        "def x(self):\n"
        "    return 1\n"
    )

    functions, _ = run(tmp_path)
    assert functions[0].decorators == ["property"]


def test_ast_collects_imports(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import requests\n"
        "from . import sibling\n"
        "from .sibling import helper\n"
    )

    _, imports = run(tmp_path)

    assert "demo.mod" in imports
    names = imports["demo.mod"]
    assert "requests" in names
    assert "sibling" in names
    assert "helper" in names


def test_ast_handles_aliased_and_dotted_imports(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import os.path\n"
        "import numpy as np\n"
        "from .sibling import helper as h\n"
    )

    _, imports = run(tmp_path)
    names = set(imports["demo.mod"])

    # `import os.path` → bind "os" (first segment, not "path")
    assert "os" in names
    assert "path" not in names
    # `import numpy as np` → bind "np" (alias)
    assert "np" in names
    # `from .sibling import helper as h` → bind "h" (alias)
    assert "h" in names
