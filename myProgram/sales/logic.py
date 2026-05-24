"""業務邏輯主控（S1 v2）。

職責：
    - 5 層狀態機主迴圈（L1 模式選擇 → L2 詢問需求 → L3 加單迴圈 → L4 結帳 → L5 致謝）
    - 層間 dispatch / context 管理
    - 對應規格書：resources/plans/業務程式邏輯規劃/

設計約束：
    - 純單線程，無 threading / queue / 旗號（incremental-rebuild S1 階段）
    - 無語音 / 無動作 / 無 UI；對外動作以 callback 注入，方便 S2-S7 替換實作
    - 唯一允許持有「外部世界」的進入點 — 其他模組保持純函式 / 純資料
"""

# TODO: S1 v2 實作（待 BDD/TDD 規劃完成後動手）
