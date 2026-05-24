"""共用 pytest fixtures 與 helpers。

當前為骨架。具體 fixtures（如 make_ctx / 商品 stub / cart 工廠 / speak-stub
記錄器等）會在 L0 BDD/TDD 第一輪 implementation 時加入。

設計原則：
    - 所有對外動作（speak / do_action / show）以 callback 注入；
      測試用純函式 lambda 收集呼叫紀錄，不用 mock library
      （見 .claude/skills/test-driven-development/testing-anti-patterns.md）
    - 不 import 任何廠商 SDK（ActionGroupControl / Board）；
      sales/ 業務邏輯嚴格隔離於廠商檔（架構決策 backend-module-structure.md 選項 C）
"""
