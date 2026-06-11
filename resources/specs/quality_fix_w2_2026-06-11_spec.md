# quality_fix_w2 — 代碼質檢修復 Wave 2（#2 dialog dispatcher 完整統一）spec

## 1. 背景與動機

2026-06-11 質檢 review 發現 #2：`l2_l3_dialog.py` 的 `DialogSession.main_loop()`（主迴圈內聯分派，438-576 行）與 `DialogSession._dispatch_inner()`（沉默期語境，347-424 行）的意圖分派邏輯約 80% 逐字重複——「拒絕 / 想一下 / 結帳 / 客服 / 想買無商品 / 商品 / unclear 兜底」七路判定雙份維護。歷史已踩同類 bug（2026-05-27 ACTION_L3 修補需「兩處 transition 點補上」）。使用者拍板**完整統一兩 dispatcher**（非只抽商品區塊）。

W1（`60a826b`）已 merge；本 wave 基於其上。

## 2. 設計核心 + 行為規約

**鐵則：行為零改變（純重構）**——`tests/sales/` **502 passed** 前後不變；既有測試零修改；speak 字面 / 計數器時機 / 回傳協定一字不變。

### 統一設計

新增單一分派核心 `DialogSession._dispatch(response, *, in_main_loop: bool)`，兩語境差異全部顯式參數化；`main_loop` 主迴圈體與 `_think_silence` 改呼叫它；**刪除 `_dispatch_inner`**（repo 內唯一 caller 是 `_think_silence`；測試只經 `run_dialog` / `main_loop` 公開 seam 驅動，無 mock 私有名——已 grep 驗證）。

回傳協定統一：`tuple` = 退出 dialog（caller 直接 return）；`None` = 已處理（主迴圈 continue 下一輪；沉默鏈回傳給上層 think 分支）。

### 逐 quirk 行為矩陣（改前 → 改後必須等價）

| intent | 主迴圈語境（`in_main_loop=True`） | 沉默期語境（`False`，原 `_dispatch_inner`） |
|---|---|---|
| 拒絕 | `CANCEL_CONFIRM.run` gate → True=`exit_a()`；False=speak `policy.cancel_declined_resume` | **同**（兩語境本就相同） |
| 想一下 | `unclear_count=0`；`think_count+=1`；達 limit→`on_think_exhausted`；**saved/writeback 包裹**（Q1：L2 不回寫 + B11：cart 非空 reset 0）包住 `_think_silence()` | `think_count+=1`；達 limit→`on_think_exhausted`；直接 `return self._think_silence()`（互遞迴，無包裹） |
| 結帳 | `on_checkout_main`（tuple→return；else 續等） | `on_checkout_inner`（Q2：不碰 unclear） |
| 客服 | **`unclear_count=0`** 先行；`SERVICE_CONFIRM.run` → yes=speak `service_yes_prompt`；no=`exit_a()` | 同流程但**無 unclear reset** |
| 想買無商品 | speak `DIALOG_VAGUE_BUY_REASK`，不動任何計數 | **同** |
| 商品 | **`unclear_count=0`** 先行；`was_empty` 轉場分支內 **`think_count=0`**（B11）+ `do_action(ACTION_L3)` + 合成 speak | 無 unclear reset；**無 `think_count=0`**（B11 註明由主迴圈 writeback 分支事後處理）；其餘同 |
| 兜底（無命中） | `unclear_count+=1`；達 `UNCLEAR_MAX`→`on_unclear_exhausted`（tuple→return；else 續）；否則 speak `policy.clarify` | **只** speak `policy.clarify`（Q2：完全不計數） |

### 分支順序等價論證（唯一的順序差異）

原 main_loop 判定序：拒絕→想一下→結帳→客服→**商品→想買無商品**→兜底；原 `_dispatch_inner`：…→客服→**想買無商品→商品**→兜底。統一版採 inner 序（想買無商品先、省一次 `parse_products` 呼叫）。

等價成立因兩分支**互斥**：`classify_intent` 的商品判定（`KEYWORDS_ICED_TEA` / `KEYWORDS_SCRATCH`）排在「想買無商品」之前，且該兩組 keyword 集與 `product_parser._PRODUCT_KEYWORD_TO_NAME` 的 keyword 集**逐項一致**（已逐項比對：茶 7 項、刮刮樂 11 項相同）——`intent=="想買無商品"` 時 `parse_products` 必回 `[]`，反之 products 非空時 intent 必為 `商品:X`。兩序在現行 keyword 資料下不可能產生不同走向。統一後只剩一個順序，未來新增 parser keyword 也不再有跨語境分歧。

### policy 取值時點等價

原 main_loop 在 read 前取 `policy = self.policy()` 並用於 dispatch；統一版 `_dispatch` 在進入時重算 `self.policy()`。兩時點之間（read 返回 → dispatch 進入）無任何 cart 變動 → 推導結果必相同。main_loop 仍自取 policy 供 `read_timeout` 用。

### 保留不動

`run_dialog` facade、`c2_second_stage` / `_c2_checkout_via_confirm`（W1 已重構）、`checkout_flow`、`exit_a`、`_reenter_speak`、`ModePolicy` 階層與兩單例、`_dialog_checkout_confirm` / `_handle_checkout_confirm_result` / `_dialog_unclear_final_confirmation` / `_prepend_cancel_notices` / `_build_order_summary`、模組 import 清單（統一後無 orphan import——所有常數兩語境原本都各自使用）。

## 3. 改檔範圍（高層）

| 檔 | 改動類型 | 行數估 |
|---|---|---|
| `myProgram/sales/states/l2_l3_dialog.py` | +`_dispatch`（~110 行含註解）；`main_loop` 迴圈體縮為 read+timeout+dispatch（~-100）；`_think_silence` 末行改呼 `_dispatch`；刪 `_dispatch_inner`（~-78） | 淨約 -60 |
| `tests/` | **零修改** | 0 |

單一 commit（一個語意完整的統一動作，拆開會破壞中間綠燈）。step-by-step 見 `resources/plans/quality_fix_w2_2026-06-11_plan.md`。

## 4. Out of scope

- W3（#5-#9）/ W4（#10-#13）各項；尤其 #7（`_dialog_unclear_final_confirmation`）本 wave 不碰。
- 既有 ModePolicy hook 設計、計數器歸屬、文案、timeout 數值。
- review 判定刻意設計 7 項。

## 5. 規範與參考

- 派 **sales-coder** 實作；plan 內已給完整新碼（含註解）與精確刪除邊界。
- 背景參考：skill `reference/sales-dialog-design.md`（C-2 / cancel_confirm / service_confirm 行為）；本檔 §2 行為矩陣為等價驗收基準。

## 6. 測試指令 + 預期結果

每階段跑：`python -m pytest tests/sales/` → **502 passed**（數量不變）。
無新增測試：純重構；七路分支行為已被既有 test_states / test_mode_policy / tests/spec 場景測試覆蓋（含 `_dispatch_inner` 對應的沉默期 regression 測試，重構後走 `_dispatch(in_main_loop=False)` 同 path）。

## 7. Commit 規範（1 個 commit）

`refactor(sales): unify dialog dispatch core for main-loop and inner contexts`
- add：`myProgram/sales/states/l2_l3_dialog.py`
- body 繁中說明統一範圍 + 逐 quirk 等價依據 + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；禁 `-A`/`.`。

## 8. 流程鳥瞰

```
worktree quality-fix-w2（branch worktree-quality-fix-w2）
  ├ 主 agent：spec + plan commit（首 commit；user 已預先授權免逐 wave approval）
  ├ sales-coder：baseline pytest 502 → 統一改動 → pytest 502 → commit → 回報
  ├ 主 agent：Iron Law（pytest 502 + branch verify + diff 對照 §3）
  ├ spec-reviewer（sonnet）→ code-quality-reviewer（opus）
  └ ExitWorktree(keep) → ff-merge → push（Stop hook sync Pi）→ cleanup
```
