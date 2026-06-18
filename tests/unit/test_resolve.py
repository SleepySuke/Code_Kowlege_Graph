'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:36:00
@Description：resolve 阶段契约测试 — 覆盖 import 快速通道命中与 unresolved 标记。
'''
from pathlib import Path

from pyknp.model.edge import ResolvedVia
from pyknp.pipeline.ast import run as ast_run
from pyknp.pipeline.resolve import run as resolve_run


def test_resolve_import_fast_path(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "callee.py").write_text(
        "def helper():\n"
        "    return 1\n"
    )
    (pkg / "caller.py").write_text(
        "from .callee import helper\n"
        "\n"
        "def use():\n"
        "    return helper()\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, location_map = resolve_run(tmp_path, functions, imports)

    # All functions should have location_id filled
    assert all(fn.location_id is not None for fn in functions)

    # At least one edge from caller.use to callee.helper
    caller = next(f for f in functions if f.ref_id == "demo.caller.use")
    callee = next(f for f in functions if f.ref_id == "demo.callee.helper")

    matching = [e for e in edges if e.caller_location_id == caller.location_id]
    assert len(matching) >= 1
    edge = matching[0]
    assert edge.callee_location_id == callee.location_id
    assert edge.resolved_via in {ResolvedVia.IMPORT_FAST_PATH, ResolvedVia.JEDI_GOTO}


def test_resolve_unresolved_callee_marked(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def use():\n"
        "    return undefined_thing()\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)

    unresolved = [e for e in edges if e.resolved_via == ResolvedVia.UNRESOLVED]
    assert len(unresolved) >= 1
    assert unresolved[0].callee_location_id is None


def test_resolve_jedi_goto_for_dotted_call(tmp_path: Path):
    """dotted call（如 mod.foo()）跳过 fast path，走 jedi goto 解析。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "callee.py").write_text("def foo():\n    return 1\n")
    (pkg / "caller.py").write_text(
        "import demo.callee as callee\n"
        "\n"
        "def use():\n"
        "    return callee.foo()\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, location_map = resolve_run(tmp_path, functions, imports)

    caller = next(f for f in functions if f.ref_id == "demo.caller.use")
    callee = next(f for f in functions if f.ref_id == "demo.callee.foo")
    matching = [e for e in edges if e.caller_location_id == caller.location_id]
    assert matching
    # 应该有边指向 callee.foo
    assert any(e.callee_location_id == callee.location_id for e in matching)


def test_resolve_builtin_call_does_not_crash(tmp_path: Path):
    """调用内置函数（如 print）时 module_path 可能为 None，应被跳过而非崩。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def use():\n"
        "    print('hello')\n"
    )

    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)
    # print 解析为内置，不会落到我们的 functions；预期 unresolved 或不影响
    assert all(e.caller_location_id for e in edges)


def test_resolve_jedi_resolves_to_external_function_no_match(tmp_path: Path):
    """jedi 解析到 stdlib 函数（如 os.getcwd），但我们的 functions 没有它 →
    落入 by_last_segment 循环的 False 分支，最终 UNRESOLVED。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import os\n"
        "def use():\n"
        "    return os.getcwd()\n"
    )
    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)
    # os.getcwd 解析成功但不在我们的项目里 → UNRESOLVED
    unresolved = [e for e in edges if e.resolved_via == ResolvedVia.UNRESOLVED]
    assert any(e.callee_ref_id_attempt == "os.getcwd" for e in unresolved)


def test_resolve_skips_caller_fn_when_functions_list_mismatched(tmp_path: Path):
    """functions 列表的 start_line 与树不一致时，caller_fn 拿不到 → 跳过 call。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def use():\n"
        "    return some_call()\n"
    )
    functions, imports = ast_run(tmp_path)
    # 故意篡改 start_line 让 line_to_fn 取不到
    for fn in functions:
        fn.start_line = 999
    edges, _ = resolve_run(tmp_path, functions, imports)
    assert edges == []


def test_resolve_jedi_returns_def_but_no_location_match(tmp_path: Path):
    """项目里有同名函数 getcwd，调用 os.getcwd 时 jedi 指向 stdlib 而非项目 →
    by_last_segment 循环走 False 分支，最终 UNRESOLVED。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import os\n"
        "\n"
        "def getcwd():\n"
        "    return 'mine'\n"
        "\n"
        "def use():\n"
        "    return os.getcwd()\n"
    )
    functions, imports = ast_run(tmp_path)
    edges, _ = resolve_run(tmp_path, functions, imports)
    # os.getcwd 指向 stdlib，与项目的 demo.mod.getcwd 不匹配 → UNRESOLVED
    os_calls = [e for e in edges if e.callee_ref_id_attempt == "os.getcwd"]
    assert os_calls
    assert all(e.resolved_via == ResolvedVia.UNRESOLVED for e in os_calls)
