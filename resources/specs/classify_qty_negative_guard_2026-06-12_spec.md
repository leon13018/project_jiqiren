# classify_qty_negative_guard — Mini SDD spec

- **檔**：`myProgram/sales/cart.py:92`（＋`tests/sales/test_cart.py` 檔尾伴隨 1 測試）
- **改前**：
  ```python
    if qty > remaining:
        return "over_limit"
  ```
- **改後**：
  ```python
    if qty < 0 or qty > remaining:
        return "over_limit"
  ```
  docstring `"over_limit"` 行同步改為：`"over_limit" — qty > 剩餘可加量，或 qty < 0（防衛上游異常負數）`
- **伴隨測試**（`test_cart.py` 檔尾，照 CART-CQ 系列格式含 Given/When/Then）：

  ```python
  ## CART-CQ-006
  ### Scenario: 負數 qty → "over_limit"（防衛上游異常，不得誤判 "ok"）
  ### Given 空 cart（remaining > 0）
  ### When classify_qty 收到負數數量
  ### Then 回 "over_limit"（對齊舊 _classify_into_pending else 分支的保守行為）
  def test_classify_qty_negative_is_over_limit() -> None:
      c = new_cart()
      assert cart_module.classify_qty(c, "冰紅茶", -3) == "over_limit"
  ```

- **Why**：反思 `classify-qty-negative-qty-gap` 採納——負數 qty 三分支皆不命中回
  `"ok"`，違反 docstring 契約（`0 < qty`）；reask 路徑會 `del pending` 但
  `add_item` 靜默跳過＝假性 resolved（perf_w3 重構引入的語義回歸，舊 else 分支
  原回 over_limit）。NLU 今日產不出負數（不可達），純防衛性對齊契約；Pass 1 路徑
  負數行為由「靜默跳過＋誤計 added」改為進重問（不可達態的保守化，知情變更）。
- **驗證**：`python -m pytest tests/sales/` → **`516 passed`**（515＋1）。
