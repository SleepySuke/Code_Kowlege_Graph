'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 NETWORK tag 的样例 — import requests 并调用。
'''
import requests


def fetch(url):
    """NETWORK tag — calls requests.get."""
    return requests.get(url)
