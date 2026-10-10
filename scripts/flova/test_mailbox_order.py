# -*- coding: utf-8 -*-
"""flova_invite.mailbox_order_key 的纯排序测试（无网络、stdlib only）。

从仓库根运行::

    python -c "import sys; sys.path.insert(0, 'scripts/flova'); \
import test_mailbox_order; test_mailbox_order.main()"
"""
from __future__ import annotations

import flova_invite as fi


def _addresses(rows: list[dict]) -> list[str]:
    return [m["address"] for m in sorted(rows, key=fi.mailbox_order_key)]


def main() -> None:
    # 1. 缺失 / None / 空串 / 0 / 非数字（另加负数）全部排在正时间戳之前。
    rows = [
        {"address": "late-1000@outlook.com", "imported_at": 1000},
        {"address": "missing@outlook.com"},  # imported_at 缺失
        {"address": "none@outlook.com", "imported_at": None},
        {"address": "empty@outlook.com", "imported_at": ""},
        {"address": "zero@outlook.com", "imported_at": 0},
        {"address": "non-numeric@outlook.com", "imported_at": "soon"},
        {"address": "negative@outlook.com", "imported_at": -5},
        {"address": "early-500@outlook.com", "imported_at": 500},
    ]
    ordered = _addresses(rows)
    no_time = {
        "missing@outlook.com",
        "none@outlook.com",
        "empty@outlook.com",
        "zero@outlook.com",
        "non-numeric@outlook.com",
        "negative@outlook.com",
    }
    assert set(ordered[: len(no_time)]) == no_time, ordered
    # 2. 两个时间戳：小的（早导入）在前。
    assert ordered[len(no_time):] == [
        "early-500@outlook.com",
        "late-1000@outlook.com",
    ], ordered

    # 3. 时间戳相同：按小写地址升序。
    tied = [
        {"address": "BEE@outlook.com", "imported_at": 700},
        {"address": "apple@outlook.com", "imported_at": 700},
        {"address": "Cherry@outlook.com", "imported_at": 700},
    ]
    assert _addresses(tied) == [
        "apple@outlook.com",
        "BEE@outlook.com",
        "Cherry@outlook.com",
    ]

    # 4. 无导入时间同档也按小写地址升序（顺序稳定）。
    early_batch = [
        {"address": "Z@outlook.com"},
        {"address": "a@outlook.com", "imported_at": None},
        {"address": "M@outlook.com", "imported_at": 0},
    ]
    assert _addresses(early_batch) == [
        "a@outlook.com",
        "M@outlook.com",
        "Z@outlook.com",
    ]

    print("test_mailbox_order: OK")


if __name__ == "__main__":
    main()
