'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 FILESYSTEM tag 的样例 — 使用 pathlib。
'''
from pathlib import Path


def read_config(path):
    """FILESYSTEM tag — uses pathlib."""
    return Path(path).read_text()
