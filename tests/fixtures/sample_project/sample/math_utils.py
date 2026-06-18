'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 COMPUTE_HEAVY tag 的样例 — 使用 numpy。
'''
import numpy as np


def compute_matrix(data):
    """COMPUTE_HEAVY tag — uses numpy."""
    return np.array(data).sum()
