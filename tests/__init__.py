"""tests/ — pytest 測試根目錄。

組織方式：
    - tests/spec/        # BDD 階段產出（按 L 層組織，對應 resources/plans/業務程式邏輯規劃/）
    - tests/sales/       # TDD 階段產出（按模組組織，對應 myProgram/sales/）

子資料夾在各 L 層第一輪 BDD 開始時才建立，避免預先建空殼。
詳細流程：.claude/rules/bdd-tdd-workflow.md
"""
