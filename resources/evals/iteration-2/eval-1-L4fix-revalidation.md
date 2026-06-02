# Iteration-2 補充驗證 — L4 v3 stale 修正（重跑 scenario 1 變體），model=opus

> **目的**：round-2 cluster 4 把 sales-dialog-design.md 的 L4 段從 stale v2（30s 單 budget）重寫為 v3 準確版（36s 雙計時器）。本變體 scenario 專測「L4 計時設計釐清」以驗證 stale hazard 是否消除。

## 背景：round-1 的反覆問題
iteration-1 / baseline 的 scenario-1 navigator **每次都標** 「sales-dialog-design §L4 budget stale（v2 30s vs code v3 36s）」「reference 矛盾 → 回 source code 確認」——stale 文件害 navigator 不信任 reference、被迫下沉 code。

## Round-2 後結果（本次）
- Navigator 正確答出 L4 v3：總 budget `L4_TOTAL_BUDGET=36s` + QR 刷新循環 `L4_QR_REFRESH_INTERVAL=12s`（36=12×3）+ 子狀態暫停/補償 + 客服 yes reset；另點出子狀態計時 service 24s / cancel 6s。
- **計時設計來源「直接從 reference 讀到」**，不需靠 grep code。
- 主動交叉核實 `timing.py`：實際值 36/12/24/6 **與 reference 完全一致**；判定「**reference 沒有 stale、沒有自相矛盾，且誠實標注權威值出處**」。

→ **stale hazard 消除並驗證**。round-1 反覆出現的「reference 矛盾、回 code 確認」不再發生。

## navigator 另標（非本輪 scope）
1. `tests/sales/test_states.py` 的**註解/docstring** 仍殘留 30s / 12s 舊值（實際 assert 用 import 常數故 test 不錯）——屬 **test code 註解**、非 skill；round-2 §11.4 不動 myProgram/tests，記為 follow-up。
2. 「`L4_TOTAL_BUDGET` 須整除 `L4_QR_REFRESH_INTERVAL`」不變量由 `test_constants` 守，reference L4 段有寫「36=12×3」但沒明講是硬性 test 不變量——可補一句（屬補內容）。
