'''
@Author ：suke
@Version ：1.0
@Date ：2026-06-16 02:00:00
@Description：sample 项目入口 — 调用所有 utils，期望 5 类资源 tag 通过
              正向传播全部出现在 handle_request 上。
'''
from sample.db_utils import query_user
from sample.fs_utils import read_config
from sample.math_utils import compute_matrix
from sample.net_utils import fetch
from sample.proc_utils import run_cmd
from sample.re_export import fetch_url


def handle_request(url, uid, config_path, cmd, data):
    """Entry point — calls all utils, expects all resource tags via propagation."""
    fetch(url)
    fetch_url(url)
    query_user(uid)
    read_config(config_path)
    run_cmd(cmd)
    compute_matrix(data)
