"""意圖識別（S1 v2）— 純函式，可單獨單測。

職責：
    - 6 步判定優先序（規格書 L0「關鍵字白名單」段）
    - 商品名 + 數量解析
    - 各層共用的 classify_intent 純函式

設計原則：
    - 無 IO、無 print、無副作用
    - 輸入字串 → 輸出意圖物件（dataclass / dict）
    - 最適合 BDD/TDD 切入點（純輸入輸出，無需 mock）
"""

# TODO: S1 v2 實作（待 BDD/TDD 規劃完成後動手）
