'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：触发 FIXTURE tag 的样例 — pytest.fixture 装饰器。
'''
import pytest


@pytest.fixture
def sample_data():
    """FIXTURE tag — decorated with @pytest.fixture."""
    return [1, 2, 3]


def test_sample(sample_data):
    assert len(sample_data) == 3
