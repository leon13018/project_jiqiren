# machine_entry_invariant_guard — Mini SDD spec

- **檔**：`myProgram/sales/states/machine.py:183-186`（`SalesMachine.run()` 進場 invariant 分派）
- **改前**：
  ```python
  if state.entry_invariant == "empty":
      _assert_cart_empty(self.cart, state.entry_ctx)
  else:
      _assert_cart_nonempty(self.cart, state.entry_ctx)
  ```
- **改後**：
  ```python
  if state.entry_invariant == "empty":
      _assert_cart_empty(self.cart, state.entry_ctx)
  elif state.entry_invariant == "nonempty":
      _assert_cart_nonempty(self.cart, state.entry_ctx)
  else:
      raise ValueError(
          f"未知 entry_invariant：{state.entry_invariant!r}"
          f"（state={type(state).__name__}）"
      )
  ```
- **伴隨測試**：`tests/sales/test_machine.py` 新增 1 測（TDD 先 Red 後 Green）——構造 `State` 子類別帶非法 `entry_invariant`（如 `"Nonempty"`）塞進 `machine._states`，`machine.run()` 進場即 `pytest.raises(ValueError, match="entry_invariant")`（raise 發生在 `state.run` 之前，不需 stub `run_*`）。
- **Why**：反思 `entry-invariant-else-branch-silent-mismatch`（2026-06-10）採納——現行 else 分支讓任何非 `"empty"` 值（含 typo）靜默走 nonempty 檢查，cart 恰非空時錯誤檢查靜默通過；改 fail-fast 與本檔 A4-c 哲學一致，合法值（`"empty"`/`"nonempty"`）零行為變更。
- **Out of scope**：不加 `__init_subclass__` / abstract property 強制 class attr（同批反思 `state-abc-class-attr-not-enforced` 已否決——封閉狀態集 + 缺屬性本就 AttributeError loud fail）。
- **驗證**：`python -m pytest tests/sales/` 全綠（459 既有 + 1 新測 = 460 passed）。
