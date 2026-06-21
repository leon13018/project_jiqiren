# 移除 L1 待機 / 客服模式 — SDD spec（2026-06-21）

## 1. 背景與動機
L1 商家模式選擇層原有三模式：`1 叫賣 / 2 待機 / 3 客服`。使用者要求**只保留「叫賣」**，刪除「待機」「客服」兩個模式選擇**及其方法函數代碼**（2026-06-21 remote-control session：先「刪除待機和客服模式選擇」、後補「待機的相關方法函數代碼也要一起刪除」）。Pi demo 走 web UI / 觸控，這兩個商家層操作模式不再需要。
- **選單去留（使用者選定）**：選單**保留**，只剩「1 — 叫賣模式」+ q；**不**砍整個模式選擇層。

## 2. 設計核心 + 行為規約
- `L1_MENU_BANNER` 只列「1 — 叫賣模式」+「（任何時刻按 q 直接退出程式）」。
- `run_l1` 主迴圈：
  - `key == "1"` → `_run_l1_hawk`（不變）
  - `key == "q"` → C14 兩次確認退出（不變）
  - 其他鍵（含舊的 `"2"`/`"3"`）→ reset confirm + 重印選單（被忽略）。**移除 `key=="2"`/`key=="3"` 專屬分派分支**。
- 移除 `_run_l1_standby`、`_run_l1_service` 兩函式（grep 確認無其他 caller）。
- `enter_hawk_immediately=True` 路徑不變（交易完成後直接連續叫賣）。
- hawk loop 內按 `2`/`3` 仍是「被忽略的非 q/t 鍵」（行為不變 → `test_l1_c_hawk_non_q_keys_ignored` 保留）。

## 3. 改檔範圍（高層；step 移 plan.md）
| 檔 | 改動 |
|---|---|
| `myProgram/sales/states/l1.py` | 移 import `L1_STANDBY_ENTRY_PROMPT` / `SERVICE_PHONE`；`run_l1` 移 `key=="2"`/`"3"` 分派；移 `_run_l1_service` + `_run_l1_standby`；module docstring + `run_l1` docstring「三鏈路（叫賣/待機/客服）」+ line 27/114 註解更新為只剩 hawk |
| `myProgram/sales/constants/l1_text.py` | `L1_MENU_BANNER` 移「2 待機」「3 客服」兩行；移 `L1_STANDBY_ENTRY_PROMPT` 常數 + `__all__` 條目 + 其註解 |
| `tests/spec/L1_mode_select_scenarios.py` | 移 L1-A（service）section、L1-B（standby ×3）section；L1-ENTRY-001 描述改「選單只含 1 叫賣 + q」；header 區塊註解更新 |
| `tests/sales/test_states.py` | `test_l1_entry_prints_mode_select_menu` 改斷言（含 `1`/`q`、**不含** `2`/`3`）+ 註解；移 `test_l1_a_service_mode_prints_phone_and_returns_to_menu`；移 `test_l1_b_standby_*`（×3） |

## 4. Out of scope（明示不動，避免越界）
- **`SERVICE_PHONE` 常數**（`constants/shared.py`）+ **L2-L4 顧客「客服 confirm」全套**（`_service_confirm.py` / `_timed_confirm.py` ServiceConfirm / `l4.py` 客服分支 + 測試 `test_service_confirm.py` / `test_timed_confirm.py` / `test_states.py` L4 客服 3602+）——這是**不同功能**（顧客點餐途中喊客服），保留。本次只刪「L1 商家層按 3 印電話」這個模式。
- web `"standby"` phase（`bus`/`display`/`machine` 的 phase 名）——與 L1 待機模式無關，保留。
- `test_machine.py`（phase `"standby"`）/ `test_logic.py`（L4 客服 docstring）——false positive，不動。
- `L1_HAWK_ENTRY_PROMPT` / hawk 全套 + C14 q 確認 + `enter_hawk_immediately`——保留。

## 5. 規範與參考
- 派 **sales-coder**（opus，frontmatter 預載 karpathy + TDD）。
- 對照 `project-01-workflow` skill `reference/sales-dialog-design.md` §服務客服 service_confirm，確認 L4 客服是獨立 helper、不誤刪。
- 繁中產出物。**最小外科式刪除**（karpathy）：不重構 run_l1 結構、不新增抽象，只拔 2/3 兩條與其碼。
- 刪除驗證：`grep -i` 掃 `待機|standby|_run_l1_standby|_run_l1_service|L1_STANDBY` 於 `myProgram/` + `tests/`，排除 web phase `"standby"` 與 L4 客服後須**零 orphan**（依 conventions.md「清理後 grep 驗證必加 -i」紀律）。

## 6. 測試指令 + 預期結果
- `py -3.14 -m pytest tests/sales/ tests/spec/ tests/stt/test_main_wireup.py -q`
- 預期：**全綠**，無 FAIL / ERROR / orphan import。移除 4 條 L1 測試（1 service + 3 standby，含 test_states 與其在 spec scaffold 的對應）後總數較前下降；其餘測試數不變。
- Pi 端：`python3.11 -m myProgram --web` → 選單只顯示「1 — 叫賣模式」+ q；按 1 進叫賣正常。

## 7. Commit 規範
- worktree 首 commit：本 spec + plan doc（`git add` 明列兩檔）。
- 實作 commit：prod（`l1.py` + `l1_text.py`）+ tests，可合一 commit 或 prod/test 分兩；`git add` 明列、禁 `-A`。
- message 範本：`refactor(l1): drop standby & service merchant modes, hawk-only menu` + 繁中 body（why + 刪了什麼 + OOS 保留 SERVICE_PHONE/客服 confirm）+ `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
[現況] L1 選單 1/2/3 ─┬ 1 → _run_l1_hawk
                      ├ 2 → _run_l1_standby（印提示 / r 回選單 / q 退）
                      └ 3 → _run_l1_service（印 SERVICE_PHONE → 回選單）
[目標] L1 選單 1 ───── 1 → _run_l1_hawk（2/3 分派 + standby/service 函式 + L1_STANDBY 常數 + 對應測試全刪；SERVICE_PHONE 常數與顧客客服 confirm 不動）
```
