'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:56:00
@Description：FastAPI 路由契约测试 — /api/analyze 成功路径与 400 拒绝非 zip。
'''
import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from pyknp.app import create_app


def _make_zip(project_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in project_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(project_dir))
    return buf.getvalue()


def test_analyze_endpoint_returns_run_result(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import requests\n"
        "def fetch(url):\n"
        "    return requests.get(url)\n"
    )

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)

    zip_bytes = _make_zip(tmp_path / "demo")
    resp = client.post(
        "/api/analyze",
        files={"file": ("demo.zip", zip_bytes, "application/zip")},
        params={"project_name": "demo"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # /analyze 现在返回最小响应，完整数据走 /runs/{id} 或 /runs/{id}/graph
    assert body["status"] == "success"
    assert body["project_name"] == "demo"
    assert body["total_functions"] == 1
    assert "run_id" in body

    # 完整数据通过 GET /runs/{id} 拿
    detail = client.get(f"/api/runs/{body['run_id']}").json()
    assert len(detail["functions"]) == 1


def test_analyze_rejects_non_zip(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.post(
        "/api/analyze",
        files={"file": ("foo.txt", b"not a zip", "text/plain")},
        params={"project_name": "foo"},
    )
    assert resp.status_code == 400


def test_runs_list_after_analyze(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)

    zip_bytes = _make_zip(tmp_path / "demo")
    client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")})

    resp = client.get("/api/runs")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert all("run_id" in i for i in items)


def test_run_detail_returns_full_result(tmp_path: Path):
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(): return 1\n")

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    zip_bytes = _make_zip(tmp_path / "demo")
    post_resp = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")})
    run_id = post_resp.json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id


def test_run_detail_404_for_missing(tmp_path: Path):
    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


def test_graph_payload_endpoint(tmp_path: Path):
    from pyknp.model.graph_payload import GraphPayload

    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "import requests\n"
        "def fetch(url):\n"
        "    return requests.get(url)\n"
    )

    app = create_app(data_dir=tmp_path / "data")
    client = TestClient(app)
    zip_bytes = _make_zip(tmp_path / "demo")
    post_resp = client.post("/api/analyze", files={"file": ("demo.zip", zip_bytes, "application/zip")})
    run_id = post_resp.json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/graph")
    assert resp.status_code == 200
    payload = GraphPayload.model_validate(resp.json())
    assert payload.run_id == run_id
    assert len(payload.nodes) >= 1
