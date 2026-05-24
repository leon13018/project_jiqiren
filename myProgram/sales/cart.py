"""購物車資料模型（S1 v2）。

職責：
    - Cart 資料結構（商品 → 數量映射）
    - add / remove / total / clear 操作
    - cart 生命週期管理（規格書 L0「cart 生命週期表」）

設計原則：
    - 純資料模型，無 IO
    - 未來上資料庫時，這層介面不變，底層改 Repository Pattern 即可
      （見 resources/architecture/frontend-backend-contract.md）
"""

# TODO: S1 v2 實作（待 BDD/TDD 規劃完成後動手）
