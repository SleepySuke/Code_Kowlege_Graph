'''
@Author ：suke
@Version ：1.1
@Date ：2026-06-16 02:00:00
@Description：触发 ref_id ≠ location_id 场景 — 通过 alias 调用 net_utils.fetch，
              验证 jedi goto 把 callee 解析到原始 location_id（net_utils.py）
              而非字面文件路径。
'''
from sample.net_utils import fetch as fetch_url  # noqa: F401  # re-export 演示：alias 绑定


def call_via_alias(url):
    """通过 alias 调用 fetch → resolve 应解到 net_utils.fetch 的物理位置。"""
    return fetch_url(url)
