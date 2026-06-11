# Mini Spec：移除死碼常數 CANCEL_CONFIRMED_NOTICE

- **日期**：2026-06-11
- **類型**：死碼清除（refactor，無行為變更）
- **檔案**：`myProgram/sales/constants/shared.py`

## What

刪除常數 `CANCEL_CONFIRMED_NOTICE`，含兩處：

1. `__all__` 內 `"CANCEL_CONFIRMED_NOTICE",` 條目
2. 定義行 `CANCEL_CONFIRMED_NOTICE: str = "好的，已為您取消這次交易"`

> 第 33-34 行的 comment block 為 `CANCEL_CONFIRM_PROMPT` / `CANCEL_DECLINED_NOTICE` 共用（描述整組 cancel confirm 子狀態文案），非本常數專屬 → **不動**。本常數無專屬註解行。

### 改前

```python
__all__ = [
    ...
    "CANCEL_CONFIRM_PROMPT",
    "CANCEL_CONFIRMED_NOTICE",
    "CANCEL_DECLINED_NOTICE",
    ...
]

# Cross-L cancel confirm 子狀態文案（2026-05-29 加）
# 跨 L2/L3/L4 任何 read 點偵測 cancel intent 後進 6s confirm
CANCEL_CONFIRM_PROMPT: str = "您是否想取消這次交易？6 秒後系統將自動取消"
CANCEL_CONFIRMED_NOTICE: str = "好的，已為您取消這次交易"
CANCEL_DECLINED_NOTICE: str = "好的，繼續為您服務"
```

### 改後

```python
__all__ = [
    ...
    "CANCEL_CONFIRM_PROMPT",
    "CANCEL_DECLINED_NOTICE",
    ...
]

# Cross-L cancel confirm 子狀態文案（2026-05-29 加）
# 跨 L2/L3/L4 任何 read 點偵測 cancel intent 後進 6s confirm
CANCEL_CONFIRM_PROMPT: str = "您是否想取消這次交易？6 秒後系統將自動取消"
CANCEL_DECLINED_NOTICE: str = "好的，繼續為您服務"
```

## Why

死碼審計（AST + grep 雙重驗證）：`CANCEL_CONFIRMED_NOTICE` 全 codebase（myProgram + tests 所有 .py）零引用、零測試斷言。cancel_confirm 的 YES 路徑直走 exit_a 致謝流程，此「已取消」通知文案從未被 speak。留著只是噪音，刪除降低後續維護者誤解（以為有對應 speak 點）。

## 驗證

- `python -m pytest tests/sales/ -q` → **501 passed**（與改前一致，不少一個）。
- 改後再次 grep `CANCEL_CONFIRMED_NOTICE` → 全 codebase 零命中。
