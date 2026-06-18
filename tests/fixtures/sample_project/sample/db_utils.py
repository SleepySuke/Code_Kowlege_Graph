'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 DATABASE tag 的样例 — import sqlite3 并调用。
'''
import sqlite3


def query_user(uid):
    """DATABASE tag — calls sqlite3.connect."""
    conn = sqlite3.connect(":memory:")
    return conn.execute("SELECT 1").fetchone()
