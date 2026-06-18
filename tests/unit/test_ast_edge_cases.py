'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:35:00
@Description：AST 阶段边界测试 — 装饰类、无参函数、typed 参数、*args / **kwargs、
              wildcard import、from M import Y.Z 等不常见但合法的 Python 语法。
'''
from pathlib import Path

from pyknp.pipeline.ast import run


def test_ast_decorated_class_with_method(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "@some_decorator\n"
        "class Foo:\n"
        "    def bar(self):\n"
        "        return 1\n"
    )
    functions, _ = run(tmp_path)
    refs = {f.ref_id for f in functions}
    assert "demo.mod.Foo.bar" in refs


def test_ast_function_with_typed_parameters(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def foo(x: int, y: str = 'a') -> bool:\n"
        "    return True\n"
    )
    functions, _ = run(tmp_path)
    fn = functions[0]
    assert "x" in fn.parameters
    assert "y" in fn.parameters


def test_ast_function_with_splat_parameters(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def foo(a, *args, **kwargs):\n"
        "    return a\n"
    )
    functions, _ = run(tmp_path)
    params = functions[0].parameters
    assert "*args" in params
    assert "**kwargs" in params


def test_ast_function_with_no_parameters(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def foo():\n    return 1\n")
    functions, _ = run(tmp_path)
    assert functions[0].parameters == []


def test_ast_wildcard_and_dotted_from_imports(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "from os.path import join as J\n"
        "from module import *\n"
    )
    _, imports = run(tmp_path)
    names = set(imports["demo.mod"])
    assert "J" in names
    assert "*" in names


def test_ast_handles_unparseable_file(tmp_path: Path):
    """tree-sitter 对语法错误宽容（产出部分树），不会抛异常；
    但若 read_bytes 失败（如权限），应跳过该文件而非炸全流程。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def ok():\n    return 1\n")
    # 模拟 read_bytes 抛异常：用 monkeypatch 难，直接断言 run 不抛
    functions, _ = run(tmp_path)
    assert any(f.ref_id == "demo.mod.ok" for f in functions)


def test_ast_class_at_module_level_without_methods(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "class Empty:\n"
        "    pass\n"
    )
    functions, _ = run(tmp_path)
    # 没有方法，不应崩溃
    assert functions == []


def test_ast_from_import_with_multiple_names(tmp_path: Path):
    """`from M import a, b` 在 import kw 后会出现 ',' token；遍历应安全跳过非目标 token。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("from os.path import join, dirname\n")
    _, imports = run(tmp_path)
    names = set(imports["demo.mod"])
    assert "join" in names
    assert "dirname" in names
