"""共用 pytest fixtures 與 helpers。

L0 BDD/TDD 實作後說明：
    - FakeScheduler stub 放在 tests/sales/test_states.py（單一檔內使用，不需跨檔共用）
    - speak / mute / unmute callback stub 以 inline lambda + list 收集實作（無跨測試共用需求）
    - 若後續 L1-L5 出現跨測試檔共用的 fixture，才搬到此處

設計原則：
    - 所有對外動作（speak / do_action / show）以 callback 注入；
      測試用純函式 lambda 收集呼叫紀錄，不用 mock library
      （見 .claude/skills/test-driven-development/testing-anti-patterns.md）
    - 不 import 任何廠商 SDK（ActionGroupControl / Board）；
      sales/ 業務邏輯嚴格隔離於廠商檔（架構決策 backend-module-structure.md 選項 C）
"""
