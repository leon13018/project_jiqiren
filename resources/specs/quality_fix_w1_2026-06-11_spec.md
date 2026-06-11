# quality_fix_w1 — 代碼質檢修復 Wave 1（高價值項 #1/#3/#4）spec

## 1. 背景與動機

2026-06-11 全 `myProgram/` 代碼質檢 review（聚焦邏輯重複 + 精簡化）發現 13 項，使用者核准全修、依價值切 4 waves（W1=#1/#3/#4、W2=#2 dispatcher 完整統一、W3=#5-#9、W4=#10-#13）。本 spec 為 Wave 1：

- **#1**：`DialogSession._c2_checkout_via_confirm` 與 `checkout_flow` 的「confirm → 三路分流」近逐字重複（`l2_l3_dialog.py`）。同檔曾因雙份維護漏改（2026-05-27 ACTION_L3 修補需「兩處 transition 點補上」），同一 bug class。
- **#3**：`tts.py` `TtsWorker._process` play 階段三個 except 各印幾乎相同的錯誤區塊，且 `with self._lock: self._proc = None` 清理重複 4 次（3 except + 成功路徑）。
- **#4**：at-cap 文案 `f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加"` 在 `_l2_l3_qty_followup.py` 兩處逐字重複，且是 states/ 內唯一未進 constants 的 speak 文案。

## 2. 設計核心 + 行為規約

**鐵則：行為零改變（純重構）**——speak / print 字面一字不變；既有測試零修改；`tests/sales/` 460 passed 前後不變是第一道等價證據。

### 改動 1（#1）：`_c2_checkout_via_confirm` 委派 `checkout_flow`

新實作（method 體全換）：

```python
result = self.checkout_flow()
if result is not None:
    return result
return self.main_loop()
```

等價論證（逐分支）：

| `_dialog_checkout_confirm` 結果 | `checkout_flow` 行為 | 原 `_c2_checkout_via_confirm` | 新版 |
|---|---|---|---|
| `"yes"` | speak GO + do_action(GO) + `("L4", 0)` | 同 | checkout_flow 回 tuple → 直接 return |
| `"cancel_to_l1"` | `self.exit_a()` tuple | 同 | 同上 |
| 其他三態 | `_handle_checkout_confirm_result` + `None` | `_handle_...` + `self.main_loop()` | checkout_flow 回 None → `return self.main_loop()` |

docstring 保留「2026-05-29 反轉合流」歷史說明，補「分流本體共用 checkout_flow」一句。既有 C-2 測試（`test_states.py`）走 `run_dialog` 公開流程、未 mock 私有 method → 透明。

### 改動 2（#3）：`_process` play 階段 try/except/finally + 錯誤印製 helper

- 新增 module-level helper（synth / play 共用）：

```python
def _print_failure(stage: str, detail_lines: list) -> None:
    print(f"[語音] ⚠️ TTS 失敗（階段={stage}）")
    for line in detail_lines:
        print(f"[語音]   {line}")
    print(f"[語音] 此字略過,繼續下一字")
```

- detail_lines 由 caller 依**舊版順序**排列（FileNotFoundError 的 `text` 在 `hint` 前；CalledProcessError 的 `cmd` 在 `text` 前），印出字面逐行（含 `[語音]   ` 三空格縮排）與舊版一致。
- play 階段改 `try/except/finally`：`finally` 內 `with self._lock: self._proc = None` 統一清理（取代 4 處重複）；三個 except 只組 detail_lines + return。
- 時序等價：成功 path 原「清 _proc → sleep(ALSA_DRAIN_SEC)」、新「try 正常結束 → finally 清 _proc → sleep」順序相同；失敗 path 原「印 → 清 _proc → return」、新「except 印 → finally 清 → return 生效」順序相同；synth 失敗不進 play try（_proc 未 spawn），與舊版相同。
- 既有大段註解（stdin=DEVNULL 原因 / Popen vs run / lock 不包 wait / SIGTERM expected exit / ALSA drain）原樣保留於對應位置。
- `test_tts_worker.py` 不驗錯誤印出字面（驗 `_pending` 計數 / wait_idle 行為）→ 透明。

### 改動 3（#4）：`AT_CAP_NOTICE_TEMPLATE` 抽常數

- `constants/products.py` 新增（含 `__all__`）：

```python
AT_CAP_NOTICE_TEMPLATE: str = "{product}已經點到單筆上限 {max_qty} {unit}，無法再加"
```

- `_l2_l3_qty_followup.py` 兩處（`resolve_and_add_products` Pass 1 / `_qty_follow_up_sub_loop`）改：

```python
io.speak(AT_CAP_NOTICE_TEMPLATE.format(product=product, max_qty=MAX_QTY_PER_ITEM, unit=unit))
```

- format 後字串與原 f-string 完全相同；`test_states.py:6098/6230` 的 substring assert（「已經點到單筆上限」「無法再加」）不動仍綠。

## 3. 改檔範圍（高層）

| 檔 | 改動類型 | 行數估 |
|---|---|---|
| `myProgram/sales/states/l2_l3_dialog.py` | `_c2_checkout_via_confirm` 體委派化 | 約 -15 |
| `myProgram/tts.py` | `_print_failure` helper + `_process` play 段重構 | 淨約 -20 |
| `myProgram/sales/constants/products.py` | +1 常數 + `__all__` | +4 |
| `myProgram/sales/states/_l2_l3_qty_followup.py` | 2 處換常數 + import | ±4 |
| `tests/` | **零修改** | 0 |

step-by-step 見 `resources/plans/quality_fix_w1_2026-06-11_plan.md`。

## 4. Out of scope

- #2 dispatcher 完整統一（Wave 2 獨立 spec）；#5-#9（Wave 3）；#10-#13（Wave 4）。
- review 判定刻意設計 7 項（ack speak UX pacing / input_reader latest-wins drain / confirm facade 測試 seam / TimedConfirm 家族邊界 / machine.py entry_invariant / l4 函式版 confirm 呼叫 / L3_STRICT 可讀性片語）。
- 任何文案字面、行為、timeout 數值變更。

## 5. 規範與參考

- 派 **sales-coder** 實作（tts.py worker 結構改動，sales-tts-ux.md 明定必派；karpathy + TDD skill 已 frontmatter 預載）。
- 背景參考：skill `reference/sales-tts-ux.md` §speak_and_wait/TtsWorker（#3）；`reference/sales-dialog-design.md` §C-2（#1）。

## 6. 測試指令 + 預期結果

每 commit 後跑：`python -m pytest tests/sales/` → **460 passed**（數量不變）。
無新增測試：純重構不加測試；at-cap 字面已被 `test_states.py:6098/6230` substring assert 釘住。

## 7. Commit 規範（3 個獨立 commit，依序）

1. `refactor(sales): dedupe C-2 checkout confirm flow via checkout_flow`
   - add：`myProgram/sales/states/l2_l3_dialog.py`
2. `refactor(tts): consolidate play-stage failure handling into try/finally + helper`
   - add：`myProgram/tts.py`
3. `refactor(sales): extract AT_CAP_NOTICE_TEMPLATE to constants`
   - add：`myProgram/sales/constants/products.py` `myProgram/sales/states/_l2_l3_qty_followup.py`

body 繁中說明 + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；git add 明列檔名（禁 `-A`/`.`）。

## 8. 流程鳥瞰

```
worktree quality-fix-w1（branch worktree-quality-fix-w1）
  ├ 主 agent：spec + plan commit（首 commit）
  ├ sales-coder：baseline pytest → #1 → pytest → commit
  │             → #3 → pytest → commit → #4 → pytest → commit → 回報 4-status
  ├ 主 agent：Iron Law（pytest 460 + git branch --contains + diff --stat 對照 §3）
  ├ spec-reviewer（sonnet）→ code-quality-reviewer（opus）
  └ ExitWorktree(keep) → ff-merge → push（Stop hook 自動 sync Pi）→ worktree cleanup
```
