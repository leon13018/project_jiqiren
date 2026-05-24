"""tests/spec/ — BDD 階段產出（按 L 層組織）。

對應 resources/plans/業務程式邏輯規劃/L0-L5.md 的規格書結構。
每個檔案內容只包含 Gherkin 格式注解 + 空函式（pass），無實際斷言。
TDD 階段（subagent）會把這些 scenarios 搬到 tests/sales/ 並補實作。

詳細流程：.claude/rules/bdd-tdd-workflow.md
"""
