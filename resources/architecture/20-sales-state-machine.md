# 20 · Sales 對話狀態機（核心）

> `myProgram/sales/` — L0–L5 規則匹配點餐 / 收款對話狀態機。純單線程、無 threading / queue；嚴格不 import 廠商 SDK，所有對外動作經 callback 注入 → 可在 Windows 完整跑 pytest。以實際 code 為準（2026-06-21）。

> 規格書（「該怎樣」）在 `resources/plans/業務程式邏輯規劃/L0_共通.md` + `L1`–`L5.md`、`resources/specs/L4_v3_dual_timer_spec.md` 等；領域設計討論在 skill `reference/sales-dialog-design.md`。本檔描述「實作現況」。

---

## 1. 整體狀態機

### 1.1 facade 與調度

`logic.run(...)`（`logic.py`）只是 facade：組 callbacks dict + `cart_module.new_cart()`，建 `SalesMachine(...).run()`。真正調度在 `states/machine.py` 的 `SalesMachine.run()`——一個 `while True` 迴圈，持 `current` 字串 state key（`"l1"/"dialog"/"l4"/"l5"`）：

每輪迴圈：
1. 取 `state = self._states[current]`。
2. **進場 cart invariant fail-fast assert**：`entry_invariant=="empty"` → `_assert_cart_empty`；`"nonempty"` → `_assert_cart_nonempty`。違反立刻 raise（系統 bug 早爆）。
3. `self._emit(current)` → emit web display phase（見 §5）。
4. `result = state.run(self)`（呼叫對應 `states.run_*`，把字串 / tuple 結果包成 `Transition` dataclass）。
5. `result is None` → `return`（程式終止）。
6. `result.enter_hawk` 為 True → `self.enter_hawk_immediately = True`。
7. `current = result.next_state`。

各 `State` 類別把 `states.run_*` 的字串 / tuple 回傳值翻譯成 `Transition(next_state, enter_hawk)`——取代了舊 logic.py 的字串 tuple 魔法值。

### 1.2 各層語義 + return shape

| 層 | State 類別 | entry_invariant | `states.run_*` 簽名 / return |
|---|---|---|---|
| **L1** 商家模式選擇（叫賣 / 待機）| `L1State` | empty | `run_l1(...) -> str \| None`；`"L2"`=進 dialog、`None`=程式終止 |
| **dialog**（L2/L3 合一）| `DialogState` | empty | `run_dialog(...) -> tuple[str, int]`；`(next_state, think_count)`，`next_state ∈ {"L4","L1_enter_hawk"}` |
| **L4** 印金額 + 等掃碼 | `L4State` | nonempty | `run_l4(...) -> tuple[str,0,0]`；`next_state ∈ {"L5","L1_enter_hawk"}` |
| **L5** 致謝 | `L5State` | nonempty | `run_l5(...) -> tuple`（回傳值無條件忽略）|

**L0 不是運行層**——它是規格書「L0_共通.md」對應的**共通 NLU / 關鍵字白名單層**，物化為 `nlu.py` + `constants/keywords.py`，被所有層共用，沒有 `run_l0`。

### 1.3 狀態轉移表

```
[start]                  →                                         → l1

l1   → run_l1 回 None（按 q 兩次 / exit）                          → [程式終止]
l1   → run_l1 回 "L2"（hawk 模式按 't' 觸控開始點餐）              → dialog

dialog(cart 空 = L2 模式) → 加單成功 cart→非空                     → dialog（下輪自動成 L3 模式，無 transition）
dialog(L2) → timeout / 第 3 次想一下 / unclear 上限 / 拒絕         → l1（exit_a，cart 空不清）
dialog(L3) → 結帳 confirm "yes"                                    → l4
dialog(L3) → 拒絕(cancel YES) / C-2 取消 / checkout 否認超時        → l1（exit_a，清 cart）

l4   → 終端 's' / 客服模式 scan（鏈路 A）                          → l5
l4   → 拒絕(cancel YES,鏈路 B) / 客服 no / 36s budget 耗盡(鏈路 D)  → l1（清 cart）
l4   → 客服 yes「繼續」                                            → l4（reset 兩計時器，不轉移）

l5   → 無條件（do_action → clear_cart → sleep）                    → l1
```

`L1_enter_hawk` 是 dialog / L4 / L5 的「交易結束回 L1」訊號 → machine 設 `enter_hawk_immediately=True` → 下次 `run_l1` 跳過主選單直接連續叫賣（涵蓋 4 個出口：dialog reject/timeout、L4 cancel、L5 完成）。

### 1.4 核心設計：cart 是唯一驅動狀態

**層轉移由「世界狀態（cart）」驅動，非動作歷史。** dialog 內部每輪 main loop 由 `cart_module.is_empty(cart)` 即時推導 L2 / L3 模式（`policy()`，不快取）：cart 空 → L2（詢問需求）；cart 非空 → L3（加單 / 結帳）。未來加「刪除商品」使 cart 變空時，dialog 下輪自動回 L2 模式，**無需額外 transition**。這也是 L2/L3 從兩個獨立狀態合併為單一 dialog 層的原因。

---

## 2. 跨層流程（橫切）

### (a) Cancel confirm — 取消確認 6s gate
`_cancel_confirm.py` + `_timed_confirm.CancelConfirm`（6s）。任何 read 點偵測到「拒絕」intent → 不直接退 L1，先進 6s confirm。**NO 先於 YES**（防「不要取消」誤命中）、亂答不重置 deadline、silent/timeout → 視為 YES（取消）。觸發點：dialog 拒絕分支、checkout confirm 內 cancel、unclear 語音退出、L4 拒絕分支、invalid_qty 否定。

### (b) Service confirm — 客服確認 24s gate
`_service_confirm.py` + `_timed_confirm.ServiceConfirm`（24s）。`allow_scan` 區分兩單例：`SERVICE_CONFIRM`（L2/L3/qty_followup/invalid_qty）vs `SERVICE_CONFIRM_SCAN`（L4，啟用終端 's' fast path）。回 `"yes"/"no"/"scan"`。保守 default=`"no"`（silent/timeout 清 cart 退）。on_enter 印 `SERVICE_PHONE`。

### (c) L4 wall-clock budget — v3 雙計時器
兩個獨立 wall-clock deadline，與子鏈路解耦：
- `L4_TOTAL_BUDGET = 36s`：耗盡 → forced exit（鏈路 D，清 cart 退 L1）。
- `L4_QR_REFRESH_INTERVAL = 12s`：每循環開頭無條件重印明細 + 重 speak 提醒（36 = 12×3，共 3 循環）。
- 兩計時器從 entry prompt 播完起算；read timeout 取 `min(cycle_remaining, budget_remaining)`。
- cancel/service confirm 子狀態期間**暫停 + 補償**：量測子狀態耗時 `pause_duration`，回主迴圈後兩 deadline 各 `+= pause_duration`。
- 客服 yes「繼續」→ **reset 兩計時器**（fresh 36s + 重印 + 重 speak entry，非補償）。
- ⚠️ 早期註解 / 文件提的「L4 60s」已過時：v1 60s → v2 30s → 現 v3 **36s**。

### (d) C-2 自動結帳 — L3 timeout
`DialogSession.c2_second_stage`。L3 模式 main loop timeout（`DYC_TIMEOUT=12s` 無回應）或第 4 次想一下 → 進 C-2 第二段：speak「…{6}秒後將自動結賬」+ `C2_DECISION_TIMEOUT=6s` wall-clock budget（亂答不重置）。三選一（**CANCEL 優先**，顧客錢包保守）：CANCEL → exit_a 清 cart 退 L1；CONTINUE → ack 後重入 main_loop；CHECKOUT → 經 confirm 結帳。silent/倒數歸零 → 經 confirm 結帳（2026-05-29 反轉：不再直接 L4，合流經 confirm 保護錢包）。

### (e) 數量追問 qty followup
`_l2_l3_qty_followup.resolve_and_add_products`：Pass1 給有數量者即時 `classify_qty` 分流（at_cap skip / over_limit/zero 收進 invalid / ok add）；Pass1.5 `invalid_qty_reask` 合併重問無效數量；Pass2 缺數量者各進 `_qty_follow_up_sub_loop`（`QTY_FOLLOWUP_TIMEOUT=12s`，最多 3 attempts）。skip 累積 `cancel_notices` 給 caller 用全形「，」拼接成單一 reask speak。

### (f) Invalid qty reask — 無效數量重問
數量超量（>50）/ 為 0 → 不自動 cap/skip，進重問 loop（`INVALID_QTY_REASK_TIMEOUT=12s`，可 reset 最多 2 次）。即時提交模型（有效立即 add_item）。否定 → `InvalidQtyCancelConfirm` 二選一 6s。

### (g) Checkout confirm — L3 C-1 結帳前確認
`_dialog_checkout_confirm`。專用 `CHECKOUT_CONFIRM_TIMEOUT=12s` / `CHECKOUT_CONFIRM_UNCLEAR_MAX=5`（比通用寬鬆，顧客可能在數錢）。每次重 prompt 重置 timeout。六態 sentinel：`"yes"/"no_explicit"/"no_unclear_exhausted"/"timeout"/"cancel_to_l1"/"continue_keep_cart"`。**必須明確答覆才進 L4**（保護錢包）。

---

## 3. 模組職責 + 關鍵簽名

| 模組 | 職責 | 關鍵公開函式 |
|---|---|---|
| `logic.py` | facade：組 callbacks + 建 SalesMachine | `run(*, print_terminal, read_terminal_key, speak, do_action, read_customer_input, sleep, tts_is_idle, exit_program, show_hawk_help, speak_and_wait=None, display=None, start_hawk=False) -> None` |
| `cart.py` | 購物車資料模型 `dict[str,int]`，無 IO | `new_cart` / `add_item` / `get_quantity` / `remaining_capacity` / `classify_qty(cart,product,qty)->QtyVerdict` / `calc_total` / `clear_cart` / `is_empty` |
| `nlu.py` | 意圖分類 + 數量解析純函式 | `classify_intent(text, mode="normal")->Intent`、`parse_quantity`、`normalize_input`、`expand_fusion`、`has_quantity`、`split_at_quantity`、`find_quantity_spans` |
| `product_parser.py` | 多商品 + 數量統一 token parser | `parse_products(text) -> list[tuple[str, int\|None]]` |
| `phonetic.py` | 拼音近音糾錯（pypinyin lazy）| `phonetic_match(text, candidates, *, to_pinyin=None, group_key=None)`（⛔頂層禁 import pypinyin）|
| `dialog_io.py` | IO callback 束 frozen dataclass | `DialogIO(speak, read_customer_input, print_terminal=None, do_action=None, speak_and_wait=None, display=None)` + `.speak_blocking(text)` |
| `states/machine.py` | L1→dialog→L4→L5 State pattern 調度 | `SalesMachine(callbacks, cart, start_hawk=False).run()`、`Transition`、`State(ABC)`、4 個 `*State` |
| `states/l1.py` | L1 商家模式選擇（叫賣輪播）| `run_l1(...) -> str\|None`；模組級 `_q_confirm_pending`（q 兩次才退）|
| `states/l2_l3_dialog.py` | L2/L3 合一 cart 驅動對話層 | `run_dialog(...) -> tuple`、`ModePolicy`/`L2Policy`/`L3Policy`、`DialogSession` |
| `states/l4.py` | L4 結帳層 v3 雙計時器 | `run_l4(...) -> tuple` |
| `states/l5.py` | L5 致謝（最簡層，無互動）| `run_l5(cart, sleep, do_action) -> tuple` |
| `states/_l2_l3_qty_followup.py` | 商品加單共享 helper | `resolve_and_add_products(...) -> tuple[bool, list[str], str\|None]`、`format_cancel_prefix` |
| `states/_cancel_confirm.py` | cancel confirm facade | `cancel_confirm(...) -> bool`、`is_cancel_intent(response) -> bool` |
| `states/_service_confirm.py` | service confirm facade | `service_confirm(..., *, allow_scan=False) -> str` |
| `states/_timed_confirm.py` | TimedConfirm Template Method 家族 | `TimedConfirm(ABC)` + `CancelConfirm`/`ServiceConfirm`/`InvalidQtyCancelConfirm` + 4 模組級單例 |
| `states/_invalid_qty_reask.py` | 無效數量重問鏈 | `invalid_qty_reask(...) -> str`、`invalid_qty_cancel_confirm(...) -> str` |
| `constants/keyword_group.py` | keyword 雙集比對原語（純值）| `KeywordGroup(substrings, strict_short=()).matches(text)`、`contains_any`、`equals_strict_short` |
| `constants/{timing,products,keywords,actions,shared,l1-l5_text}.py` | 純資料常數 | 經 `constants/__init__.py` wildcard re-export |

---

## 4. NLU 細節

**`classify_intent(text, mode)`** — 層別語意感知，回 `Intent` Literal：
`"拒絕"/"想一下"/"結帳"/"客服"/"商品:冰紅茶"/"商品:刮刮樂"/"繼續交易"/"退出交易"/"等待安撫"/"想買無商品"/"無法判斷"`。

`mode` 影響分流：`"l4_service"`（繼續 / 退出交易）、`"l4"`（先判「等待安撫」、no→拒絕）、`"l2"`（no→拒絕）、`"normal"`(L3，嚴格 reject：通用短詞「不要/不用」→ 結帳=不追加)。**同字跨 mode 不同義**（「不用」L3=結帳 vs L2/L4=拒絕；「等一下」L4=等待安撫 vs L2/L3=想一下），全靠 mode + 判定順序保證分流。

**`parse_quantity(text, default=1)`** — 阿拉伯數字緊接乘數先攔（「9 萬」=90000）→ 阿拉伯優先（顯式 0 回 0）→ 複合中文（十/百/千/萬）→ 單字 fallback → default。`default=None` 走「缺數量」語意。

**`parse_products(text)`** — 八步統一 token parser：①精確商品 span（長詞先 + 去重）②數量 span ③garbled 品名 span（phonetic 糾錯 + 剝「我要」前綴）④排序 token ⑤鄰近綁定數量 ⑥garbled 數量糾錯 ⑦組 raw ⑧per-product dedup。回 `[(product_name, qty_or_None), …]`。⚠️ dedup 規則 3 是**覆寫非累加**（「紅茶2 紅茶3」= 改成 3 瓶，顧客修正語意）。

**`normalize_input(raw, max_length=200)`** — IO 邊界消毒：截斷 200 字 + 移除控制字元 + 全形數字→半形。`expand_fusion` 台灣合音還原「醬/將」→「這樣」（只在 dispatch unclear 出口跑）。

---

## 5. Callback 注入清單

`logic.run` 接收 11 個 callback，組成 dict 傳入 `SalesMachine`，各層按需取用：

| callback | 簽名 | 用於哪層 |
|---|---|---|
| `print_terminal` | `(text)` | L1 選單 / q 提示、L4 明細、service confirm 印電話 |
| `read_terminal_key` | `(timeout=None) -> str` | L1（hawk 模式 timeout=0.1 polling）|
| `speak` | `(text)` 非阻塞 | 全層語音 |
| `speak_and_wait` | `(text)` 同步阻塞 | wall-clock budget 子狀態（C-2 / L4 entry / cancel / service / qty）；None fallback 到 speak |
| `do_action` | `(name)` 同步阻塞跑廠商動作 | L1 hawk entry、dialog entry、L3→L4、L4 pay、L5 farewell |
| `read_customer_input` | `(timeout) -> str\|None` | dialog / L4 / 所有 confirm 子狀態 |
| `sleep` | `(seconds)` | L5 純等待 |
| `tts_is_idle` | `() -> bool` | L1 hawk 輪播間距 |
| `exit_program` | `()` | L1 q 兩次退出 |
| `show_hawk_help` | `()` | L1 hawk entry 印操作提示 |
| `display` | `(phase, cart_dict, paid=0)` | **web 鏡像**（終端模式為 None，全部 guard）|

### `display(...)` emit 點全清單（web 鏡像關鍵 → 接 `30`）

共 **3 處** emit phase：

1. **`SalesMachine._emit`** — 每進一層（invariant 後、`state.run` 前）。`_PHASE_BY_STATE`：`l1→"standby"`、`dialog→"ordering"`、`l4→"checkout"`、`l5→"thankyou"`。`paid` 僅 l5（thankyou）帶 `calc_total`（清 cart 前算），其餘為 0。
2. **dialog main loop 每輪** — 每輪處理完（cart 可能變動）`io.display("ordering", dict(cart))` → 前端購物車逐項長出的增量鏡像。
3. **進結帳確認** — `_dialog_checkout_confirm` 進場 `io.display("checkout_confirm", dict(cart))`。此步在 dialog 機台狀態內（machine 不會發此 phase）→ 前端跳確認卡片。

phase 全集：`standby` / `ordering`（machine 進場 + dialog 每輪）/ `checkout_confirm`（dialog 內）/ `checkout`（L4）/ `thankyou`（L5，帶 paid）。所有 emit 點都 guard `display is not None`。

---

## 6. 值得記住的設計決策 / gotcha

- **架構選項 C（嚴格不 import 廠商 SDK）**：sales/ 全程 callback 注入。唯一例外 pypinyin 在 `phonetic` 內 lazy import + `ImportError → None` graceful（Windows 未裝時糾錯層靜默 no-op）。
- **cart invariant fail-fast**：每進層 assert cart 空 / 非空，違反立刻 raise。
- **mock seam = 模組屬性晚綁定**：machine 一律 `states.run_*(...)` 呼叫，禁 `from ... import run_l1`（測試 monkeypatch.setattr 替換）；l4 客服 / cancel 也經 facade 函式（非 `.run` 實例）保留 mock seam。
- **錢包保守原則**：所有 confirm 子狀態 silent/timeout → 保守 default（cancel→取消、service→退、checkout→不進 L4）。C-2 silent 已反轉為「經 confirm 才結帳」。
- **TimedConfirm Template Method**：cancel(6s) / service(24s) / invalid_qty(6s) 共用 wall-clock 骨架，差異下放 hook。`run` 用 `outcome is not None` 判定（⚠️ False 是 CancelConfirm NO 的合法結果，不能用 truthiness）。
- **wall-clock budget 從 TTS 播完起算**：budget 子狀態用 `speak_blocking`（避免 2–3s 語音吃掉一半 budget）。
- **keyword 雙集（substring + strict_short）防短詞誤命中**：「好」substring 會中「好亂」、「取消」中「取消會議」→ strict_short 只完全相等才命中。
- **NLU phonetic 糾錯多層 gating**：只在 dialog `_dispatch` unclear 出口才跑（拒絕 / 想一下 / 結帳 / 客服 / 正常解析皆已先 return）。
- **價格九折硬編在 PRODUCTS**：冰紅茶 30→27 元/瓶、刮刮樂 200→180 元/張；`MAX_QTY_PER_ITEM=50`。HAWK_SLOGANS 含價 slogan 用 f-string 從 PRODUCTS 取（改價不漏改文案）。
- **L5 不再 speak**（2026-06-15）：致謝語音併入 L4 鏈路 A 的單句（消除 L4→L5 語音邊界 ALSA drain 尾截），L5 純 do_action → clear_cart → sleep。
- **L1 q-confirm polling 陷阱**：hawk polling 模式下 `""`（timeout 無輸入）不可 reset q_confirm，否則連按 q 永遠退不出。

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-06-21 | 初版：L0–L5 狀態機、SalesMachine 調度、跨層流程、NLU、callback 注入與 display emit 清單。|
