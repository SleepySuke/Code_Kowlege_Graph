'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:30:00
@Description：覆盖率补丁测试 — 针对 dev-spec §6 100% line/branch 要求，
              覆盖各模块防御性分支与边界路径（archive 变体、zip/tar slip、
              异常处理、bare-name 规则命中、空图、jedi 未解析等）。
'''
from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from pyknp.app import create_app
from pyknp.model.function import FunctionNode
from pyknp.model.tag import Tag
from pyknp.model.tag_evidence import TagEvidence
from pyknp.pipeline.orchestrator import run_pipeline
from pyknp.rules import RuleContext, RuleRegistry
from pyknp.rules.base import Rule
from pyknp.rules.compute_heavy import ComputeHeavyRule
from pyknp.rules.database import DatabaseRule
from pyknp.rules.filesystem import FilesystemRule
from pyknp.rules.network import NetworkRule
from pyknp.rules.subprocess_rule import SubprocessRule
from pyknp.storage.run_store import RunStore


def _fn(loc: str = "demo/mod.py:1") -> FunctionNode:
    return FunctionNode(
        ref_id="demo.mod.fn", qualified_name_in_file="fn",
        file="demo/mod.py", start_line=1, end_line=2,
        parameters=[], decorators=[], source_hash="abc",
        location_id=loc,
    )


# -------------------- Resource rules: 裸名命中 + 匹配但未调用 --------------------

def test_network_rule_returns_none_when_lib_imported_but_not_called():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"requests"},
        call_expressions=[("other_lib", "get")],
        decorators=[],
        source_text="",
    )
    assert NetworkRule().check(ctx) is None


def test_database_rule_returns_none_when_lib_imported_but_not_called():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"sqlite3"},
        call_expressions=[("other", "x")],
        decorators=[],
        source_text="",
    )
    assert DatabaseRule().check(ctx) is None


def test_database_rule_matches_when_module_called():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"sqlite3"},
        call_expressions=[("sqlite3", "connect")],
        decorators=[],
        source_text="",
    )
    assert DatabaseRule().check(ctx) is not None


def test_filesystem_rule_matches_via_bare_open_call():
    """未导入 FS 库但调用内建 open() → 仍命中 FILESYSTEM。"""
    ctx = RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[(None, "open")],
        decorators=[],
        source_text="",
    )
    ev = FilesystemRule().check(ctx)
    assert ev is not None
    assert "open" in ev.evidence


def test_filesystem_rule_returns_none_when_no_lib_no_bare_call():
    """既无 FS 库也无 open 调用 → None。"""
    ctx = RuleContext(
        function=_fn(),
        module_imports={"other_lib"},
        call_expressions=[(None, "other")],
        decorators=[],
        source_text="",
    )
    assert FilesystemRule().check(ctx) is None


# -------------------- Orchestrator invariants 3 & 4 触发 --------------------


def test_filesystem_rule_returns_none_when_no_call():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"Path"},
        call_expressions=[(None, "other")],
        decorators=[],
        source_text="",
    )
    assert FilesystemRule().check(ctx) is None


def test_compute_heavy_rule_matches_via_bare_np_call():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"np"},
        call_expressions=[(None, "np")],
        decorators=[],
        source_text="",
    )
    assert ComputeHeavyRule().check(ctx) is not None


def test_compute_heavy_rule_returns_none_when_no_call():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"np"},
        call_expressions=[(None, "other")],
        decorators=[],
        source_text="",
    )
    assert ComputeHeavyRule().check(ctx) is None


def test_subprocess_rule_matches_subprocess_run():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"subprocess"},
        call_expressions=[("subprocess", "run")],
        decorators=[],
        source_text="",
    )
    assert SubprocessRule().check(ctx) is not None


def test_subprocess_rule_matches_os_system():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"os"},
        call_expressions=[("os", "system")],
        decorators=[],
        source_text="",
    )
    assert SubprocessRule().check(ctx) is not None


def test_subprocess_rule_returns_none_when_os_imported_but_no_cmd_call():
    ctx = RuleContext(
        function=_fn(),
        module_imports={"os"},
        call_expressions=[("os", "getpid")],
        decorators=[],
        source_text="",
    )
    assert SubprocessRule().check(ctx) is None


# -------------------- RuleRegistry: 单规则异常吞掉 --------------------

class _ExplodingRule(Rule):
    @property
    def id(self) -> str:
        return "test.explode"

    @property
    def tag(self) -> Tag:
        return Tag.NETWORK

    def check(self, ctx: RuleContext) -> TagEvidence | None:
        raise RuntimeError("boom")


def test_registry_run_all_swallows_rule_exception():
    registry = RuleRegistry()
    registry.register(_ExplodingRule())
    results = registry.run_all(RuleContext(
        function=_fn(),
        module_imports=set(),
        call_expressions=[],
        decorators=[],
        source_text="",
    ))
    assert results == []


# -------------------- Storage: 损坏 index.json 兜底 --------------------

def test_run_store_read_index_handles_corrupt_json(tmp_path: Path):
    store = RunStore(tmp_path)
    store.index_path.write_text("not valid json {")
    # 损坏文件应被吞掉，返回空列表
    assert store.list() == []


# -------------------- Orchestrator: 顶层异常 + 空图 pagerank --------------------

def test_orchestrator_propagates_stage_exception_to_failed(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("stage crashed")

    with patch("pyknp.pipeline.orchestrator.ast_run", side_effect=_boom):
        result = run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "failed"
    assert any("stage crashed" in e for e in result.errors)


def test_orchestrator_empty_graph_skips_pagerank(tmp_path: Path):
    # 一个 .py 文件但没有函数定义 → graph 节点为 0，pagerank/betweenness 走空分支
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# only a comment\n")
    (pkg / "mod.py").write_text("X = 1\n")
    result = run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "success"
    assert result.calculation.total_functions == 0


# -------------------- App: GET / 返回 HTML --------------------

def test_app_index_endpoint_returns_html(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "知识图谱" in resp.text


# -------------------- Routes: archive 变体 + slip 防护 + 413 --------------------

def _zip_bytes_with_evil_member() -> bytes:
    """构造一个含 '../escape.py' 路径的 zip，触发 slip 检测。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../escape.py", "print('pwned')\n")
    return buf.getvalue()


def _tar_bytes_with_evil_member(mode: str = "w") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=mode) as tf:
        info = tarfile.TarInfo(name="../escape.py")
        data = b"print('pwned')\n"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_analyze_rejects_zip_slip(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("evil.zip", _zip_bytes_with_evil_member(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "slip" in resp.json()["detail"].lower()


def test_analyze_handles_tar_gz(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path in pkg.rglob("*"):
            if path.is_file():
                info = tarfile.TarInfo(name=str(path.relative_to(pkg)))
                data = path.read_bytes()
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.tar.gz", buf.getvalue(), "application/gzip")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_analyze_handles_plain_tar(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path in pkg.rglob("*"):
            if path.is_file():
                info = tarfile.TarInfo(name=str(path.relative_to(pkg)))
                data = path.read_bytes()
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.tar", buf.getvalue(), "application/x-tar")},
    )
    assert resp.status_code == 200


def test_analyze_rejects_tar_slip(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("evil.tar.gz", _tar_bytes_with_evil_member("w:gz"), "application/gzip")},
    )
    assert resp.status_code == 400
    assert "slip" in resp.json()["detail"].lower()


def test_analyze_rejects_corrupt_zip(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("bad.zip", b"PK\x03\x04corrupt", "application/zip")},
    )
    assert resp.status_code == 400


def test_analyze_rejects_oversized_upload(tmp_path: Path):
    from pyknp.api import routes as routes_module
    big = b"x" * (routes_module.MAX_UPLOAD_BYTES + 1)
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("huge.zip", big, "application/zip")},
    )
    assert resp.status_code == 413


def test_analyze_unwraps_single_top_level_dir(tmp_path: Path):
    """zip 内若只有单个顶层目录，应进入该目录作为 project_root。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    # 构造一个 zip，里面顶层是 demo/，再下面是 __init__.py 和 mod.py
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in pkg.rglob("*"):
            if path.is_file():
                zf.write(path, f"demo/{path.relative_to(pkg)}")
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", buf.getvalue(), "application/zip")},
        params={"project_name": "demo"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_analyze_rejects_archive_without_python_files(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no python here\n")
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("empty.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 422


def test_graph_endpoint_404_for_missing_run(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.get("/api/runs/nonexistent/graph")
    assert resp.status_code == 404


def test_graph_payload_includes_edges(tmp_path: Path):
    """两个模块互相调用 → graph payload 应包含至少一条 edge。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "callee.py").write_text("def helper():\n    return 1\n")
    (pkg / "caller.py").write_text(
        "from .callee import helper\n"
        "\n"
        "def use():\n"
        "    return helper()\n"
    )
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/callee.py": "def helper():\n    return 1\n", "demo/caller.py": "from .callee import helper\n\ndef use():\n    return helper()\n"})
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    graph_resp = client.get(f"/api/runs/{run_id}/graph")
    assert graph_resp.status_code == 200
    payload = graph_resp.json()
    assert len(payload["edges"]) >= 1


def _zip_with_files(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


# -------------------- Filesystem: module-form 命中 --------------------

def test_filesystem_rule_matches_via_module_call():
    """import os; os.getcwd() → module 'os' 命中 _FS_LIBS。"""
    ctx = RuleContext(
        function=_fn(),
        module_imports={"os"},
        call_expressions=[("os", "getcwd")],
        decorators=[],
        source_text="",
    )
    ev = FilesystemRule().check(ctx)
    assert ev is not None
    assert "os" in ev.evidence


# -------------------- Subprocess: 混合调用覆盖 False 分支 --------------------

def test_subprocess_rule_handles_mixed_calls_when_both_imported():
    """import subprocess + os，调用 subprocess.run 与 os.system，再调一个非目标 →
    覆盖 subprocess 循环的 False 分支与 os 循环的 False 分支。"""
    ctx = RuleContext(
        function=_fn(),
        module_imports={"subprocess", "os"},
        call_expressions=[
            ("subprocess", "run"),
            ("os", "system"),
            ("other", "x"),  # 触发两个循环的 False 分支
        ],
        decorators=[],
        source_text="",
    )
    ev = SubprocessRule().check(ctx)
    assert ev is not None
    assert "subprocess" in ev.evidence
    assert "os.system" in ev.evidence


# -------------------- Tagging: 无 location_id 的函数被跳过 --------------------

def test_tagging_skips_function_without_location_id(tmp_path: Path):
    """直接调用 tagging（不走 resolve），functions 的 location_id 为 None → 应被跳过。"""
    from pyknp.pipeline.ast import run as ast_run
    from pyknp.pipeline.tagging import run as tagging_run

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    functions, imports = ast_run(tmp_path)
    # 故意不调用 resolve，functions[*].location_id 全为 None
    direct_tags = tagging_run(tmp_path, functions, imports)
    # 不应崩，且因 location_id 缺失不会有任何条目
    assert direct_tags == {}


def test_tagging_skips_tree_function_not_in_functions_list(tmp_path: Path):
    """传入空 functions 列表，但树里有函数 → line_to_fn 取不到 → 跳过。"""
    from pyknp.pipeline.tagging import run as tagging_run

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    direct_tags = tagging_run(tmp_path, [], {})
    assert direct_tags == {}


# -------------------- Resolve: caller_fn 不在 functions 列表 --------------------

def test_resolve_skips_call_when_caller_not_in_functions(tmp_path: Path):
    """传入不完整的 functions 列表（缺 caller），resolve 应跳过对应 call 而不崩。"""
    from pyknp.pipeline.ast import run as ast_run
    from pyknp.pipeline.resolve import run as resolve_run

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def use():\n    return undefined_thing()\n"
    )

    functions, imports = ast_run(tmp_path)
    # 故意传空 functions，但保留 imports 触发 resolve 内部解析
    edges, _ = resolve_run(tmp_path, [], imports)
    # caller_fn 永远为 None，不会有边
    assert edges == []


# -------------------- App: 缺 frontend 目录时跳过 mount --------------------

def test_app_create_without_frontend_dir(tmp_path: Path, monkeypatch):
    """FRONTEND_DIR 不存在时应跳过 static mount 与 / 路由。"""
    from pyknp import app as app_module
    monkeypatch.setattr(app_module, "FRONTEND_DIR", tmp_path / "nonexistent_frontend")
    app = app_module.create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    # 没有 index 路由 → 404
    resp = client.get("/")
    assert resp.status_code == 404


# -------------------- DoS 防护：解压炸弹 / symlink / 成员数上限 --------------------

def _zip_with_many_files(count: int) -> bytes:
    """构造一个含 count 个小文件的 zip，触发成员数上限。"""
    from pyknp.api import routes as routes_module
    # 临时调小上限让测试可行
    orig = routes_module.MAX_EXTRACTED_FILES
    routes_module.MAX_EXTRACTED_FILES = count + 5  # 让上限触达
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(count + 10):
                zf.writestr(f"f{i}.py", "x = 1\n")
        return buf.getvalue()
    finally:
        routes_module.MAX_EXTRACTED_FILES = orig


def test_analyze_rejects_zip_with_too_many_members(tmp_path: Path):
    from pyknp.api import routes as routes_module
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    # 构造超 limit 的 zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(routes_module.MAX_EXTRACTED_FILES + 5):
            zf.writestr(f"f{i}.py", "x = 1\n")
    resp = client.post(
        "/api/analyze",
        files={"file": ("huge.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "members" in resp.json()["detail"]


def test_analyze_rejects_zip_bomb(tmp_path: Path, monkeypatch):
    """单个高压缩比成员超过 MAX_EXTRACTED_BYTES（用 monkeypatch 调小阈值，避免实际分配 GB 级内存）。"""
    from pyknp.api import routes as routes_module
    monkeypatch.setattr(routes_module, "MAX_EXTRACTED_BYTES", 100)
    huge_content = b"x" * 200
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge.dat", huge_content)
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("bomb.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "uncompressed" in resp.json()["detail"].lower()


def test_analyze_rejects_zip_symlink_member(tmp_path: Path):
    """zip 含 symlink 成员 → 拒收。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # 构造一个 symlink 成员：external_attr 高位 = 0xA000（符号链接）
        info = zipfile.ZipInfo("link.txt")
        info.external_attr = (0o120000 << 16) | 0o777
        zf.writestr(info, "/etc/passwd")
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("link.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "symlink" in resp.json()["detail"].lower()


def test_analyze_rejects_tar_symlink_member(tmp_path: Path):
    """tar 含 symlink 成员 → 拒收。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        info.size = 0
        tf.addfile(info)
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("link.tar.gz", buf.getvalue(), "application/gzip")},
    )
    assert resp.status_code == 400


def test_analyze_rejects_tar_with_too_many_members(tmp_path: Path):
    from pyknp.api import routes as routes_module
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for i in range(routes_module.MAX_EXTRACTED_FILES + 5):
            info = tarfile.TarInfo(name=f"f{i}.py")
            data = b"x = 1\n"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("many.tar.gz", buf.getvalue(), "application/gzip")},
    )
    assert resp.status_code == 400


def test_analyze_rejects_tar_bomb(tmp_path: Path, monkeypatch):
    """tar 的 regular 文件总大小超 MAX_EXTRACTED_BYTES（monkeypatch 调小阈值）。"""
    from pyknp.api import routes as routes_module
    monkeypatch.setattr(routes_module, "MAX_EXTRACTED_BYTES", 100)
    huge = b"x" * 200
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="huge.dat")
        info.size = len(huge)
        tf.addfile(info, io.BytesIO(huge))
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("bomb.tar.gz", buf.getvalue(), "application/gzip")},
    )
    assert resp.status_code == 400


def test_analyze_handles_zip_with_directory_entries(tmp_path: Path):
    """zip 含目录成员 → is_dir() 命中 continue 分支，正常处理。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        dir_info = zipfile.ZipInfo("demo/")
        dir_info.external_attr = 0o040755 << 16  # 目录 mode
        zf.writestr(dir_info, "")
        zf.writestr("demo/__init__.py", "")
        zf.writestr("demo/mod.py", "def f(): return 1\n")
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", buf.getvalue(), "application/zip")},
        params={"project_name": "demo"},
    )
    assert resp.status_code == 200


def test_analyze_handles_tar_with_directory_entries(tmp_path: Path):
    """tar 含目录成员 → isreg() False 分支跳过字节统计。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # 目录成员
        dir_info = tarfile.TarInfo(name="demo/")
        dir_info.type = tarfile.DIRTYPE
        dir_info.mode = 0o755
        tf.addfile(dir_info)
        # 普通文件
        info = tarfile.TarInfo(name="demo/mod.py")
        data = b"def f(): return 1\n"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.tar.gz", buf.getvalue(), "application/gzip")},
        params={"project_name": "demo"},
    )
    assert resp.status_code == 200


# -------------------- Pipeline 408 超时 --------------------

def test_analyze_returns_408_on_pipeline_timeout(tmp_path: Path, monkeypatch):
    """pipeline 超时 → 408，extract_dir 留 .cancelled 标记。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "def f(): return 1\n"})

    from pyknp.api import routes as routes_module

    def _slow_pipeline(*_args, **_kwargs):
        import time
        time.sleep(1.0)

    data_dir = tmp_path / "data"
    monkeypatch.setattr(routes_module, "run_pipeline", _slow_pipeline)
    monkeypatch.setattr(routes_module, "PIPELINE_TIMEOUT_SECONDS", 0.1)

    app = create_app(data_dir=data_dir)
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 408
    # spec §6：超时后 extract_dir 应留 .cancelled 标记
    cancelled_markers = list((data_dir / "uploads").rglob(".cancelled"))
    assert len(cancelled_markers) >= 1


def test_resolve_unresolved_logs_at_debug_and_summary_at_info(tmp_path: Path, caplog):
    """UNRESOLVED 调用走 DEBUG；阶段末尾输出 INFO 汇总（spec §6 日志策略）。"""
    import logging

    from pyknp.pipeline.ast import run as ast_run
    from pyknp.pipeline.resolve import run as resolve_run

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def use():\n"
        "    return undefined_thing()\n"
    )
    functions, imports = ast_run(tmp_path)
    with caplog.at_level(logging.DEBUG, logger="pyknp.pipeline.resolve"):
        resolve_run(tmp_path, functions, imports)
    # UNRESOLVED 走 DEBUG
    assert any("UNRESOLVED" in r.message for r in caplog.records if r.levelno == logging.DEBUG)
    # 末尾有 INFO 汇总
    assert any("resolve stage done" in r.message for r in caplog.records if r.levelno == logging.INFO)


# -------------------- node_type 推断（routes._derive_node_type 全分支）--------------------

def test_derive_node_type_all_branches():
    from pyknp.api.routes import _derive_node_type
    from pyknp.model.function import FunctionNode

    def _fn(qname: str) -> FunctionNode:
        return FunctionNode(
            ref_id="x." + qname, qualified_name_in_file=qname,
            file="x.py", start_line=1, end_line=2, parameters=[], decorators=[],
            source_hash="abc", location_id="x.py:1",
        )

    # 顶层函数
    assert _derive_node_type(_fn("foo"), []) == "function"
    # 方法
    assert _derive_node_type(_fn("Cls.method"), []) == "method"
    # 嵌套
    assert _derive_node_type(_fn("Cls.outer.inner"), []) == "nested"
    # 角色 tag 优先
    assert _derive_node_type(_fn("Cls.x"), [Tag.PROPERTY]) == "property"
    assert _derive_node_type(_fn("handler"), [Tag.HTTP_ENDPOINT]) == "http_endpoint"
    assert _derive_node_type(_fn("fix"), [Tag.FIXTURE]) == "fixture"


# -------------------- orchestrator stage timing 日志 --------------------

def test_orchestrator_logs_stage_timings_on_success(tmp_path: Path, caplog):
    """pipeline 成功跑完应输出包含 'stages:' 的 INFO 汇总。"""
    import logging

    from pyknp.pipeline.orchestrator import run_pipeline

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    with caplog.at_level(logging.INFO, logger="pyknp.pipeline.orchestrator"):
        result = run_pipeline(tmp_path, project_name="demo")

    assert result.status.value == "success"
    assert any(
        "stages:" in r.message and "total=" in r.message
        for r in caplog.records if r.levelno == logging.INFO
    )


# -------------------- /api/runs/{id}/source 端点 --------------------

def test_source_endpoint_returns_file_content(tmp_path: Path):
    """上传后能取到文件源码。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f():\n    return 1\n")

    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "def f():\n    return 1\n"})
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    post_resp = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")})
    run_id = post_resp.json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/source", params={"file": "mod.py"})
    assert resp.status_code == 200
    body = resp.json()
    assert "def f" in body["content"]
    assert body["total_lines"] == 2


def test_source_endpoint_supports_line_range(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("line1\nline2\nline3\nline4\n")

    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "line1\nline2\nline3\nline4\n"})
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    run_id = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")}).json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/source", params={"file": "mod.py", "start_line": 2, "end_line": 3})
    body = resp.json()
    assert body["content"] == "line2\nline3"


def test_source_endpoint_404_for_missing_file(tmp_path: Path):
    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "x = 1\n"})
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    run_id = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")}).json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/source", params={"file": "ghost.py"})
    assert resp.status_code == 404


def test_source_endpoint_400_for_path_escape_attempt(tmp_path: Path):
    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "x = 1\n"})
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    run_id = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")}).json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/source", params={"file": "../../../etc/passwd"})
    assert resp.status_code == 400


def test_source_endpoint_404_for_unknown_run(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.get("/api/runs/nonexistent/source", params={"file": "x.py"})
    assert resp.status_code == 404


def test_source_endpoint_404_when_extraction_dir_missing(tmp_path: Path):
    """run 存在但 extract_dir 被清理过 → 404。"""
    import shutil

    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "x = 1\n"})
    data_dir = tmp_path / "data"
    app = create_app(data_dir=data_dir)
    client = TestClient(app)
    run_id = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")}).json()["run_id"]

    # 手动删除 extract_dir 模拟清理
    shutil.rmtree(data_dir / "uploads" / run_id, ignore_errors=True)

    resp = client.get(f"/api/runs/{run_id}/source", params={"file": "mod.py"})
    assert resp.status_code == 404


def test_analyze_returns_500_on_pipeline_crash(tmp_path: Path, monkeypatch):
    """pipeline 抛非超时异常 → 500。"""
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    zip_bytes = _zip_with_files({"demo/__init__.py": "", "demo/mod.py": "def f(): return 1\n"})

    from pyknp.api import routes as routes_module

    def _boom(*_args, **_kwargs):
        raise RuntimeError("stage crashed")

    monkeypatch.setattr(routes_module, "run_pipeline", _boom)

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 500


# -------------------- Orchestrator invariants 运行时校验 --------------------

def test_orchestrator_invariant_missing_location_id_marks_failed(tmp_path: Path, monkeypatch):
    """invariant 1 触发：functions 含 location_id=None → FAILED。"""
    from pyknp.pipeline import orchestrator

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    def _noop_resolve(*_args, **_kwargs):
        # 故意不回填 location_id，让 functions 保持 None
        return [], {}

    monkeypatch.setattr(orchestrator, "resolve_run", _noop_resolve)
    result = orchestrator.run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "failed"
    assert any("invariant 1" in e for e in result.errors)


def test_orchestrator_invariant_orphan_caller_marks_failed(tmp_path: Path, monkeypatch):
    """invariant 2 触发：edge 的 caller_location_id 不在 functions → FAILED。"""
    from pyknp.model.edge import CallEdge, ResolvedVia
    from pyknp.pipeline import orchestrator

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    def _fake_resolve(*_args, **_kwargs):
        # 故意构造 caller_location_id 不在 functions 列表的边
        return [
            CallEdge(
                caller_location_id="ghost.py:1",
                callee_location_id=None,
                callee_ref_id_attempt="x",
                call_line=1,
                resolved_via=ResolvedVia.UNRESOLVED,
            )
        ], {}
    monkeypatch.setattr(orchestrator, "resolve_run", _fake_resolve)
    result = orchestrator.run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "failed"
    assert any("invariant 2" in e for e in result.errors)


def test_orchestrator_invariant_propagated_subset_marks_failed(tmp_path: Path, monkeypatch):
    """invariant 3 触发：direct_tags 含 propagated_tags 没有的 tag → FAILED。"""
    from pyknp.model.tag_evidence import TagEvidence
    from pyknp.pipeline import orchestrator

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    def _fake_tagging(*_args, **_kwargs):
        # 故意构造 direct_tags 与 propagated_tags 不一致
        return {
            "demo/mod.py:1": [
                TagEvidence(tag=Tag.NETWORK, function_id="demo/mod.py:1", rule_id="x", evidence="e")
            ]
        }

    def _fake_graph(*_args, **_kwargs):
        # graph 阶段故意没把 NETWORK 传给该位置
        import networkx as nx
        G = nx.DiGraph()
        G.add_node("demo/mod.py:1")
        return G, {"demo/mod.py:1": []}

    monkeypatch.setattr(orchestrator, "tagging_run", _fake_tagging)
    monkeypatch.setattr(orchestrator, "graph_run", _fake_graph)
    result = orchestrator.run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "failed"
    assert any("invariant 3" in e for e in result.errors)


def test_orchestrator_invariant_tag_distribution_marks_failed(tmp_path: Path, monkeypatch):
    """invariant 4 触发：tag_distribution 与 propagated_tags 实际计数不符 → FAILED。"""
    from pyknp.model.run import CalculationReport
    from pyknp.pipeline import orchestrator

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    def _fake_calc(*_args, **_kwargs):
        # 故意构造 NETWORK 计数为 5（实际 0）
        return CalculationReport(
            total_functions=1, total_edges=0,
            tag_distribution={Tag.NETWORK: 5}, tag_distribution_pct={},
            in_degree_top10=[], out_degree_top10=[],
            pagerank_top10=[], betweenness_top10=[],
            module_tag_distribution={},
        )

    monkeypatch.setattr(orchestrator, "calc_run", _fake_calc)
    result = orchestrator.run_pipeline(tmp_path, project_name="demo")
    assert result.status.value == "failed"
    assert any("invariant 4" in e for e in result.errors)


# -------------------- Atomic write 异常清理 --------------------

def test_atomic_write_cleans_up_tempfile_on_failure(tmp_path: Path, monkeypatch):
    """os.replace 失败时应清理 tmp 文件并向上抛。"""
    from pyknp.storage import run_store

    target = tmp_path / "out.json"
    # 让 os.replace 抛异常
    def _boom(*_args, **_kwargs):
        raise OSError("simulated")

    monkeypatch.setattr(run_store.os, "replace", _boom)
    import pytest
    with pytest.raises(OSError):
        run_store._atomic_write_json(target, '{"x": 1}')
    # 不应残留 .tmp 文件
    tmps = list(tmp_path.glob("*.tmp"))
    assert not tmps


def test_run_store_write_succeeds_under_normal_conditions(tmp_path: Path):
    """正路 write 应通过 atomic_write_json + flock，正常落盘。"""
    from datetime import datetime, timezone

    from pyknp.model.run import CalculationReport, PipelineRunResult, RunStatus

    store = RunStore(tmp_path)
    result = PipelineRunResult(
        run_id="normal",
        status=RunStatus.SUCCESS,
        started_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        project_name="demo",
        functions=[], edges=[],
        direct_tags={}, propagated_tags={},
        calculation=CalculationReport(
            total_functions=0, total_edges=0,
            tag_distribution={}, tag_distribution_pct={},
            in_degree_top10=[], out_degree_top10=[],
            pagerank_top10=[], betweenness_top10=[],
            module_tag_distribution={},
        ),
        errors=[],
    )
    store.write(result)
    assert store.read("normal") is not None
