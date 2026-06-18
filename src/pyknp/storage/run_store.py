'''
@Author ：suke
@Version ：1.1
@Date ：2026-06-16 01:54:00
@Description：RunStore — 把 PipelineRunResult 落到 data/runs/{run_id}.json，
              把 RunSummary 列表维护到 data/index.json（按 started_at 倒序）。
              index.json / run 文件均通过 tempfile + os.replace 原子替换；
              并发写经 fcntl.flock 串行化（防 lost-update）。
'''
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List

from pyknp.model.run import PipelineRunResult, RunSummary

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows 无 fcntl
    _HAS_FCNTL = False


def _atomic_write_json(path: Path, payload: str) -> None:
    """tempfile 写入再 os.replace，确保文件要么完整要么不动。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:  # pragma: no cover — tmp 文件已被清理或权限不足
            pass
        raise


class RunStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.runs_dir = data_dir / "runs"
        self.index_path = data_dir / "index.json"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("[]")

    def write(self, result: PipelineRunResult) -> None:
        run_file = self.runs_dir / f"{result.run_id}.json"
        _atomic_write_json(run_file, result.model_dump_json(indent=2))

        summary = RunSummary(
            run_id=result.run_id,
            project_name=result.project_name,
            status=result.status,
            started_at=result.started_at,
            total_functions=result.calculation.total_functions,
            total_edges=result.calculation.total_edges,
        )
        summaries = self._read_index()
        summaries = [s for s in summaries if s.run_id != result.run_id]
        summaries.append(summary)
        summaries.sort(key=lambda s: s.started_at, reverse=True)
        data = [s.model_dump(mode="json") for s in summaries]
        # 对 index.json 加文件锁防并发 RMW；POSIX 上 fcntl，Windows 无 fcntl 跳过。
        if _HAS_FCNTL:
            with self.index_path.open("a+") as lockf:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
                _atomic_write_json(self.index_path, json.dumps(data, indent=2, default=str))
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover — Windows-only 分支
            _atomic_write_json(self.index_path, json.dumps(data, indent=2, default=str))

    def read(self, run_id: str) -> PipelineRunResult | None:
        run_file = self.runs_dir / f"{run_id}.json"
        if not run_file.exists():
            return None
        return PipelineRunResult.model_validate_json(run_file.read_text())

    def list(self) -> List[RunSummary]:
        return self._read_index()

    def _read_index(self) -> List[RunSummary]:
        try:
            data = json.loads(self.index_path.read_text())
            return [RunSummary.model_validate(item) for item in data]
        except Exception:
            return []
