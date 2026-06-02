# Sales 對話狀態機 / 跨層流程設計

> **🎯 何時讀本檔**：要改 sales 對話狀態機 / 跨層流程（L2 / L3 / L4、qty followup、cancel / service confirm、C-2、錢包保守邏輯）。

## 目錄
- C-2 三選一設計
- L4 wall-clock budget
- 跨層 cancel_confirm 子狀態
- 服務客服 service_confirm 統一 helper
- Confirm default 必須保守

myProgram sales 對話層（L2/L3/L4 + qty followup + 各 confirm 子狀態）的領域設計決策。改 sales code 須對照本檔，避免推翻已對齊的 UX / 錢包保守 / 跨層 confirm 等決定。

---

## C-2 三選一設計

**背景**：Pi demo 2026-05-28 揭示 c2 二元 yes/no UX bug——顧客講「不要」歧義（「不要結帳、繼續逛」vs「不要整單」）被當「拒絕整單」清 cart，違反顧客錢包預期。重構為**三選一明確意圖**（無歧義詞 fall through）：
```
[語音] 請問您想要繼續選購商品、結賬還是取消購買，如 6 秒內未答復將進行結賬。
```

### 三選一行為對應表
| 顧客動作 | helper | 行為 |
|---|---|---|
| **CANCEL keyword**（取消 / 取消吧 / 幫我取消…） | `_dialog_exit_a` | 清 cart + speak `L3_REJECT_THANKS` + return `("L1_via_subroutine_a", 0)` 退出 |
| **CONTINUE keyword**（繼續 / 繼續選購…） | `_dialog_main_loop` | **不清 cart**，重入 dialog 讓顧客繼續加單 |
| **CHECKOUT keyword**（結 / 結賬 / 直接結賬…） | `_c2_checkout_via_confirm` | 經 `_dialog_checkout_confirm` 確認明細 → "yes" 進 L4；非 yes 清 cart + 重入 |
| **6s timeout（silent）** | `_c2_checkout_via_confirm` | 合流到 confirm path（見下「反轉」）|
| 亂答（不在三組 keyword） | 既有 silent 倒數 | 首次 speak「請說『繼續』『結賬』或『取消』」，後續 silent；不重置 deadline |

- **單字 token 用 strict-short**（`KEYWORDS_C2_*_STRICT_SHORT`）：「結」「繼續」「取消」單字嚴格相等才命中，防 substring 誤命中「結束」/「繼續努力」/「取消會議」。
- **設計原則**：未來其他 dispatcher 若有「一詞涵蓋多意圖」風險，第一反應是**拆 path 而非補強 keyword list**。

### CHECKOUT keyword 經 confirm，silent timeout 也合流到 confirm（2026-05-29 反轉）
- **CHECKOUT keyword** → 經 `_dialog_checkout_confirm`（speak「您即將結帳，總共…正確嗎？」12s + 5 次亂答容忍）：給「最後確認金額」機會防多商品累加誤判。
- **silent 6s timeout** → **原**直接 L4（`_c2_direct_checkout`），**後反轉**（commits `87a44bb`→`3a94fa8`）：silent customer 也應有確認金額機會、且「6 秒後自動結賬」可寬鬆解讀為「啟動結帳流程（含 confirm）」。`_c2_direct_checkout` 刪除、silent timeout 改 call `_c2_checkout_via_confirm`（與 CHECKOUT path 一致）。
- **後續**（2026-05-30）：keyword family 大幅擴（CONTINUE/CANCEL/CONFIRM_YES + REJECT 同類一次掃；FP 防護故意不加「還要」「加買」）；新 sentinel `cancel_to_l1`（`_dialog_checkout_confirm` 內 cancel_confirm YES → 3 個 caller 識別後直 call `_dialog_exit_a` 退 L1，免兩輪 YES）；合成 ack voice（`L3_C2_CONTINUE_ACK` / `*_CANCEL_DECLINED_RESUME` 避免顧客失上下文）。詳見對應 commit。
- **reuse 既有 helper**（零新 architecture）：`_dialog_exit_a`（取消退出）/ `_dialog_checkout_confirm`（C-1 confirm）/ `_dialog_main_loop`（重入）。

---

## L4 wall-clock budget

> ⚠️ **本段描述 v2「30s 單一 budget」設計（2026-05-30 `0090786`）；code 後續演進到 v3 雙計時器（`L4_TOTAL_BUDGET=36s` + `L4_QR_REFRESH_INTERVAL=12s`，`36=12×3`）。改 L4 前以 `resources/specs/L4_v3_dual_timer_spec.md` + `timing.py`/`l4.py` 實際值為準；下方虛擬碼與行為矩陣的「結構」仍適用，差別在 budget 值與多一個 QR 刷新計時器。**

從原本 60s + 雙計數器 + 4 階段語氣 + final confirmation 大幅簡化為單一 wall-clock budget：
```python
deadline = time.monotonic() + L4_TOTAL_BUDGET
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0: return _l4_exit_d_forced(...)        # 清 cart 退 L1
    response = read_customer_input(timeout=min(L4_PROMPT_INTERVAL, remaining))  # min(12, remaining)
    if response is None:
        speak(L4_REMIND_PROMPT)                              # 「請您掃碼付款」每 12s 重提示（不重置 budget）
        continue
    result = _l4_dispatch_response(...)
    if isinstance(result, tuple): return result
    if result is None:                                       # 客服繼續（唯一語意）
        _l4_print_entry_detail(...); speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
        deadline = time.monotonic() + L4_TOTAL_BUDGET        # re-speak entry + reset budget
    continue                                                 # "ack" → 不重置 budget
```

### 鏈路行為矩陣
| 顧客動作 | 行為 |
|---|---|
| 終端 "s" | 鏈路 A → `L4_A_PAY_SUCCESS` + `do_action(ACTION_L4_PAY)` → L5 |
| 等待安撫 NLU（好/嗯/等等） | `L4_ACK_GENTLE` + continue 不重置 budget |
| 拒絕 NLU | `cancel_confirm` 6s gate → YES=`_l4_exit_b` / NO=`CANCEL_DECLINED_NOTICE` + continue 不重置 |
| 客服 NLU | `_service_confirm`（24s）→ YES=re-speak entry + reset budget / NO=清 cart 退 L1 / "s"=L5 |
| 想一下 / 結帳 / 商品 / 無法判斷 | speak `L4_UNCLEAR_NOTICE`「不好意思我聽不太懂」+ continue **不重置** |
| silent 12s 沒回應 | speak `L4_REMIND_PROMPT`「請您掃碼付款」+ continue **不重置**（每 12s 重提示）|
| budget 耗盡 | `_l4_exit_d_forced` speak `L4_D_FORCED_EXIT` + clear cart 退 L1 |

- **design 哲學（user 字面）**：「就單純 budget 計時，沒結賬每 12 秒重複提示一次，亂輸入不重置 budget、只印提示」。
- **How to apply**：所有非 "ack"/`None` path 都不重置 budget；新亂答 path → speak `L4_UNCLEAR_NOTICE` + continue；客服繼續一定要 re-speak entry + reset budget；**不要加新 counter**（unclear_count / loop_count 等已廢除）。

---

## 跨層 cancel_confirm 子狀態

訴求「L2~L4 任何階段講『不買了』『取消交易』→ 6s 確認後退 L1」。**設計**：跨層任何 reject 意圖偵測點 → 進 6s confirm 子狀態 → YES/timeout 取消、NO 繼續。

**Helper `myProgram/sales/states/_cancel_confirm.py`**：
```python
def cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> bool:
    # True = 取消（YES keyword / silent timeout / 亂答耗盡 budget）；False = NO keyword
```
- 6s wall-clock budget（`CANCEL_CONFIRM_TIMEOUT=6.0`），用 `speak_and_wait` 確保 deadline 從 TTS 播完起算（見 [sales-tts-ux.md](sales-tts-ux.md) speak_and_wait）。
- **NO check 先於 YES check**（避免「不要取消」誤命中 YES 的「取消」substring）；silent / 倒數歸零 → True（字面 promise「6 秒後自動取消」）。
- `is_cancel_intent(response)`：用 `mode="l4"` 走 classify_intent 認「拒絕」（L3 strict mode 會漏「不要」「不用」短詞，跨層用 l4 mode 抓更廣）。
- keyword 集 `KEYWORDS_CANCEL_CONFIRM_YES/NO(_STRICT_SHORT)`、文案 `CANCEL_CONFIRM_PROMPT/CONFIRMED_NOTICE/DECLINED_NOTICE`（見 keywords.py / shared.py）。

**8 個 explicit gate**：`_dialog_main_loop`（L2/L3 主等待）/ `_dialog_dispatch_inner_l2` / `_dialog_dispatch_inner_l3` / `_dialog_checkout_confirm` / `_l4_dispatch_response` / `_dialog_unclear_final_confirmation` / `_l4_final_confirmation` / `_l4_service_mode`——reject → cancel_confirm，YES 退 L1 / NO 重 prompt continue。

**不 cover 的 2 例外**：
- **qty_followup**（`_l2_l3_qty_followup.py`）：reject 仍直接 `return False` fall-through 到 main loop，顧客需再喊一次才觸發 cancel_confirm。Why 不 cover：return type 是 `tuple[bool, str|None]`，propagate 取消 sentinel 需 invasive return-type change 影響 100+ fixture（Karpathy avoid premature abstraction + user 接受 UX trade-off）。
- **C-2 CANCEL keyword**：直走 `_dialog_exit_a` 退 L1，**不走 cancel_confirm**。Why：C-2 已是「警告 6s 倒數中」context，再加 6s confirm = 罰 12s 違反字面 promise（user 拍板 keep 快速 path）。

> 13 個 function signature 加 `speak_and_wait=None`（default fallback `speak`，向後相容）；propagate chain `logic.run → run_dialog/run_l4 → 13 helper`。

---

## 服務客服 service_confirm 統一 helper

所有層「顧客講客服進入」都進統一 helper `_service_confirm`（對齊 cancel_confirm 風格但**語意 inverse**）。

**Helper `myProgram/sales/states/_service_confirm.py`**：
```python
def service_confirm(speak, print_terminal, read_customer_input, speak_and_wait=None, *, allow_scan=False) -> str:
    # "yes" | "no" | "scan"(僅 allow_scan)
```
行為：印 `SERVICE_PHONE` → `speak_and_wait("請問是否繼續交易？24秒後將自動取消交易。")` → `deadline = monotonic()+L4_C_CONFIRM_TIMEOUT`（24s 一次性決策）→ 迴圈讀：silent/歸零 → `"no"`；**NO keyword（先 check，防「不繼續」含「繼續」誤命中 YES）** → `"no"`；YES → `"yes"`；終端 "s"（allow_scan）→ `"scan"`；亂答 → speak unclear **不重置 budget**。

**6 個進入點**：`_l4_service_mode`（allow_scan=True；YES→return None 讓 main loop re-speak entry + reset budget / NO→清 cart 退 L1）｜`_dialog_main_loop`、`_dialog_dispatch_inner_l2`、`_dialog_dispatch_inner_l3`（YES→re-speak 該鏈路 entry prompt + continue / NO→`_dialog_exit_a`）｜`_qty_follow_up_sub_loop`（YES→re-speak qty prompt 不計 attempts / NO→`(False, cancel_notice)` skip 該商品）。對齊 user 字面：「回原鏈路 + 重印該鏈路 entry prompt（非亂答 clarify）」。

**keyword**（獨立集 `KEYWORDS_L4_C_CONFIRM_*`，不走 `classify_intent(mode="l4_service")`——避免影響仍用該 mode 的 caller）；NO 必先 check。

**inverse 對稱**：
| | cancel_confirm | service_confirm |
|---|---|---|
| Timeout | 6s | 24s |
| YES 語意 | 取消(True) | 繼續("yes") |
| NO 語意 | 繼續(False) | 取消("no") |
| silent → | 取消 | 取消 |

- **How to apply**：新客服進入點用 `service_confirm` 不 inline；改 timeout 動 `L4_C_CONFIRM_TIMEOUT` 一處（template 用 `{seconds}` 自動更新文案）；改 keyword 動 `KEYWORDS_L4_C_CONFIRM_*` 且 NO 先 check；不要改 `mode="l4_service"` classify_intent 分支（仍給 `_dialog_unclear_final_confirmation` 用）。

---

## Confirm 亂答 / timeout default 必須保守

**Rule**：確認類子狀態（被問「正確嗎？」「要繼續嗎？」）的 timeout / 亂答 / 達 unclear 上限等 ambiguous 結果，一律 default「取消 / 不繼續」；只有顧客**明確答應**（YES keyword / 終端 "1" / "對"）才推進。

**Why**：2026-05-26 `9309059` 修錯——`_dialog_checkout_confirm` 曾把 unclear cap default 設 `return True`（進 L4），理由「跟 timeout 一致」，結果顧客亂答 3 次自動扣款（影響錢包）。timeout default 也翻成 cancel（直接 Enter 不該視為同意付款）。

**How to apply**：confirm-like sub-state 的 ambiguous answer 預設 negative（保守 / 不推進 / 回安全狀態）；timeout 跟 unclear cap 不要為「邏輯對稱」一起設成 YES。**例外**：純廣播通知無 yes/no 抉擇不適用；C-2 自動結帳（主迴圈 timeout 沒講結帳 → 推測想結帳離開）是另一層流程，與 confirm 內 unclear 性質不同。

---

**相關 reference**：[sales-tts-ux.md](sales-tts-ux.md)（TTS / 計時倒數 / UX 過場）/ [myprogram-threading-paths.md](myprogram-threading-paths.md)（S6 非阻塞 input）/ [sdd.md](sdd.md)（改 sales code 走 SDD）/ [CLAUDE.md](../../../../CLAUDE.md)
