'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 01:04:00
@Description：pytest 共享夹具 — 提供 fixture_project_root 与 --update-golden 选项。
'''
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixture_project_root() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_project"


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Refresh golden regression snapshots",
    )
