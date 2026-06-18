'''
@Author ：suke
@Version ：1.1
@Date ：2026-06-16 01:56:00
@Description：FastAPI 路由 — POST /api/analyze 接收 zip/tar.gz 上传，解压
              （带 zip/tar slip + symlink + 解压炸弹 + 成员数上限防护）后跑 pipeline，
              pipeline 在 executor 中跑并用 asyncio.wait_for 包 900s 超时（spec §6），
              落库到 RunStore 并返回 PipelineRunResult。GET /api/runs、/api/runs/{id}、
              /api/runs/{id}/graph 通过 app.state 注入 store / uploads_root。
'''
from __future__ import annotations

import asyncio
import io
import logging
from typing import Any
import shutil
import tarfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from pyknp.model.function import FunctionNode
from pyknp.model.graph_payload import GraphPayload
from pyknp.model.run import PipelineRunResult, RunSummary
from pyknp.model.tag import Tag
from pyknp.pipeline.orchestrator import run_pipeline
from pyknp.storage.run_store import RunStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pyknp"])

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB（spec §5）
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB 解压后总字节上限（防 zip 炸弹）
MAX_EXTRACTED_FILES = 100_000  # 成员数上限
PIPELINE_TIMEOUT_SECONDS = 900  # spec §6 的 900s


class _ArchiveLimitExceeded(HTTPException):
    """解压过程命中 DoS 上限，转 HTTP 400。"""


def _is_within(child: Path, parent: Path) -> bool:
    """判断 child 路径是否在 parent 内（含等于 parent 自身）。"""
    try:
        child.relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    """防 zip slip + symlink + 解压炸弹。"""
    dest_resolved = dest.resolve()
    members = zf.infolist()
    if len(members) > MAX_EXTRACTED_FILES:
        raise _ArchiveLimitExceeded(
            status_code=400,
            detail=f"archive has {len(members)} members; max {MAX_EXTRACTED_FILES}",
        )
    total_uncompressed = 0
    for member in members:
        if member.is_dir():
            continue
        # symlink 逃逸防护（external_attr 高 16 位为 Unix mode，0o120000 = S_IFLNK）
        if ((getattr(member, "external_attr", 0) >> 16) & 0o170000) == 0o120000:
            raise _ArchiveLimitExceeded(
                status_code=400, detail="symlink members are not allowed",
            )
        total_uncompressed += member.file_size
        if total_uncompressed > MAX_EXTRACTED_BYTES:
            raise _ArchiveLimitExceeded(
                status_code=400,
                detail=f"uncompressed size exceeds {MAX_EXTRACTED_BYTES} bytes",
            )
        target = (dest / member.filename).resolve()
        if not _is_within(target, dest_resolved):
            raise _ArchiveLimitExceeded(status_code=400, detail="zip slip detected")
    zf.extractall(dest)


def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    """防 tar slip + symlink + 解压炸弹；显式 filter='data'（3.14 默认）。"""
    dest_resolved = dest.resolve()
    members = tf.getmembers()
    if len(members) > MAX_EXTRACTED_FILES:
        raise _ArchiveLimitExceeded(
            status_code=400,
            detail=f"archive has {len(members)} members; max {MAX_EXTRACTED_FILES}",
        )
    total_uncompressed = 0
    for member in members:
        if member.issym() or member.islnk():
            raise _ArchiveLimitExceeded(
                status_code=400, detail="symlink/hardlink members are not allowed",
            )
        if member.isreg():
            total_uncompressed += member.size
            if total_uncompressed > MAX_EXTRACTED_BYTES:
                raise _ArchiveLimitExceeded(
                    status_code=400,
                    detail=f"uncompressed size exceeds {MAX_EXTRACTED_BYTES} bytes",
                )
        target = (dest / member.name).resolve()
        if not _is_within(target, dest_resolved):
            raise _ArchiveLimitExceeded(status_code=400, detail="tar slip detected")
    # filter="data" 自 3.12 起支持；3.14 起为默认。拒绝 device/pipe/absolute/symlink 成员。
    tf.extractall(dest, filter="data") if hasattr(tarfile, "data_filter") else tf.extractall(dest)


def _extract_archive(upload_bytes: bytes, filename: str, dest: Path) -> None:
    """解压到 dest。失败时清理 dest 防泄漏空目录。"""
    try:
        lower = filename.lower()
        if lower.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
                _safe_extract_zip(zf, dest)
        elif lower.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=io.BytesIO(upload_bytes), mode="r:gz") as tf:
                _safe_extract_tar(tf, dest)
        elif lower.endswith(".tar"):
            with tarfile.open(fileobj=io.BytesIO(upload_bytes), mode="r:") as tf:
                _safe_extract_tar(tf, dest)
        else:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {filename}")
    except HTTPException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"invalid archive: {exc}") from exc


def _find_project_root(extracted: Path) -> Path:
    """解压后若是单顶层目录，进入该目录；否则用解压根。"""
    children = [c for c in extracted.iterdir() if not c.name.startswith(".")]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extracted


@router.post("/analyze")
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    project_name: str = Query("uploaded"),
) -> dict[str, Any]:
    """上传 → 分析 → 持久化；返回最小元信息（不含完整 PipelineRunResult，前端再走 /graph 拉数据）。

    PipelineRunResult 对大项目可达数 MB，直接返回会让浏览器 resp.json() 卡顿。
    """
    store: RunStore = request.app.state.store
    uploads_root: Path = request.app.state.uploads_root

    upload_bytes = await file.read()
    if len(upload_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload exceeds 500MB limit")

    run_id = uuid.uuid4().hex[:12]
    extract_dir = uploads_root / run_id
    _extract_archive(upload_bytes, file.filename or "upload.zip", extract_dir)
    project_root = _find_project_root(extract_dir)

    py_files = list(project_root.rglob("*.py"))
    if not py_files:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="no python files found in archive")

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: run_pipeline(project_root, project_name=project_name, run_id=run_id),
            ),
            timeout=PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        # spec §6：超时取消并清理 tmpdir（保留 .cancelled 标记）
        (extract_dir / ".cancelled").touch(exist_ok=True)
        logger.warning("pipeline run %s timed out after %ss", run_id, PIPELINE_TIMEOUT_SECONDS)
        raise HTTPException(status_code=408, detail=f"pipeline timed out after {PIPELINE_TIMEOUT_SECONDS}s")
    except Exception as exc:
        logger.exception("pipeline run %s crashed", run_id)
        raise HTTPException(status_code=500, detail=f"pipeline error: {type(exc).__name__}") from exc

    store.write(result)
    # 返回最小响应，避免大 JSON 阻塞浏览器
    return {
        "run_id": result.run_id,
        "status": result.status.value,
        "project_name": result.project_name,
        "total_functions": result.calculation.total_functions,
        "total_edges": result.calculation.total_edges,
        "errors": result.errors,
    }


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(request: Request) -> list[RunSummary]:
    store: RunStore = request.app.state.store
    return store.list()


@router.get("/runs/{run_id}", response_model=PipelineRunResult)
async def get_run(run_id: str, request: Request) -> PipelineRunResult:
    store: RunStore = request.app.state.store
    result = store.read(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return result


@router.get("/runs/{run_id}/graph", response_model=GraphPayload)
async def get_run_graph(run_id: str, request: Request) -> GraphPayload:
    store: RunStore = request.app.state.store
    result = store.read(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return _build_graph_payload(result)


@router.get("/runs/{run_id}/source")
async def get_run_source(
    run_id: str,
    request: Request,
    file: str = Query(..., description="相对 project root 的文件路径"),
    start_line: int = Query(1, ge=1),
    end_line: int = Query(0, ge=0, description="0 表示读到文件末尾"),
) -> dict[str, Any]:
    """返回指定文件的源码片段，前端代码预览面板使用。

    file 路径相对 run 的 project_root；uploads/{run_id}/ 是解压根，
    若单顶层目录则需进入该目录（与 analyze 时的 _find_project_root 一致）。
    """
    store: RunStore = request.app.state.store
    result = store.read(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    uploads_root: Path = request.app.state.uploads_root
    extract_dir = uploads_root / run_id
    if not extract_dir.exists():
        raise HTTPException(status_code=404, detail=f"extraction dir for run {run_id} not found")

    project_root = _find_project_root(extract_dir)
    # 安全：file 不能逃出 project_root
    target = (project_root / file).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError as e:
        raise HTTPException(status_code=400, detail="file path escapes project root") from e
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {file}")

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if end_line <= 0:
        end_line = len(lines)
    snippet = "\n".join(lines[max(start_line - 1, 0):end_line])
    return {
        "run_id": run_id,
        "file": file,
        "start_line": start_line,
        "end_line": end_line,
        "total_lines": len(lines),
        "content": snippet,
    }


def _derive_node_type(fn: FunctionNode, tags: list[Tag]) -> str:
    """根据 qualified_name 嵌套深度 + tag 推断节点类型，前端着色用。"""
    if Tag.PROPERTY in tags:
        return "property"
    if Tag.HTTP_ENDPOINT in tags:
        return "http_endpoint"
    if Tag.FIXTURE in tags:
        return "fixture"
    depth = fn.qualified_name_in_file.count(".")
    if depth == 0:
        return "function"
    if depth == 1:
        return "method"
    return "nested"


def _build_graph_payload(result: PipelineRunResult) -> GraphPayload:
    """从 PipelineRunResult 派生前端友好的 GraphPayload。

    在此处重算 pagerank，让所有节点（不只 top-10）拿到正确尺寸；
    tag_distribution 直接复用 calculation 已有的（按 spec 一致性）。
    """
    import networkx as nx

    from pyknp.model.graph_payload import GraphEdge, GraphNode

    loc_to_fn = {fn.location_id: fn for fn in result.functions if fn.location_id}
    G = nx.DiGraph()
    for loc in loc_to_fn:
        G.add_node(loc)
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for edge in result.edges:
        if edge.callee_location_id is None:
            continue
        G.add_edge(edge.caller_location_id, edge.callee_location_id)
        in_degree[edge.callee_location_id] = in_degree.get(edge.callee_location_id, 0) + 1
        out_degree[edge.caller_location_id] = out_degree.get(edge.caller_location_id, 0) + 1

    pagerank_full: dict[str, float] = (
        nx.pagerank(G, max_iter=200) if G.number_of_nodes() > 0 else {}
    )

    nodes: list[GraphNode] = []
    for loc, fn in loc_to_fn.items():
        tags = [Tag(t) for t in result.propagated_tags.get(loc, [])]
        nodes.append(GraphNode(
            location_id=loc,
            ref_id=fn.ref_id,
            label=fn.qualified_name_in_file.split(".")[-1],
            file=fn.file,
            tags=tags,
            in_degree=in_degree.get(loc, 0),
            out_degree=out_degree.get(loc, 0),
            pagerank=pagerank_full.get(loc, 0.0),
            node_type=_derive_node_type(fn, tags),
            qualified_name_in_file=fn.qualified_name_in_file,
        ))

    edges: list[GraphEdge] = [
        GraphEdge(
            source=edge.caller_location_id,
            target=edge.callee_location_id,
            resolved_via=edge.resolved_via,
        )
        for edge in result.edges
        if edge.callee_location_id is not None
    ]

    tag_dist: dict[Tag, int] = {Tag(t): c for t, c in result.calculation.tag_distribution.items()}

    return GraphPayload(
        run_id=result.run_id,
        nodes=nodes,
        edges=edges,
        tag_distribution=tag_dist,
    )
