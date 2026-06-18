'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 SUBPROCESS tag 的样例 — 调用 subprocess.run。
'''
import subprocess


def run_cmd(cmd):
    """SUBPROCESS tag — calls subprocess.run."""
    return subprocess.run(cmd, capture_output=True)
