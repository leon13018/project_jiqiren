# Sales 對話狀態機 / 跨層流程設計

> **🎯 何時讀本檔**：要改 sales 對話狀態機 / 跨層流程（L2 / L3 / L4、qty followup、cancel / service confirm、C-2、錢包保守邏輯）。

## 目錄
- C-2 三選一設計
- L4 wall-clock budget
- 跨層 cancel_confirm 子狀態
- 服務客服 service_confirm 統一 helper
- Confirm default 必須保守
- 無效數量重問鏈 invalid_qty_reask（超上限 / 數量為 0）

myProgram sales 對話層（L2/L3/L4 + qty followup + 各 confirm 子狀態）的領域設計決策。改 sales code 須對照本檔，避免推翻已對齊的 UX / 錢包保守 / 跨層 confirm 等決定。

---

## C-2 三選一設計

**背景**：c2 二元 yes/no 有 UX bug——顧客講「不要」歧義（「不要結帳、繼續逛」vs「不要整單」）被當「拒絕整單」清 cart，違反顧客錢包預期。重構為**三選一明確意圖**（無歧義詞 fall through）：
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
- **L3 reject 短詞 = 結帳意圖（非取消）**：「沒有了 / 沒了 / 不了 / 不要 / 不用」等短詞在 L3 normal mode（`classify_intent` mode="normal"）歸**「結帳」**（不追加→去結帳），不走 cancel_confirm；只 L2/L4 當拒絕。L3 僅 `_KEYWORDS_REJECT_L3_STRICT`（「我不要了 / 不想買了 / 取消購買 / 退出」等明確退出詞）才算取消。判「沒有了」走哪條 path 依此。

### CHECKOUT keyword + silent timeout 都經 confirm
- **CHECKOUT keyword** → 經 `_dialog_checkout_confirm`（speak「您即將結帳，總共…正確嗎？」12s + 5 次亂答容忍）：給「最後確認金額」機會防多商品累加誤判。
- **silent 6s timeout** → 同樣 call `_c2_checkout_via_confirm`（與 CHECKOUT path 一致）：silent customer 也應有確認金額機會，且「6 秒後自動結賬」寬鬆解讀為「啟動結帳流程（含 confirm）」。
- **keyword family**：CONTINUE/CANCEL/CONFIRM_YES + REJECT 同類一次掃（FP 防護故意不加「還要」「加買」）；sentinel `cancel_to_l1`（`_dialog_checkout_confirm` 內 cancel_confirm YES → 3 個 caller 識別後直 call `_dialog_exit_a` 退 L1，免兩輪 YES）；合成 ack voice（`L3_C2_CONTINUE_ACK` / `*_CANCEL_DECLINED_RESUME` 避免顧客失上下文）。
- **reuse 既有 helper**（零新 architecture）：`_dialog_exit_a`（取消退出）/ `_dialog_checkout_confirm`（C-1 confirm）/ `_dialog_main_loop`（重入）。

---

## L4 wall-clock budget（v3 雙計時器）

兩個獨立 wall-clock 計時器，與子鏈路狀態解耦（權威值見 `resources/specs/L4_v3_dual_timer_spec.md` + `timing.py`/`l4.py`）：

| 計時器 | 常數 | 秒 | 行為 |
|---|---|---|---|
| 總 budget | `L4_TOTAL_BUDGET` | 36 | 耗盡 → `_l4_exit_d_forced`（speak `L4_D_FORCED_EXIT` + clear cart 退 L1） |
| QR 刷新循環 | `L4_QR_REFRESH_INTERVAL` | 12 | 每循環開頭**無條件**重印結帳區塊 + 重 speak `L4_REMIND_PROMPT`（不論顧客是否回應）|

`36 = 12 × 3`，總 budget 期間共 3 個循環；進 L4 的 entry prompt + 結帳明細 = 第 1 次刷新。**改 budget 須維持 `L4_TOTAL_BUDGET` 為 `L4_QR_REFRESH_INTERVAL` 整數倍**（`test_constants` 守此不變量、倒數視覺要對齊循環邊界）。
```python
now = time.monotonic()
budget_deadline = now + L4_TOTAL_BUDGET          # 36s
cycle_deadline  = now + L4_QR_REFRESH_INTERVAL   # 12s
while True:
    now = time.monotonic()
    if budget_deadline - now <= 0: return _l4_exit_d_forced(...)        # budget 優先
    if cycle_deadline  - now <= 0:                                       # 循環刷新（不動 budget）
        _l4_print_entry_detail(...); speak(L4_REMIND_PROMPT)
        cycle_deadline = time.monotonic() + L4_QR_REFRESH_INTERVAL; continue
    response = read_customer_input(timeout=min(cycle_remaining, budget_remaining))
    if response is None: continue                                        # silent → 下次由 cycle 判刷新
    result = _l4_dispatch_response(...)
    if isinstance(result, tuple): return result
    if result is None:                                                   # 客服 yes 繼續 → reset 兩計時器
        _l4_print_entry_detail(...); speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
        now = time.monotonic(); budget_deadline = now+L4_TOTAL_BUDGET; cycle_deadline = now+L4_QR_REFRESH_INTERVAL
    continue                                                             # "ack" → 不動任何計時器
```

### 鏈路行為矩陣
| 顧客動作 | 行為 | 計時器影響 |
|---|---|---|
| 終端 "s" | 鏈路 A → `L4_A_PAY_SUCCESS` + `do_action(ACTION_L4_PAY)` → L5 | n/a（退出）|
| 等待安撫 NLU（好/嗯/等等） | speak `L4_ACK_GENTLE` | **完全不影響** |
| 亂答（想一下/結帳/商品/無法判斷） | speak `L4_UNCLEAR_NOTICE`「不好意思我聽不太懂」 | **完全不影響** |
| 拒絕 NLU | `cancel_confirm` 6s gate → YES=`_l4_exit_b` / NO=`CANCEL_DECLINED_NOTICE` continue | 子狀態期間**暫停**、退出後**補償** |
| 客服 NLU | `_service_confirm` 24s → YES=reset 兩計時器 + re-speak entry / NO=清 cart 退 L1 / "s"=L5 | 子狀態期間暫停；YES 改 **reset**（覆蓋補償）|
| silent | 下次 iteration 由 `cycle_deadline` 判是否刷新 | 不影響 budget |
| budget 耗盡 | `_l4_exit_d_forced` + clear cart 退 L1 | — |

- **子狀態暫停 / 補償**：進 `cancel_confirm` / `service_confirm` 前記 `paused_at`，退出後兩 deadline 都 `+= 實際耗時`（凍結子狀態時間，避免子狀態吃掉付款 budget）。
- **客服 yes 為何 reset 而非補償**：讓顧客感受「客服處理完、QR 流程 fresh 重新開始」，reset 覆蓋補償。
- **How to apply**：ack / 亂答 path 不動任何計時器；QR 刷新**無條件**每 12s（非「沒回應才提示」）；客服 yes reset、cancel NO 補償；**不要加新 counter**（unclear_count / loop_count 等已廢除）。

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

**Why**：曾把 `_dialog_checkout_confirm` 的 unclear cap default 設 `return True`（進 L4），理由「跟 timeout 一致」，結果顧客亂答 3 次自動扣款（影響錢包）。timeout default 也翻成 cancel（直接 Enter 不該視為同意付款）。

**How to apply**：confirm-like sub-state 的 ambiguous answer 預設 negative（保守 / 不推進 / 回安全狀態）；timeout 跟 unclear cap 不要為「邏輯對稱」一起設成 YES。**例外**：純廣播通知無 yes/no 抉擇不適用；C-2 自動結帳（主迴圈 timeout 沒講結帳 → 推測想結帳離開）是另一層流程，與 confirm 內 unclear 性質不同。

---

## 無效數量重問鏈 invalid_qty_reask（2026-06-09 加；2026-06-09 一般化）

**背景**：兩類無效數量舊行為各自出錯——
- **超上限**（> `MAX_QTY_PER_ITEM`）：舊行為直接 cap 成上限加入（顧客「343434」被當 50 瓶），違反本意。
- **數量為 0**（「紅茶 0 杯」）：`cart.add_item(.,0)` silent skip 但 caller 仍 `added_count+=1` → **假性「已加入購物車」**（cart 沒東西卻播已加入）。

重構為**統一重問鏈**——問到合法數量才加入。原 `over_limit_reask` 一般化為 `invalid_qty_reask`，`pending` 從 `list[str]` 改為 **`dict[str, str]`**（`product → reason`，`reason ∈ {"over_limit", "zero"}`，dict 保插入序）。loop 系統值（12s budget / 最多 2 reset / 客服暫停補償 / 否定→二選一 6s / 控制往上傳）**完全沿用**，唯一差異：**prompt 依 reason 分組** + `_apply_quantities` 重答時重新分類 reason。

**Helper `myProgram/sales/states/_invalid_qty_reask.py`**：
```python
invalid_qty_reask(pending: dict, cart, speak, print_terminal, read_customer_input, speak_and_wait=None) -> str
#   "resolved" | "reenter_timeout" | "reenter_cancel" | "exit_l1"
invalid_qty_cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> str  # "cancel_overlimit" | "exit"
```

- **即時提交模型（無 staging）**：有效數量立即 `add_item` + `del pending[product]`，`pending` 只含仍無效商品 → 自然「保留已 OK、只丟無效」。
- **prompt 依 reason 分組**：zero 句「不接受冰紅茶0瓶這種數量…」+ over 句「…最多只能選購 50 瓶」；混合 reason（同句既有 0 又超量）→ 兩句串接成一個 speak。over 句 single/multi 由 over_products 數量決定（非 total pending）。
- **重答重新分類**：`_apply_quantities`→`_classify_into_pending`：合法→add+del；仍 0→reason=zero；仍超量→reason=over_limit。任一商品仍 pending → 觸發 reset（最多 2 次）。
- **12s budget + 最多 2 reset**：亂答 / 沉默**不** reset。判定序 否定→客服→數量→亂答。
- **客服**：走既有 `_service_confirm`，期間 deadline 暫停 + 補償（對齊 L4 pattern）。
- **否定 → 二選一 `invalid_qty_cancel_confirm`（6s）**：CONTINUE（取消這些商品繼續）**先於** EXIT（退出）check，保守 default `cancel_overlimit`（保 cart）——對齊「confirm ambiguous 保守」鐵則。文案已中性化（「取消這些商品」涵蓋 zero+超量，不再只說「超量」）。
- **偵測點（qty==0 funnel，鏡像超量）**：
  - **Pass1**（`resolve_and_add_products`）：直接數量分類——in-range 即加 / `qty==0`→`invalid_pending[p]="zero"` / 超量→`"over_limit"` / 缺數量排 missing / at-cap 保留舊 skip → Pass1.5 合併重問（**先於** missing）→ Pass2 缺數量追問（其 0 / 超量答案 funnel 進單商品 `invalid_qty_reask`）。情境3「無效先於缺數量追問」由此序保證。
  - **`parse_products` 透出明確 0**：`_parse_quantity_in_window` 視窗有阿拉伯數字但全為 0 → 回 `0`（非 `None`「缺數量」），對齊 `nlu.parse_quantity` B16——**否則 Pass1 `qty==0` 偵測點不可達**（「紅茶0」被當缺數量走追問，spec 前提修正 commit f1739ba）。
- **訊號往上傳**：`resolve_and_add_products` 與 `_qty_follow_up_sub_loop` return 第 3 元素 `control`；3 個 dialog caller 解 3-tuple——`exit_l1`→`_dialog_exit_a` 退 L1；`reenter_*`→speak「prefix+當前層 entry」continue（prefix = timeout / cancel 兩種）。reenter **不**觸發 `do_action(L3)` transition（邊緣重入路徑）。
- **at-cap 例外**：`remaining<=0`（已點滿）保留既有「無法再加」skip，不進重問鏈。
- **負數 out-of-scope**：`parse_quantity` 用 `re.findall(r"\d+")`，負號被忽略（「-1瓶」解成 1 正常加入）；STT 亦產不出負號 → 不加負號偵測（YAGNI）。

> 規格：`resources/specs/invalid_qty_reask_2026-06-09_spec.md` + plan（base：`over_limit_reask_2026-06-09_spec.md`）。
