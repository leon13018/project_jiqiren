"""共用 pytest fixtures 與 helpers。

L0 BDD/TDD 實作後說明：
    - speak / mute / unmute callback stub 以 inline lambda + list 收集實作（無跨測試共用需求）
    - 若後續 L1-L5 出現跨測試檔共用的 fixture，才搬到此處

設計原則：
    - 所有對外動作（speak / do_action / show）以 callback 注入；
      測試用純函式 lambda 收集呼叫紀錄，不用 mock library
      （見 .claude/skills/test-driven-development/testing-anti-patterns.md）
    - 不 import 任何廠商 SDK（ActionGroupControl / Board）；
      sales/ 業務邏輯嚴格隔離於廠商檔（架構決策 backend-module-structure.md 選項 C）
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_l1_q_confirm_state():
    """每 test 前後 reset L1 q confirm 模組級 state（C14 防殘留）。

    Wave 7b C14 加入「兩次 q 才真退」後，l1.py 用 module-level _q_confirm_pending
    追蹤狀態。pytest 之間若不 reset，前一 test 殘留的 pending=True 會讓下一 test
    的第一次 q 直接退出（行為改變）。此 fixture 確保每 test 起點為 pending=False。
    """
    from myProgram.sales.states import l1
    l1._q_confirm_pending = False
    yield
    l1._q_confirm_pending = False
