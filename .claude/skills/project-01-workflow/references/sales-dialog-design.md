# Sales 對話狀態機 / 跨層流程設計

myProgram sales 對話層（L2/L3/L4 + qty followup + 各 confirm 子狀態）的領域設計決策。日後改 sales code 須對照本檔，避免推翻已對齊的 UX / 錢包保守 / 跨層 confirm 等決定。

> 每個 section 對應一份原始 memory，忠實搬運其全部設計細節 + Why + 歷史演進。**矛盾以該 section 內最新註記為準**（例：L4 budget 現況為 30s，非舊版 60s）。

---

## C-2 三選一設計（c2-three-way-design）

**Pi demo 2026-05-28 揭示 c2 二元 yes/no 子狀態 UX bug**：顧客講「不要」歧義（「不要結帳、繼續逛」vs「不要整單」）被 `KEYWORDS_CONFIRM_NO` 命中當「拒絕整單」清 cart。違反顧客錢包 expectation。重構為**三選一明確意圖**：

```
[語音] 請問您想要繼續選購商品、結賬還是取消購買，如 6 秒內未答復將進行結賬。
```

**Why:** 二元 yes/no 強迫顧客把複雜意圖（繼續逛 / 結帳 / 取消）映射到單一維度，必有歧義詞 fall through 到錯 path。三選一無歧義詞。對應 [conservative-confirm](#confirm-亂答--timeout-default-必須保守confirm-default-must-be-conservative) ：顧客錢包不該因模糊詞被默默操作。

**How to apply:** 未來其他 dispatcher 場景如有「拒絕一詞涵蓋多種意圖」風險，第一反應應該是拆三個 path 而非「補強 keyword list」。

### 三選一行為對應表

| 顧客動作 | 對應 helper | 行為 |
|---|---|---|
| **CANCEL keyword**（「取消」/「取消吧」/「幫我取消」...） | `_dialog_exit_a` | 清 cart + speak `L3_REJECT_THANKS` + return `("L1_via_subroutine_a", 0)` 退出 |
| **CONTINUE keyword**（「繼續」/「繼續選購」/「選購商品」...） | `_dialog_main_loop` | **不清 cart**，重入 dialog 主迴圈讓顧客繼續加單 |
| **CHECKOUT keyword**（「結」/「結賬」/「直接結賬」...） | `_c2_checkout_via_confirm` | 經 `_dialog_checkout_confirm` 確認明細 → "yes" 進 L4；非 yes 清 cart + 重入 |
| **6s timeout（silent）** | `_c2_direct_checkout` | **直接 L4 跳過 confirm**（user 字面 promise「6 秒內未答將進行結賬」） |
| 亂答（不在三組 keyword） | 既有 silent 倒數 | 第一次 speak「請說『繼續』、『結賬』或『取消』」，後續 silent；不重置 deadline |

**單字 token 用 strict-short**（`KEYWORDS_C2_*_STRICT_SHORT`）：「結」「繼續」「取消」單字嚴格相等才命中，防 substring 誤命中「結束」/「繼續努力」/「取消會議」等。

### 為何 silent timeout 跳 confirm 而 CHECKOUT keyword 經 confirm

**Pi demo 後 user AskUserQuestion 對齊（2026-05-28 原版）**：

| 場景 | 行為 | 理由 |
|---|---|---|
| **顧客主動講「結賬」keyword** | 經 `_dialog_checkout_confirm`（speak「您即將結帳，總共...正確嗎？」12s + 5 次亂答容忍）| user 答 B：給「最後確認金額」最後機會（防多商品累加誤判） |
| **顧客 silent 6s timeout** | 直接 L4，跳過 confirm | user prompt 字面 promise「6 秒內未答將進行結賬」 — silent customer 預期被結帳，不該再罰 confirm timeout 12s 清 cart |

**對應 helper 拆分**：
- `_c2_direct_checkout(speak, do_action)` — silent timeout 用
- `_c2_checkout_via_confirm(...)` — CHECKOUT keyword 用

### 2026-05-29 反轉：silent timeout 也合流到 confirm path

**commits `87a44bb` → `3a94fa8`**：Pi demo 後 user 反饋 silent timeout 直接 L4 仍突兀（缺 ack cue + 跳過確認），且文案「6 秒後自動結賬」可寬鬆解讀為「自動啟動結賬流程（含 confirm）」非「跳過所有確認直接扣款」。

**新行為（最終）**：
- `_c2_direct_checkout` 函數**刪除**（dead code 移除）
- `_dialog_c2_second_stage` 內 silent timeout / 倒數歸零 → 改 call `_c2_checkout_via_confirm`（合流到 CHECKOUT keyword path）
- 顧客體驗：silent timeout → 進 confirm 子狀態「您即將結帳，總共...正確嗎？」→ 顧客「對」進 L4；非 yes 清 cart 重入 dialog
- 對應 31 個既有 test fixture 更新（append「對」response）

**Why 反轉**：silent customer 也應有「確認金額明細」機會，跟 CHECKOUT keyword path UX 完全一致；user 字面 promise 寬鬆解讀無衝突。

**文案同期更新（commit `a7d225e`）**：`L3_C2_WARNING_TEMPLATE` 從「請問您想要繼續選購商品、結賬還是取消購買，{seconds} 秒後自動結賬。」改成「請問您想要繼續選購商品、結賬還是取消購買？{seconds}秒後將自動結賬。」（標點 + 加「將」+ 去空格）

### 2026-05-30 後續：keyword 大幅擴 + cancel-to-l1 path 直退 L1

**commits `db1871e` + `5dc249f` + `83b2e24` + `c118384` + `4776cb1` + `b1d1614` + `973ebd2`** — Pi demo 連續暴露 NLU 與 flow 問題，多輪修補：

**Keyword family 大幅擴**（同類路徑一次掃，見 fix-one-path-sweep-related memory）：
- `KEYWORDS_C2_CONTINUE`：既有 5 個 → 加 19 繁體 + 5 簡體（繼續 X / 再 X / 想再 X family）；FP 防護故意不加「還要」/「我還要」（會吃 CHECKOUT）/「加買」（FP「不想加買」）
- `KEYWORDS_C2_CANCEL`：既有 5 個 → 加 5 繁 + 5 簡（取消 X / 不想要了 family）
- `KEYWORDS_CONFIRM_YES`：加「對哦」「對呢」「對啊」+ 簡體（「對 + 語助詞」sweep；「沒錯/正確 + 語助詞」既有 substring 已 cover）
- `_KEYWORDS_REJECT`：L3 mode 加「不需要」（cover 不需要 / 我不需要 / 不需要了）+「沒有額外」（cover「沒有額外需要購買的」）
- `_KEYWORDS_REJECT_L3_STRICT`：加「不要買了」「不想買」+ 簡體（避免 mode="normal" 通用 substring「不要」/「不想」誤判為「結帳」）

**Flow 修正 — cancel_to_l1 sentinel**（commit `5dc249f`）：
- `_dialog_checkout_confirm` 內 cancel_confirm YES 原 return `"no_explicit"` → caller `_handle_checkout_confirm_result` clear cart + speak `L3_CHECKOUT_REJECT_CLEAR_NOTICE`「請告訴我您想買什麼」→ 回 main loop → user 再答「不了」又 cancel_confirm（兩輪 YES 才退 L1）
- **修法**：新 sentinel `"cancel_to_l1"`；3 個 caller（main_loop 結帳分支 / `_dialog_dispatch_inner_l3` / `_c2_checkout_via_confirm`）識別後直 call `_dialog_exit_a` 退 L1
- 8 個 cancel_confirm 觸發點掃描分類確認此唯一 bug — 其他 7 處 YES 已正確退 L1

**UX 合成 voice**（commits `4776cb1` + `b1d1614` + `973ebd2`）：
- `L3_C2_CONTINUE_ACK = "好的，請繼續選購，請問還要買什麼呢？"`（合成 ack + reask；CONTINUE 後回 main loop 不重 speak entry，顧客失上下文 → 沉默 → 又被 DYC_TIMEOUT 抓回 C-2 → 修補）
- `L2_CANCEL_DECLINED_RESUME = "好的，繼續為您服務，請問需要購買什麼東西嗎？"` / `L3_CANCEL_DECLINED_RESUME = "好的，繼續為您服務，請問還有額外需要購買的嗎？"`（cancel_confirm NO 合成 DECLINED + entry 重啟，避免顧客失上下文）

詳見對應 commit messages。

### reuse 既有 helper（沒新增 architecture）

- `_dialog_exit_a` — 既有「鏈路 A 拒絕退出」helper，cart 非空時 speak `L3_REJECT_THANKS` + clear cart + return L1。**完全符合「取消購買」需求**，零新 code
- `_dialog_checkout_confirm` + `_handle_checkout_confirm_result` — 既有 L3 C-1 confirm 機制，CHECKOUT keyword path reuse
- `_dialog_main_loop` — 既有「主迴圈 core」helper，CONTINUE path 重入 dialog 用

只新增 2 個小 helper（`_c2_direct_checkout` 4 行 / `_c2_checkout_via_confirm` 20 行）+ keywords / timing 常數。

### Cap retry 嘗試三輪 revert

c2 重構**之前** user 還對 cap retry sub-loop 嘗試 3 種行為（cancel / reprompt / block forever），每輪都 user 試後不滿意，最後 **revert 回 9931605 state**（保留原版 cap retry timeout 預設加 1 行為）。教訓：cap retry 的「user 答錯後該怎麼辦」設計空間複雜，需要更深 user expectation 對齊；本 session 沒處理，待後續迭代。

### 改動規模（c2 重構本身）

- 5 個檔（keywords.py / timing.py / l3_text.py / l2_l3_dialog.py / test_states.py）
- +265 / -100 行
- 4 個既有 c2 tests 改寫 + 1 個新 strict-short 「結」test
- Tests 264 → 265
- commit `a1612d5`

---

## L4 30s wall-clock budget 設計（l4-ack-wallclock-budget-design）

**架構（2026-05-30 commit `0090786` 二次重構）：** L4 從原本 60s + 雙計數器 + 4 階段語氣 + final confirmation + 獨立 service timeout 大幅簡化為**單一 30s wall-clock budget**。

### 當前設計（簡化版）

```python
deadline = time.monotonic() + L4_TOTAL_BUDGET  # 30s
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return _l4_exit_d_forced(...)  # 清 cart 退 L1
    response = read_customer_input(timeout=min(L4_PROMPT_INTERVAL, remaining))  # min(12, remaining)
    if response is None:
        speak(L4_REMIND_PROMPT)  # 「請您掃碼付款」每 12s 重提示（不重置 budget）
        continue
    result = _l4_dispatch_response(...)
    if isinstance(result, tuple): return result
    if result is None:
        # 客服繼續 → re-speak entry + reset budget
        _l4_print_entry_detail(...)
        speak(L4_ENTRY_PROMPT_TEMPLATE.format(total=total))
        deadline = time.monotonic() + L4_TOTAL_BUDGET
    continue  # "ack"（等待安撫 / cancel_confirm NO / 亂輸入）→ 不重置 budget
```

### 鏈路行為

| 顧客動作 | 行為 |
|---|---|
| 終端 "s" | 鏈路 A → `L4_A_PAY_SUCCESS` + `do_action(ACTION_L4_PAY)` → L5 |
| 等待安撫 NLU（「好/嗯/等等」） | `L4_ACK_GENTLE` + continue 不重置 budget |
| 拒絕 NLU | `cancel_confirm` 6s gate → YES = `_l4_exit_b` / NO = `CANCEL_DECLINED_NOTICE` + continue 不重置 budget |
| 客服 NLU | 進 `_service_confirm` helper（24s 一次性決策；見 [服務客服 confirm](#服務客服-confirm-統一-helperservice-confirm-unified)）→ YES = re-speak entry + reset 30s budget / NO = 清 cart 退 L1 / "s" fast path = L5 |
| 想一下 / 結帳 / 商品 / 無法判斷 | speak `L4_UNCLEAR_NOTICE`「不好意思我聽不太懂」+ continue **不重置 budget**（user 反饋簡化版） |
| silent 12s 沒回應 | speak `L4_REMIND_PROMPT`「請您掃碼付款」+ continue **不重置 budget**（每 12s 重提示） |
| budget 耗盡（30s） | `_l4_exit_d_forced` speak `L4_D_FORCED_EXIT` + clear cart 退 L1 |

**user 字面 design 哲學**：「就單純 budget 計時，沒結賬的話，每 12 秒會重複提示一次，如果亂輸入不會重置 budget，只會印提示給用戶系統無法判斷」

### 從舊版移除（user 反饋過度設計）

- `loop_count`（D 鏈路 4 階段語氣 6 次循環機制：中性/柔/中度/警告）
- `unclear_count`（E 鏈路達 3 自動進客服機制）
- `_l4_final_confirmation`（達上限後「1=取消 / 2=繼續」18s 子狀態）
- `L4_SERVICE_TIMEOUT=60s` 獨立（客服改 24s，見 [服務客服 confirm](#服務客服-confirm-統一-helperservice-confirm-unified)）
- `L4_D_VOICE_NEUTRAL/GENTLE/MODERATE/WARNING` 4 階段文案
- `L4_D_FINAL_PROMPT` / `L4_E_CLARIFY` / `L4_E_AUTO_SERVICE` 文案

### 從舊版保留

- `L4_TOTAL_BUDGET`（值改 60 → 30）
- `L4_D_FORCED_EXIT`（budget 耗盡 speak）
- `L4_ACK_GENTLE`（等待安撫）
- `L4_ENTRY_PROMPT_TEMPLATE`「您的總金額是 N 元（已享全品項九折優惠），請您掃碼付款」
- `L4_A_PAY_SUCCESS` / `L4_B_CANCEL_THANKS`
- `L4_QR_MOCK_HINT`

### 從舊版新增

- `L4_PROMPT_INTERVAL: int = 12`（每 12s silent 重提示間隔）
- `L4_REMIND_PROMPT: str = "請您掃碼付款"`（短促中性提示）
- `L4_UNCLEAR_NOTICE: str = "不好意思我聽不太懂"`（亂答提示，對齊 L2/L3 B-1 風格）

### 設計沿革（兩次重轉）

| 階段 | commit | 設計 |
|---|---|---|
| v1 方案 A（2026-05-26） | `0016e23` | ack 重設 6s timer 不影響預算 — user 一度確認 |
| v1 方案 B（同日反轉） | `0236879` | wall-clock 60s 全程預算；ack 不重置 — 防 spam 無限拖延 |
| **v2 簡化（2026-05-30）** | `0090786` | 30s 單一 budget + 12s 重提示 + 廢除 loop/unclear/final 全部過度設計 |
| v2.1 客服 YES reset | `bcc2920` | 主 loop 收到 `None`（客服繼續唯一語意）→ re-speak entry + reset 30s budget（v2 漏修） |

**為何 v2 簡化（user 反饋）**：60s + 多層計數機制過度工程，Pi demo 顧客 UX 並不感受到 4 階段語氣差異，反而「亂輸入幾次就被自動進客服」突兀。簡化為「就單純 budget」更符合直覺：顧客有 30s 思考 + 每 12s 一次提醒 + 亂答無懲罰只印 unclear。

### How to apply

- 編 L4 主迴圈 → 嚴守單一 30s budget，所有非 "ack"/`None` path 都不重置 budget
- 加新「亂答 path」 → speak `L4_UNCLEAR_NOTICE` + continue（對齊 dispatcher 設計）
- 客服繼續 → 一定要 re-speak entry + reset budget（v2.1 補修教訓）
- 不要加新 counter 機制（unclear_count / loop_count / attempts 等都已廢除）

---

## 跨層 cancel_confirm 子狀態（cancel-confirm-cross-l）

**2026-05-29 落地的跨層 cancel 架構**（commit `1679239` + `83e77bc`）：解 user 訴求「L2~L4 任何狀態階段都支援『不買了』『取消交易』等口語 → 6s 確認後退 L1」。

### 設計（一句話）

跨 L2/L3/L4 任何 reject 意圖偵測點 → 進新 6s confirm 子狀態 → YES/timeout 取消、NO 繼續。

### 架構

**新模組 `myProgram/sales/states/_cancel_confirm.py`**

```python
def cancel_confirm(speak, read_customer_input, speak_and_wait=None) -> bool:
    """跨層共用 cancel confirm 6s wall-clock budget 子狀態。

    Returns:
        True  — 確認取消（YES keyword 命中 / silent timeout / 亂答耗盡 budget）
        False — 顧客 NO（NO keyword 命中）
    """
```

設計細節：
- 6s wall-clock budget pattern（CANCEL_CONFIRM_TIMEOUT=6.0）
- 用 `speak_and_wait` 確保 deadline 從 TTS 播完起算（見 [speak-and-wait 架構](sales-tts-ux.md#speak_and_wait-架構--ttsworker-設計speak-and-wait-architecture)）
- NO check 先過 YES check（避免「不要取消」誤命中 YES「取消」substring）
- silent / 倒數歸零 → True（取消，user 字面 promise「6 秒後系統將自動取消」）

**新 helper `is_cancel_intent(response: str) -> bool`**

簡單 wrapper：用 `mode="l4"` 走 classify_intent，認「拒絕」intent（L3 strict mode 反而會漏掉「不要」「不用」等短詞，跨層 cancel 用 l4/l2 mode 抓得更廣）。

**新 keyword（`keywords.py`）**

```python
KEYWORDS_CANCEL_CONFIRM_YES: list = [
    "是的", "沒錯", "沒錯的",
    "我想取消", "是的我想取消", "取消吧", "給我取消",
    "取消這次", "取消這次交易", "取消交易",
]
KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT: list = ["是", "對", "取消"]

KEYWORDS_CANCEL_CONFIRM_NO: list = [
    "不要取消", "不想取消", "別取消", "別給我取消啊",
    "繼續交易", "我想繼續交易", "給我繼續交易",
]
KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT: list = [
    "否", "不", "不要", "不想", "我不想", "別", "繼續",
]
```

**新文案（`shared.py`）**

```python
CANCEL_CONFIRM_PROMPT: str = "您是否想取消這次交易？6 秒後系統將自動取消"
CANCEL_CONFIRMED_NOTICE: str = "好的，已為您取消這次交易"
CANCEL_DECLINED_NOTICE: str = "好的，繼續為您服務"
```

**NLU 擴充（`nlu.py`）**

`_KEYWORDS_REJECT_L3_STRICT` + `_KEYWORDS_REJECT` 補「我想取消交易」「取消交易」「我要取消交易」「退出交易」（user 列表未覆蓋既有 NLU 的詞）。

### 8 個 explicit cancel_confirm gate（commit `1679239` + `83e77bc`）

| Gate | 位置 | 處理 reject 後行為 |
|---|---|---|
| L2/L3 主等待 | `_dialog_main_loop` | reject → cancel_confirm yes → 退 L1；no → 重 prompt + continue |
| L2 inner silence | `_dialog_dispatch_inner_l2` | 同上 |
| L3 inner silence | `_dialog_dispatch_inner_l3` | 同上 |
| L3 checkout confirm | `_dialog_checkout_confirm` | response is cancel intent → cancel_confirm gate |
| L4 主 dispatch | `_l4_dispatch_response` | 同 L2/L3 主等待 |
| L3 unclear final | `_dialog_unclear_final_confirmation` | 同上 |
| L4 final confirm | `_l4_final_confirmation` | 同上 |
| L4 service mode | `_l4_service_mode` | 兩個分支（`退出交易` + `拒絕` fallback）都 gate |

### 不 cover 的 2 個例外

**qty_followup（user 接受現狀）**

`_l2_l3_qty_followup.py` line 157-158 reject path 仍直接 `return False, notice_str` — 顧客在「您要幾瓶？」追問內喊取消，會 fall-through 到 main loop 由 caller 重 prompt，顧客再喊一次才觸發 cancel_confirm。

**Why 不 cover：** Return type 是 `tuple[bool, str | None]`（cancel_notice 機制），propagate「整單取消」sentinel 到 caller chain 需要 invasive return type change，影響 100+ test fixture。**Karpathy avoid premature abstraction + invasive change** + user 接受 UX trade-off（顧客被迫喊兩次但仍能取消）。

**C-2 三選一 CANCEL keyword（保留快速 path）**

`KEYWORDS_C2_CANCEL` 直接走 `_dialog_exit_a` 清 cart + 退 L1 — **不走 cancel_confirm**。

**Why 保留快速 path：** C-2 是「已警告 6s 倒數中」子狀態（顧客已位於 warning context），CANCEL keyword 命中再加 confirm 6s = 罰 12s 違反 prompt 字面 promise + UX 冗長。User 拍板 keep。

### 13 個 function signature 加 `speak_and_wait=None`

跨 callback chain propagation：`logic.run` → `run_dialog` / `run_l4` → 內部 13 個 helper。Default `None` fallback to `speak`，向後相容既有 test。

### Tests 影響

- 9 個新 cancel_confirm helper unit test
- 5 個新 NO path tests（L2 / L3 / L4 / L2-B3 silence / cross-L phrase）
- 2 個新 checkout_confirm cancel tests
- 1 個新 NLU test
- 6 個新 inner state path tests（unclear_final / l4_final / l4_service x2 各 YES/NO）
- 3 個既有 reject test 修補
- 2 個 L4-C 既有 test 修補（fixture 加 confirm yes）

從 265 → 288 PASS（+23 tests）

---

## 服務客服 confirm 統一 helper（service-confirm-unified）

**架構（2026-05-31 commit `92fedb6` + `46c0b52` + `5c9fb1e`）：** 所有層的「顧客講客服進入」都進統一 helper `_service_confirm` 子狀態，對齊 [cancel_confirm](#跨層-cancel_confirm-子狀態cancel-confirm-cross-l) 風格但語意 inverse。

### Helper 簽名與行為

**位置：** `myProgram/sales/states/_service_confirm.py`（跟 `_cancel_confirm.py` 對稱）

```python
def service_confirm(speak, print_terminal, read_customer_input, speak_and_wait=None, *, allow_scan: bool = False) -> str:
    """共用客服 confirm 24s 子狀態。
    Returns: "yes" | "no" | "scan" (僅 allow_scan=True)
    """
```

**子狀態行為**：
1. `print_terminal(SERVICE_PHONE)` 印客服電話
2. `speak_and_wait(L4_C_CONFIRM_PROMPT_TEMPLATE.format(seconds=24))`「請問是否繼續交易？24秒後將自動取消交易。」
3. `deadline = monotonic() + L4_C_CONFIRM_TIMEOUT`（24s 一次性決策；wall-clock budget）
4. 迴圈讀顧客 input：
   - silent / 倒數歸零 → `return "no"`（caller 清 cart 退 L1）
   - NO keyword（先 check，防「不繼續」substring 含「繼續」誤命中 YES）→ `return "no"`
   - YES keyword → `return "yes"`（caller 回原鏈路）
   - 終端 "s"（僅 `allow_scan=True`）→ `return "scan"`（L4 caller fast path 進 L5）
   - 亂答 → `speak(L4_UNCLEAR_NOTICE)` continue（**不重置 24s budget**）

### 6 個進入點（caller 對應行為）

| Caller | allow_scan | YES 回原鏈路行為 | NO 退出行為 |
|---|---|---|---|
| `_l4_service_mode`（L4 主迴圈客服分支） | **True** | `return None` → main loop 重 speak L4 entry + reset 30s budget（見 [L4 budget](#l4-30s-wall-clock-budget-設計l4-ack-wallclock-budget-design)） | clear cart + return `("L1_via_subroutine_a", 0, 0)` |
| `_dialog_main_loop` 客服分支 | False | re-speak `L2_ENTRY_PROMPT`（cart 空）/ `L3_REASK`（cart 非空）+ continue | `return _dialog_exit_a(speak, cart)` |
| `_dialog_dispatch_inner_l2` 客服分支 | False | speak `L2_ENTRY_PROMPT` + return None | `return _dialog_exit_a(speak, cart)` |
| `_dialog_dispatch_inner_l3` 客服分支 | False | speak `L3_REASK` + return None | `return _dialog_exit_a(speak, cart)` |
| `_qty_follow_up_sub_loop` 客服分支 | False | re-speak `QTY_PROMPT_TEMPLATE.format(product, unit)`「請問 X 要幾 Y？」(回到 qty 追問鏈路初始提示，不計 attempts) | `return (False, cancel_notice)` skip 該商品 |

**對齊 user 字面**：「呼叫客服的**狀態鏈路** + 重印那個**鏈路的提示**」 — 鏈路提示是該鏈路初始 entry prompt（非亂答 clarify）。

### NLU 設計（KEYWORDS_L4_C_CONFIRM_*）

獨立 keyword 集（不走 `classify_intent(mode="l4_service")`，避免影響 `_dialog_unclear_final_confirmation` 等仍用該 mode 的 caller）：

```python
KEYWORDS_L4_C_CONFIRM_YES = ["是的", "好的", "繼續交易"]
KEYWORDS_L4_C_CONFIRM_YES_STRICT_SHORT = ["是", "好", "繼續"]
KEYWORDS_L4_C_CONFIRM_NO = ["不繼續", "不交易", "不要了", "不交易了", "不想了", "不想要了",
                            "取消交易", "取消吧", "幫我取消", "幫我取消交易"]
KEYWORDS_L4_C_CONFIRM_NO_STRICT_SHORT = ["否", "不要", "不", "取消"]
```

**NO 必須先 check（caller 端固定順序）**：防「不繼續」substring 含「繼續」strict_short 誤命中 YES。

### 設計沿革

| 階段 | commit | 變化 |
|---|---|---|
| L4 service mode 第一次重構（一次性 12s） | `2141e7e` | 從舊版「retry loop + cancel_confirm gate」改成一次性 12s 決策；新增 prompt template + 4 個 keyword 集 |
| L4 service-continue 補 reset budget | `bcc2920` | 主 loop 收到 `None` (客服 YES) → re-speak entry + reset 30s budget；對齊舊版漏修 |
| 抽 helper + L2/L3 對齊 | `92fedb6` | 新 `_service_confirm.py` 對外 export `service_confirm`；L4 + L2/L3 三個客服進入點都用 helper |
| qty followup 也對齊 | `46c0b52` | user clarify「L2/L3 數量詢問也要改」+ user 訂正用語「狀態鏈路 + 鏈路提示」 |
| timeout 12 → 24 | `5c9fb1e` | user 反饋「打電話需更充裕時間」；template `{seconds}` 模板自動更新文案 |
| sweep stale 12s comments | `168ef65` + `f9fc54d` | 純 docstring/comment 對齊 24s |

### 為何 inverse 對齊 cancel_confirm

| pattern | cancel_confirm | service_confirm |
|---|---|---|
| Prompt 字面 | 「您是否想取消這次交易？{seconds}秒後系統將自動取消」 | 「請問是否繼續交易？{seconds}秒後將自動取消交易。」 |
| Timeout | 6s | 24s |
| YES 語意 | 取消 (`True`) | 繼續 (`"yes"`) |
| NO 語意 | 繼續 (`False`) | 取消 (`"no"`) |
| silent → | YES (取消) | NO (取消) |

**設計對稱性**：兩個 helper silent 都歸於「取消」，但語意 inverse — cancel_confirm 是「主動觸發取消」確認；service_confirm 是「進入客服後是否繼續」確認。

### How to apply

- 新增客服進入點 → 用 `service_confirm` helper，不要 inline 重寫
- 改 timeout → 動 `L4_C_CONFIRM_TIMEOUT` 一處全 cover（template 用 `{seconds}` 模板）
- 改 keyword → 動 `KEYWORDS_L4_C_CONFIRM_*` 4 個 list；NO 必須先 check（caller 已固定順序）
- 不要改 `mode="l4_service"` classify_intent 分支（仍給 `_dialog_unclear_final_confirmation` 用）

---

## Confirm 亂答 / timeout default 必須保守（confirm-default-must-be-conservative）

確認類 confirm 子狀態（顧客被問「正確嗎？」「要繼續嗎？」等需要明確 yes/no 的場景）：

**rule：** timeout / 亂答 / 達 unclear 上限等「ambiguous」default 一律 return「取消 / 不繼續」，不要 default「視為確認 / 進下一步」。只有顧客**明確答應**（命中 YES keyword / 終端 "1" / 終端 "對"）才推進。

**Why:** 2026-05-26 commit `9309059` 修了這個錯誤。先前 `_dialog_checkout_confirm` 把 unclear cap default 設為 `return True`（進 L4），理由「跟 timeout 一致」。但這影響顧客錢包：顧客講「結帳」→ confirm「正確嗎？」→ 顧客亂答 / 沒答 → 系統默默扣款。使用者實機測到亂答 3 次自動進 L4 後反饋「明顯有錯誤」。timeout default 也一併翻成 cancel（顧客直接 Enter 不該被視為同意付款）。

**How to apply:**
- 寫 confirm-like sub-state 時，ambiguous answer 預設 negative outcome（保守 / 不推進 / 取消 / 回安全狀態）
- 只有顧客明確 YES 才進下一步
- timeout 跟 unclear cap **不要** 為了「邏輯對稱」就一起設成「視為 YES」 — 對 ambiguous 一律保守
- 對應 `_dialog_checkout_confirm` 跟未來類似 sub-state（如付款確認 / 訂單調整確認）都遵循

**例外（不適用此 rule）：**
- 純廣播 / 通知類 prompt（無 yes/no 抉擇）不適用
- L4 D 最終確認子狀態跟 dialog unclear final：default 也是 cancel（已對齊本 rule）
- C-2 自動結帳（在主迴圈 timeout 沒講結帳時）：保留 spec「兩段提示 → 自動進 L4」設計，那是另一層流程（cart 非空 + 顧客明確沒回應 = 推測想結帳離開），跟 confirm 內 unclear 性質不同

關聯：user-step-by-step-pace memory（這次違反「使用者沒明確指令就不要主動決定」— 把 unclear cap default 自行設成 True 是過度推測）。

---

**相關 reference**：[sales-tts-ux.md](sales-tts-ux.md)（TTS / 計時倒數 / UX 過場）/ [myprogram-threading-paths.md](myprogram-threading-paths.md)（S6 非阻塞 input 底層）/ [sdd.md](sdd.md)（改 sales code 走 SDD 流程）/ [CLAUDE.md](../../../CLAUDE.md)
