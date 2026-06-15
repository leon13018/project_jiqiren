# 結帳收尾語音合併（付款成功＋致謝合一句）— SDD spec

> 2026-06-15 brainstorming 定案。Pi 實測：結帳收尾語音分兩拍播放（L4「付款成功」→ L5「謝謝光臨，歡迎再來」）聽起來不夠順。本 spec：把兩句合成單一語音「付款成功，謝謝光臨，歡迎再來」由 L4 播放，動作 bow→wave_hand 順序維持不變。
> Plan：[../plans/farewell_voice_merge_2026-06-15_plan.md](../plans/farewell_voice_merge_2026-06-15_plan.md)。

## 1. 背景與現況（實證可重現）

結帳成功（終端 `s` 或客服 `scan`，共用 `_l4_pay_success`）四拍橫跨 L4→L5：

| 拍 | 來源 | 內容 |
|---|---|---|
| 1 語音 | `l4.py` `_l4_pay_success` → `L4_A_PAY_SUCCESS` | 付款成功 |
| 2 動作 | `l4.py` `ACTION_L4_PAY` | bow（非阻塞 enqueue） |
| 3 語音 | `l5.py` `run_l5` → `L5_THANKS` | 謝謝光臨，歡迎再來 |
| 4 動作 | `l5.py` `ACTION_L5_FAREWELL` | wave_hand（wire-up 阻塞至播完才 clear_cart+sleep） |

**問題**：兩句語音之間有 L4→L5 狀態切換的停頓/邊界，聽感不連貫；且該邊界正是既知「付款成功尾巴被 ALSA buffer 沖掉截斷」（`tts.py:60-64` ALSA_DRAIN_SEC 註解）發生處。

**前提確認**：`run_l5` 為**單一入口**——全 repo 僅 `_l4_pay_success` `return ("L5", …)`（拒絕/取消/客服 no 皆走 L1），故合併不影響其他路徑。

## 2. 設計核心

### 2.1 語音合併（Option 1：合併句在 L4 播）

- `_l4_pay_success`：`io.speak(L4_A_PAY_SUCCESS_FAREWELL)` + `io.do_action(ACTION_L4_PAY)` → `return ("L5", 0, 0)`（不變）。
- `run_l5`：**移除** `speak(L5_THANKS)`；保留 `do_action(ACTION_L5_FAREWELL)` → `clear_cart` → `sleep(THANK_DELAY)` → `return ("L1_via_subroutine_a", 0, 0)`。
- **`run_l5` 連帶移除 `speak` 參數**：machine 每 state 精確傳所需 callback（非統一 bundle），L5 不再 speak → `machine.py` `L5State.run` 同步不再傳 `speak=cb["speak"]`；test stub（test_logic/test_machine）與 bench 的 `run_l5` 簽名同步去 speak。（留未用參數會被 reviewer 標、違反本 codebase 慣例。）

> 棄 Option 2（合併句在 L5 播、L4 只 bow）：bow 會在無語音的靜默中先跑、較突兀。

### 2.2 常數變更（`constants/`）

- **新增** `l4_text.py`：`L4_A_PAY_SUCCESS_FAREWELL: str = "付款成功，謝謝光臨，歡迎再來"`（不加結尾「。」，match 現有語音常數 house style；14 字 → `tts._pick_rate` 落「中句 +6%」，已確認接受此語速，較原兩句短句 +3% 快約 3%、無感）。
- **移除死常數**：`L4_A_PAY_SUCCESS`（僅 `_l4_pay_success` 用）、`L5_THANKS`（僅 `run_l5` 用），方式為改各自子模組的 `__all__`；`constants/__init__.py` 用 `import *` 由 `__all__` 驅動 → **無需直接改**。`THANK_DELAY` / `ACTION_L4_PAY` / `ACTION_L5_FAREWELL` 不動。

### 2.3 動作時序與不變項

- bow（L4 非阻塞）→ wave_hand（L5）兩動作順序不變，於合併語音播放期間接連跑（＝使用者要求「動作照樣 bow 之後接 wave_hand」）。**動作 callback 本身不改**。
- `THANK_DELAY`（3s 靜默）、`clear_cart` 順序不變；整體致謝時長幾乎不變。
- **附帶修復**：L4→L5 語音邊界消失 → 免疫「付款成功尾巴被截」。

### 2.4 預錄資產（part B，Pi 端）

`tts_prewarm.py` **自動枚舉** l1~l5_text + shared 公開 str 常數（排除 `{` 模板）→ 新增 `L4_A_PAY_SUCCESS_FAREWELL` 後**腳本零改動**自動納入預熱；舊孤兒 mp3（`付款成功`/`謝謝光臨，歡迎再來`）留著無害（prewarm `os.path.exists` skip）。

SOP（文案常數改動）：Pi 端 `python3.11 -m myProgram.tts_prewarm`（勿與 demo 同跑）→ dev 端 scp 拉回 → `git add myProgram/tts_cache` commit。寫 pineedtodo。

## 3. 改檔範圍

| # | 檔 | 類型 | 內容 |
|---|---|---|---|
| 1 | `myProgram/sales/constants/l4_text.py` | 改 | +`L4_A_PAY_SUCCESS_FAREWELL`（含 `__all__`），−`L4_A_PAY_SUCCESS` |
| 2 | `myProgram/sales/constants/l5_text.py` | 改 | −`L5_THANKS`，`__all__` 清空 |
| – | `constants/__init__.py` | **不改** | `import *` 由各子模組 `__all__` 驅動，自動同步 |
| 3 | `myProgram/sales/states/l4.py` | 改 | `_l4_pay_success` speak 改用合併常數 + import |
| 4 | `myProgram/sales/states/l5.py` | 改 | `run_l5` 移除 `speak` 參數 + `speak(L5_THANKS)` + import + docstring |
| 5 | `myProgram/sales/states/machine.py` | 改 | `L5State.run` 不再傳 `speak=cb["speak"]` 給 `run_l5` |
| 6 | tests | 改 | `test_states`（L4 合併句 / L5 不 speak / run_l5 簽名）、`test_tts_worker`（prewarm 枚舉換新常數）、`test_main_read_callbacks`（樣本字串）、`test_logic`/`test_machine`（stub_run_l5 去 speak）、`bench_sales`（去 speak）、`tests/spec/*` 敘述對齊 |

## 4. Out of scope

- 動作與語音段落精準對齊（bow 對齊前半、wave 對齊後半）——維持接連即可，不引入 pacing 機制。
- `THANK_DELAY` 數值調整、rate band 覆寫（已選自然 +6%）。
- 舊孤兒快取 mp3 清除（無害，不處理）。
- 其他層 speak 文案不動。

## 5. 規範與參考

- 派 **sales-coder（opus）**；TDD。現 **589 測試是回歸網，全程保綠**。
- 改 `l5.py` 偏離原 `業務程式邏輯規劃/L5.md` ENTRY-002（L5 不再 speak）屬**刻意 UX 修訂**，docstring 標注之。
- 三段審不變（spec-reviewer + code-quality-reviewer）。
- 對照 skill `sales-tts-ux.md`（預錄/雲端混合、prewarm SOP、ALSA drain）+ `sales-dialog-design.md`（L4/L5 流程）。

## 6. 測試指令 + 預期

`python -m pytest tests/sales/`；現 589 passed + 更新後全綠、0 failed。

重點案例（test_states）：
- `_l4_pay_success`（終端 `s` 與客服 `scan` 兩入口）→ io.speak 收到 `L4_A_PAY_SUCCESS_FAREWELL`、io.do_action 收到 bow、return `("L5",0,0)`。
- `run_l5` → **不**呼叫 speak；do_action 收到 wave_hand；clear_cart 被呼叫；sleep(THANK_DELAY)；return `("L1_via_subroutine_a",0,0)`。
- 回歸：其餘結帳/取消/客服/拒絕路徑不受影響。

## 7. Commit 規範

- worktree：`worktree-farewell-merge`。
- 建議 commit：(1) `refactor(sales): 結帳收尾語音合併為單句「付款成功，謝謝光臨，歡迎再來」（L4 播、L5 去 speak 留揮手）`。
- `git add` 明列檔名；message 繁中 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[spec approved] → writing-plans 出 plan → worktree → 派 sales-coder（TDD，保 589 綠）
  → 三段審 → Iron Law → ff-merge → push → 清理
  → pineedtodo：Pi 重跑 tts_prewarm 合成合併句 + scp 拉回 + git add tts_cache commit
  → Pi 複測：結帳成功聽到單句合併語音、bow→wave_hand、斷網可播
```
