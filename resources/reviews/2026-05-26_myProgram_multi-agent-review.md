# myProgram/ 多視角審查整合報告

> **日期：** 2026-05-26
> **基線 commit：** `db1dcf3` (tune(constants): OPENCV_MUTE 12s -> 6s for better demo pacing)
> **分支：** `main`（review 時 clean，172 tests PASS）
> **審查範圍：** ONLY `myProgram/` 資料夾（含 14 個 .py 檔；廠商檔 `ActionGroupControl.py` / `Board.py` 內容禁改但位置可重組）
> **排除路徑：** `tests/`、`resources/`、`.claude/`、根目錄腳本

---

## 0. 元資訊

### 0.1 派出的審查視角

| # | 視角 | Agent | 模型 | 模式 | 產出長度（約） |
|---|---|---|---|---|---|
| A | 結構與檔名 | opus subagent #1 | claude-opus-4-7 | extended thinking, high effort | ~2800 字 |
| B | 狀態機正確性 + cart invariant | opus subagent #2 | claude-opus-4-7 | extended thinking, high effort | ~3700 字 |
| C | NLU 健壯性（keyword / mode-aware / 簡繁） | opus subagent #3 | claude-opus-4-7 | extended thinking, high effort | ~3800 字 |
| D | 橫切面 /review 適配版（wire-up / 風格 / 效能 / 安全） | 主 agent（claude-opus-4-7） | 主對話 | 直接審查 | ~1800 字 |

### 0.2 為何不是 6 份

使用者原訂「`/review` build-in（3 subagent）+ 1 結構 + 2 自選 = 6 份」。實際運作：

- **`/review` 內建 skill** 是 **單一 prompt 的 PR 審查工作流**（`gh pr list` → `gh pr view` → `gh pr diff` → 寫評論），**不是 3 個並行 subagent**。使用者對 `/review` 行為的預期有誤。
- 當前無 open PR，且使用者 scope arg 被當「PR number」傳入，原版 `/review` 流程不適用。
- 主 agent 改採 `/review` 的五大維度（正確性 / 慣例 / 效能 / 測試 / 安全）對 myProgram/ 做適配版審查 = 視角 D。

最終實得 **4 個獨立視角**（A/B/C 為 opus subagent 並行 / D 為主 agent 直接審）。

### 0.3 範圍嚴格守則（4 視角共同遵守）

- 純 read-only：無檔案修改、無 commit、無 push。
- 廠商檔（`ActionGroupControl.py` / `Board.py`）內容當黑盒，僅可建議搬位置。
- 全程繁體中文輸出。

---

## 1. Executive Summary（主要發現）

### 1.1 整體評分（4 視角彙整）

| 維度 | 分數 | 主要支撐 |
|---|---|---|
| 結構 / 檔名 | 6.5 / 10 | 廠商檔與業務碼平鋪、package/module 同名、states/ 命名混三套、dead callback/parameter |
| 狀態機正確性 | 7.5 / 10 | 主架構乾淨，但 C-2 NO keyword 歧義會直接清顧客 cart；inner copy-paste 維護負擔 |
| NLU 健壯性 | 6.5 / 10 | substring「沒了」「好」「錯」單字過於寬鬆；大小寫敏感；簡繁覆蓋只在商品 |
| 橫切面（wire-up / 風格 / 效能 / 安全） | 中上 | 慣例守得好；wire-up `unmute_opencv` 漏對稱清 dwell；customer q 越層 sys.exit |

### 1.2 最關鍵 7 個發現（跨視角整合，按嚴重度排序）

1. **【critical】C-2 strict yes/no 內 `KEYWORDS_CONFIRM_NO` 包含「沒了 / 不要 / 沒有」與 L3 normal 的「結帳意圖」**語意重疊。顧客在「請問是否要結帳」回「沒了」（本意 = 沒其他要加，**結帳**）→ 先匹配 CONFIRM_NO → cart 被清空。**逆向錯誤、顧客錢包風險最高**。
   來源：視角 B #3、視角 C #2 / #6 同時發現。

2. **【critical】`dialog.py:510` C-2 YES 條件含 `classify_intent==結帳`**，把「no / nope / 沒了」當 YES 推進 L4。**顧客講 nope 卻被結帳**。
   來源：視角 C #6。

3. **【critical】`KEYWORDS_CONFIRM_YES` 含「好」單字 + substring match** → 「好像不對」「好亂」「好困惑」會誤判 YES。`KEYWORDS_CONFIRM_NO` 含「錯」 → 「沒錯」「不錯」誤判 NO。
   來源：視角 C #3。

4. **【high】`_dialog_checkout_confirm` unclear 達上限 (5 次) return False 跟「明確說不對」走同訊息**（caller speak `L3_CHECKOUT_REJECT_CLEAR_NOTICE`）。顧客亂答 5 次被踢，但訊息語意 = 「你說不對」，與 timeout 不對稱。
   來源：視角 B #1。

5. **【high】C-2 YES 後再進 `_dialog_checkout_confirm` 形成 12s + 12s = 24s 雙漏斗**。顧客明確說要結帳 → 比 timeout 還慢。
   來源：視角 B #2。

6. **【high】廠商檔 `ActionGroupControl.py` / `Board.py` 與業務碼 / wire-up 平鋪於 `myProgram/` root**，視覺無隔離，hook 路徑 hardcode 是唯一保護。應搬到 `myProgram/vendor/`。
   來源：視角 A #1、視角 D #6.4 同時發現。

7. **【high】`do_action` callback 從未被 sales/ 內任何函式呼叫**，但被當 dead parameter pollution 傳遍 dialog / l4 / l5 簽名。S3 真接動作層時再加，符合 karpathy「no premature abstraction」。
   來源：視角 A #3.5、視角 D #2.5（順帶 `schedule` 也是 dead）同時發現。

### 1.3 修補後預期改善

- **必修第 1-3 條** → 直接消除「顧客錢包 / cart 誤清」高頻 false positive。
- **必修第 4-5 條** → checkout confirm 邏輯與顧客直覺對齊。
- **必修第 6-7 條** → 結構性 dead code / 隔離不足，長期維護負擔降低。

預估這 7 條修完後：**狀態機 7.5 → 9，NLU 6.5 → 8.5，結構 6.5 → 8**。

---

## 2. 跨視角共識點（多視角同步觀察）

### 2.1 「沒了 / 不要 / 沒有」keyword 同時出現在多個 set 是核心病灶

- **狀態機視角 B #3**：C-2 strict yes/no 內 NO 詞表含「沒了」「不要」「沒有」與 L3 normal mode「結帳意圖」的詞重疊，顧客「沒了」（= 結帳）被當 NO（= 取消）。
- **NLU 視角 C #2 + #6 + caller §4**：同 keyword 在 `KEYWORDS_CHECKOUT`（結帳）、`KEYWORDS_CONFIRM_NO`（拒絕）、`_KEYWORDS_REJECT`（拒絕）三處出現，語意分歧。caller 端 dialog.py:510 進一步把 `intent==結帳` 的 keyword 當 CONFIRM_YES 又疊一層歧義。

**整合判定：** 不是單一檔的 bug，是 **constants.py keyword 設計衝突 + caller dispatch 優先序混亂** 的雙因素。修法要同步改 constants（縮窄 NO 詞表）+ dialog.py:510（移除 intent==結帳 條件）+ 補規格說明「沒了」在 C-2 應該 = YES。

### 2.2 廠商檔位置 + dead code = 結構誠實度問題

- **視角 A #1, #3.1, #3.5**：廠商檔放 root 沒視覺隔離 / `do_action` dead parameter / `schedule` callback 從未呼叫 / `_dialog_c2_auto_checkout` 純 wrapper。
- **視角 B dead code #1**：`_dialog_c2_auto_checkout` 完整 wrapper，3 個 caller 可直接呼 `_dialog_c2_second_stage`。
- **視角 D §2.5, §6.4**：`schedule` 從未被 logic.py 呼叫；廠商檔位置安全性依賴 hook hardcode。

**整合判定：** 結構性「為未來預留」的代碼已開始累積技術債。符合 karpathy「premature abstraction」反模式。應一次清理。

### 2.3 dialog.py 的 `_dialog_continue_after_c2_inner` 是已知維護負擔

- **視角 A #3.4**：dialog.py 含 775 行 + `_dialog_continue_after_c2_inner` 與 `run_dialog` 主迴圈幾乎重複（113 行 copy-paste）。
- **視角 B #5（medium）**：同一發現，建議抽 `_dialog_main_loop_body(play_entry_prompt: bool)` helper。

**整合判定：** 需要 refactor 但有 159+ tests 安全網。視角 A/B 建議方案一致：抽出 `_dialog_main_loop(play_entry_prompt: bool)` 共享 helper。

### 2.4 顧客輸入邊界處理不一致

- **視角 D §6.1**：customer 輸入 raw 直接進 NLU，無長度上限 / 控制字元剔除。S4 接 STT 後是 DoS vector。
- **視角 C §5（大小寫）**：classify_intent 完全沒做 `.lower()`，CHECKOUT/CONFIRM 的英文 keyword「YES / NO / OK」**不命中**。
- **視角 C §5（全/半形）**：終端輸入「１」「２」全形數字不命中 `response == "1"` / `"2"` 比對。

**整合判定：** customer-input pipeline 在 wire-up + NLU + caller 三層的 sanitize 都缺。應在 NLU 統一處理（`_normalize_input` helper）。

### 2.5 L4 鏈路 D 達上限催促語音斷層

- **視角 B #6（medium）**：`l4.py:130` loop_count 從 6 → 7 後 `_l4_d_speak_loop_voice(7, ...)` 命不到 dispatch table（只到 5/6），第 7 次 silent。

僅視角 B 發現；視角 A/C/D 範圍不涵蓋此細節。是獨立發現但同屬「邊界條件不完整」類別。

---

## 3. 完整建議清單（按優先級彙整）

> 來源欄位：A = 結構審查、B = 狀態機審查、C = NLU 審查、D = /review 適配版。

### 3.1 必修（critical / high — 影響顧客錢包 / cart invariant / 安全保護失效）

| # | 來源 | 位置 | 問題描述 | 建議修法 |
|---|---|---|---|---|
| M1 | B#3 / C#2 | `dialog.py:494` + `constants.py KEYWORDS_CONFIRM_NO` | C-2 strict yes/no NO 優先匹配「沒了」「不要」「沒有」「沒了」（與「結帳意圖」重疊），顧客「沒了」（= 結帳）→ cart 被清 | C-2 內 NO 詞表縮窄到「不對 / 不是 / 錯字無歧義詞」；或拉出獨立 `KEYWORDS_C2_STRICT_NO = ["不對", "不是", "不要結帳", "不結"]` |
| M2 | C#6 / caller §4 | `dialog.py:510` | YES 條件含 `classify_intent==結帳`，「no / nope / 沒了」被當 YES 推進 L4 | 移除 `classify_intent==結帳` 條件，YES 僅靠 `response=="1"` + `KEYWORDS_CONFIRM_YES` substring |
| M3 | C#3 / table | `constants.py KEYWORDS_CONFIRM_YES/NO` | 「好」單字 substring → 「好像/好亂」誤 YES；「錯」substring → 「沒錯/不錯」誤 NO；「沒了」「沒有」substring → 整類否定肯定句誤命中 | YES 移除「好」單字（改「好的」/「好啊」）；NO 移除「錯/沒了/沒有/改」（改「不對/不正確/不是/wrong」）；補簡體「对/错/没/不买」 |
| M4 | C§5 (大小寫) | `nlu.py classify_intent` | `KEYWORDS_CHECKOUT` 含「no/nope」、CONFIRM_YES 含「yes/ok/correct」均 case-sensitive；顧客打 NO / YES / Ok 不命中 | 加 `_contains_any` helper 做 `.lower()` 後比對；或先 normalize input：`text = text.lower()` |
| M5 | C§4 (L4 客服) | `nlu.py _KEYWORDS_CONTINUE` | substring「繼續」→ 「不繼續」誤判繼續交易 | l4_service 分支內加否定 guard：`if any(neg in text for neg in ["不繼續","不要繼續","別繼續"]): return "退出交易"` 排在 CONTINUE 前 |
| M6 | C#1 + 註解 #20-23 | `nlu.py _KEYWORDS_REJECT` | 「沒」單字會誤命中「沒事」「沒問題」「沒空」 → L2/L3 reject 退場 | 移除「沒」單字（保「沒有」），與使用者確認實機案例權衡（使用者原本要求加入；可改成「沒打算 / 沒了」更安全） |
| M7 | A#1 / D§6.4 | `myProgram/ActionGroupControl.py` + `Board.py` 位置 | 廠商檔與業務碼平鋪 root，視覺無隔離；hook 路徑 hardcode 是唯一保護 | 搬到 `myProgram/vendor/` + `__init__.py` 加 "DO NOT MODIFY" docstring；**同步更新 `.claude/hooks/` 內 hardcode 路徑 + `vendor-files` memory** |

### 3.2 建議修（medium — UX 一致性 / 維護負擔 / 邊界條件）

| # | 來源 | 位置 | 問題 | 建議 |
|---|---|---|---|---|
| S1 | B#1 | `dialog.py:708-710` `_dialog_checkout_confirm` | unclear 達上限 (5) return False 與「明確說不對」共用訊息，顧客無法區分 | 4-valued return (`True/False/None/"unclear_exhausted"`)；caller 加分支 speak「不好意思我聽不太懂，已取消這次結帳」 |
| S2 | B#2 | `dialog.py:512-523` | C-2 YES → 再進 confirm → 12s+12s=24s 雙漏斗 | C-2 YES 直接 `return ("L4", 0)`，或 C-2 prompt 改「即將結帳 X，請說是/否」一次到位、移除後置 confirm |
| S3 | B#4 / 視角 D | `constants.py L2_TIMEOUT_TO_HAWK_VOICE` | 「由於顧客沒有回應，我將繼續叫賣模式」第三人稱對顧客講違和 | 改顧客語氣：「不打擾您了，歡迎再次光臨」；或乾脆 silent 直接回 L1 hawk |
| S4 | B#6 | `l4.py:130` + `_l4_d_speak_loop_voice` | loop_count 從 6 → 7 後 dispatch table 不命中 → 第 7 次 silent 進 final | `(5, 6)` 改 `>= 5`，或主迴圈頂 `loop_count >= L4_MAX_LOOPS` 前先處理剛 ++ 上限的 voice |
| S5 | A#3.4 / B#5 | `dialog.py:551-663` `_dialog_continue_after_c2_inner` | 113 行幾乎複製 `run_dialog` 主迴圈，雙份維護 | 抽 `_dialog_main_loop(play_entry_prompt: bool, initial_unclear: int)`，兩處變 thin wrapper |
| S6 | B#7 | `dialog.py:649-663` | `_dialog_continue_after_c2_inner` 內 think_count 不在 final confirmation 選「繼續」後 reset | line 660 `unclear_count = 0` 處同步 `think_count = 0`，或規格明示「跨子流程 persist」意圖 |
| S7 | A#3.5 / D§2.5 | `dialog.py`/`l4.py`/`l5.py`/`myProgram.py` | `do_action` callback 在 sales/ 內 0 呼叫；`schedule` callback 同樣 dead | 從 callback dict 與所有 layer 簽名移除（S3+ 真用時再加）；測試 conftest fixture 同步刪 |
| S8 | A#3.1 | `myProgram/myProgram.py` 與 package 同名 | `myProgram.myProgram` 路徑模糊，新人困惑 | 改名 `myProgram/main.py` + 補 `myProgram/__init__.py`（顯式 package）+ 可選 `__main__.py` 支援 `python -m myProgram` |
| S9 | A#3.3 | `states/` 內檔名混三套（l1/l4/l5 vs dialog vs subroutine_a vs _product_helpers） | 一致性差，讀目錄如「歷史地層」 | 統一層編號制：`subroutine_a.py` → `l0_subroutine_a.py`，`dialog.py` → `l2_l3_dialog.py`，`_product_helpers.py` → `_l2_l3_qty_followup.py` |
| S10 | C§5 (全形) | wire-up / NLU 邊界 | 顧客「１」「２」全形數字不命中 `response=="1"/"2"` | 加 `_normalize_digits` helper `str.translate("０１２３４５６７８９","0123456789")`，wire-up 端先 normalize |
| S11 | D§2.2 | `myProgram.py:127-132` `unmute_opencv` | 沒清 `state.opencv_dwell`（與 mute 不對稱） | 加 `state.opencv_dwell = 0.0` 一行 |
| S12 | D§2.4 / §6.1 | `myProgram.py:74-90` `read_customer_input` | customer 輸入 raw 直接傳 NLU，無長度上限 / S4 接 STT 是 DoS vector | 加 `raw = raw[:200]`；customer "q" 改 return sentinel + logic 層 handle（不從 callback `sys.exit` 越層） |
| S13 | C#6 | `nlu.py _KEYWORDS_CHECKOUT` | 「no / nope」短詞 substring（「nothing / none / known」誤命中）；「好了」會命中「再等好了」（語意 think） | 移除「no / nope / 好了」 |
| S14 | C#7 | `nlu.py _KEYWORDS_REJECT_L3_STRICT` | L3「整單作廢」缺常用「全部取消 / 都不要 / 整單取消 / 取消」 | 補入；含簡體「取消订单 / 不买了」 |
| S15 | C#9 | `nlu.py _KEYWORDS_ICED_TEA` | 「tea」短詞 substring（「steak」不含但 STT 雜訊可能誤轉） | 改「iced tea」「black tea」更具體 |
| S16 | B#4 註解 | `logic.py:105-109` | assert 註解「L4-B/C/D 已清 cart」漏列 `_l4_service_mode` 掃碼路徑 | 註解改「L4 非 L5 路徑必清 cart（_l4_exit_b / _l4_exit_d_forced / _l4_service_mode 退出三條皆 clear_cart；掃碼 → L5 由 L5 自身 clear）」 |
| S17 | A#3.6 | `constants.py` 239 行單檔 | 已開始膨脹，混 L0-L5 文字 + keyword + 商品 | 接近 400 行才拆 `constants/timing.py + products.py + keywords.py + l?_text.py`；當前可暫不拆 |
| S18 | A#3.7 | `nlu.py` 內 `_PRODUCT_KEYWORD_TO_NAME` + `parse_products` | 商品實體解析混在「純意圖」模組，職責糊 | 抽出 `sales/product_parser.py`；nlu.py 維持 `classify_intent` / `parse_quantity` 純意圖 |

### 3.3 可不改（low — 註解 / 風格 / 已 documented 設計）

| # | 來源 | 位置 | 描述 |
|---|---|---|---|
| L1 | A#3.10 | `__pycache__/l2.cpython-314.pyc` + `l3.cpython-314.pyc` | 孤兒 .pyc，源檔已刪；下次 `Remove-Item __pycache__` 自然消失 |
| L2 | A#3.8 / #3.9 | `sales/__init__.py` + `states/__init__.py` | 目前 facade 合理，保持現狀 |
| L3 | B 註解類 | `l4.py:155-162` `_l4_dispatch_response` 註解只列一條 None 來源 | 補一行註解即可 |
| L4 | B low | `dialog.py:362-363` `_dialog_dispatch_inner_l2` 兜底 `speak(L2_B1_CLARIFY)` 不累積 unclear | inner 不維持 counter 是設計選擇，註解標明 |
| L5 | B low | `_dialog_c2_auto_checkout` 純 wrapper | dead wrapper 可刪可留 |
| L6 | B low | `dialog.py:466-477` 註解寫「wall-clock 倒數」但實際依賴 callback timeout 機制 | callback 規格已含「必須遵守 timeout」；註解可加備註 |
| L7 | B low | `l4.py:299` speak + print 同訊息 | 音 + 文雙保險，設計選擇 |
| L8 | B low | `dialog.py:709-711` confirm unclear 達上限 return 後 speak 無法 reach | 邏輯正確，讀起來不流暢；可不改 |
| L9 | D§2.3 | `read_terminal_key` 'c' 鍵 side-effect + return "" 設計 | docstring 已標註，OK |
| L10 | D§3 | 各種 print prefix 10 種（[商家][顧客][系統][語音][動作][opencv][等待][schedule][模擬][模擬提示]） | S1 模擬期接受，S4 過渡前統一 |
| L11 | D§5.2 | wire-up 缺整合 smoke test | 172 unit tests 已足；stdin mock 麻煩 |
| L12 | D§4.1 | NLU substring `in` 是 O(N×M) | 對話頻率 < 1 Hz，當前無問題 |
| L13 | D§2.6 | wire-up 日誌噪音 prefix 過多 | S1-only，S4 過渡時統一 |
| L14 | C§5 (拼音 fallback) | hong cha / lottery / scratch / contact / wait | 命中率低但 substring 較長無誤命中，保留 |
| L15 | D§3.5 | import 順序非 PEP8 嚴格 | 可加 ruff / isort 自動化，但當前 OK |

---

## 4. 完整原始報告（毫無保留）

### 4.1 視角 A：結構與檔名審查（opus subagent #1）

#### 1. 總評

**現況評分：6.5 / 10**

整體結構展現「層次清晰的努力」（`sales/states/` 子資料夾、callback 注入隔離廠商 SDK、純函式 nlu / cart），但有 **5 個結構性問題** 拉低分數，且都是「越晚改成本越高」的類別。

主要痛點（依嚴重度排序）：

1. **【必改】廠商檔與業務碼平鋪於 `myProgram/`** — `ActionGroupControl.py` / `Board.py`（廠商 SDK）跟 `myProgram.py`（自寫 wire-up）放同一層，沒有任何視覺 / 命名上的隔離。新成員 `ls myProgram/` 看到三個 .py 完全無法判斷哪個能改哪個不能改。`.claude/hooks/` 的禁改是「行為層」隔離，**目錄層仍未隔離**。
2. **【必改】Package 與模組同名 `myProgram/myProgram.py`** — package directory `myProgram/` 內有檔案 `myProgram.py`。從外面 `python -m myProgram.myProgram` 可跑，但 `from myProgram import xxx` 會撞 namespace 模糊；新人讀檔名第一眼會困惑「這是入口還是 package re-export」。
3. **【建議改】`states/dialog.py` 含 775 行 + `_dialog_continue_after_c2_inner` 與 `run_dialog` 主迴圈邏輯幾乎重複** — 雙份維護是現實 bug 來源（任何 dispatch 改動要兩處同步）。`_dialog_continue_after_c2_inner` 是「主迴圈 minus entry prompt」的 copy，可以用一個 `skip_entry_prompt: bool` 參數合掉。
4. **【建議改】`do_action(name)` 在整個 sales/ 內被傳遞但從未呼叫** — wire-up `myProgram.py` 定義 stub，dialog / l4 / l5 簽名都吃 `do_action`，但 `Grep do_action(` 在 sales/ 樹下 0 hit。屬「為了未來 S3 動作層預留」的 dead parameter pollution。S1 階段該移除，S3 真接動作時再加，符合 karpathy「no premature abstraction」。
5. **【建議改】`states/` 內檔名命名三套混用** — `l1.py / l4.py / l5.py`（層編號制）+ `dialog.py`（合一後改職能制）+ `subroutine_a.py`（規格書代號制）+ `_product_helpers.py`（內部 helper 底線制）。四套命名邏輯讀起來像「歷史地層」，缺一致性。

次要痛點：
- `constants.py` 239 行單檔混 L0/L1/L2/L3/L4/L5 + keyword + 商品定義，已開始膨脹
- `__pycache__/l2.cpython-314.pyc` / `l3.cpython-314.pyc` 是孤兒 .pyc（源檔已不存在）— `.gitignore` 應有擋掉，但本機 stale，亂讀容易誤導
- `nlu.py`（sales/ root）與 `_product_helpers.py`（states/ 內）職責邊界不清

#### 2. 現況目錄樹

```
myProgram/
├── __pycache__/                  (gitignore)
├── ActionGroupControl.py         廠商 SDK，禁改
├── Board.py                      廠商 SDK，禁改
├── myProgram.py                  S1 wire-up 入口（callback 注入 + main）
└── sales/                        後端業務邏輯 package
    ├── __pycache__/              (gitignore，含孤兒 l2/l3.pyc)
    ├── __init__.py               純 docstring
    ├── cart.py                   購物車資料模型（純函式）
    ├── constants.py              L0-L5 常數 + keyword + 商品（239 行）
    ├── logic.py                  主控狀態機（L1→dialog→L4→L5 cycle）
    ├── nlu.py                    意圖識別 + 數量解析 + 多商品解析
    └── states/                   各層鏈路實作
        ├── __pycache__/          (gitignore)
        ├── __init__.py           re-export 5 個 run_* 函式
        ├── _product_helpers.py   L2/L3 鏈路 C 商品加單 helper
        ├── dialog.py             L2/L3 合一對話層（775 行）
        ├── l1.py                 商家模式選擇層
        ├── l4.py                 結帳層
        ├── l5.py                 致謝層
        └── subroutine_a.py       L0 共通子例程 A
```

#### 3. 具體建議（逐檔 / 逐資料夾）

##### 3.1 廠商檔位置

**【必改】把 `ActionGroupControl.py` 與 `Board.py` 搬到 `myProgram/vendor/`**

- 理由：(a) 視覺上立即與自寫碼分離；(b) `myProgram/vendor/__init__.py` 可加 `# Hiwonder TonyPi SDK — DO NOT MODIFY` 一行，當原始碼層的提醒（hook 是事後攔截，註解是事前嚇阻）；(c) 未來引入其它廠商檔有歸屬地。
- 改動：搬檔 + `__init__.py` 一行 docstring + 全專案 `from myProgram import ActionGroupControl as Act` 改為 `from myProgram.vendor import ActionGroupControl as Act`（目前 sales/ 內沒人 import，僅 wire-up `myProgram.py` 第 11-12 行 docstring 提到，實際還沒 import；改動成本接近 0）。
- **不建議**改名為 `hardware/` — Board 雖然偏硬體，但 ActionGroupControl 更貼近「動作 SDK」，`vendor/` 語意最中立準確，也與 memory `vendor-files` / `vendor-sdk-api` 等命名一致。

##### 3.2 入口檔位置與命名

**【必改】把 `myProgram/myProgram.py` 改名並搬位置**

兩個方案擇一：
- **方案 A（推薦）：** 改名 `myProgram/main.py`，跑法 `python -m myProgram`（在 `myProgram/__init__.py` 加 `from .main import main` + `__main__.py` 或直接 `python -m myProgram.main`）。
- **方案 B：** 改名 `myProgram/app.py` 或 `myProgram/entry.py`，跑法 `python -m myProgram.app`。

理由：消除 package 與檔同名的 namespace 模糊；`main.py` 是 Python 圈慣例，新人零學習成本。

注意：`myProgram/__init__.py` 目前**不存在**（從 Glob 結果看 `myProgram/` 沒有 `__init__.py`，僅 `sales/__init__.py`）— 這代表目前 `myProgram` 是「隱式 namespace package」（PEP 420），跑得起來但行為不嚴格。改名同時應補 `myProgram/__init__.py`（即使是空檔）讓 package 顯式化，避免未來 import 行為飄移。

##### 3.3 `sales/states/` 內檔名一致化

**【建議改】統一改成「層編號制」或「職能制」二選一，不要混用**

- **推薦：層編號制**（與規格書 L1-L5.md 對齊）：
  - `subroutine_a.py` → `l0_subroutine_a.py`（或更直白：`l0_common.py`）
  - `dialog.py` → `l2_l3_dialog.py`（明示是 L2+L3 合一）
  - `_product_helpers.py` → `_l2_l3_qty_followup.py`（更精確說明是追問子迴圈，不是「商品 helper」泛論）
  - `l1.py` / `l4.py` / `l5.py` 不動
- 理由：規格書全用 L0/L1/L2/L3/L4/L5 編號，code 跟規格 1:1 對應最易追溯。`dialog.py` 改 `l2_l3_dialog.py` 後，新人讀目錄馬上知道「合一了哪兩層」，省一層 docstring 解釋。

##### 3.4 `dialog.py` 拆分與去重

**【建議改】抽 dispatch core，消除 `_dialog_continue_after_c2_inner` vs `run_dialog` 主迴圈雙份維護**

目前兩函式約 90% 邏輯重複，差別僅「是否在開頭播 entry prompt」。建議：
- 新增 `_dialog_main_loop(..., play_entry_prompt: bool)` 私有函式，含真正的 dispatch 迴圈
- `run_dialog` 變 thin wrapper：`opencv_disable()` + `_dialog_main_loop(play_entry_prompt=True, ...)`
- `_dialog_continue_after_c2_inner` 變 thin wrapper：`_dialog_main_loop(play_entry_prompt=False, ...)`
- 後續 dispatch 改動只改 `_dialog_main_loop` 一處

風險：原本兩函式可能在「looks identical 但細微不同」處藏 bug — 合併前必須 line-by-line diff 兩段邏輯，由 tests/sales/ 既有 159 tests 守住。

**【建議改】檔案拆分為 `dialog/` 子 package（若上面合併後仍 >500 行）**

可選結構：
```
sales/states/dialog/
├── __init__.py          re-export run_dialog
├── main_loop.py         _dialog_main_loop + run_dialog
├── checkout_confirm.py  _dialog_checkout_confirm + _handle_checkout_confirm_result
├── c2_auto_checkout.py  _dialog_c2_auto_checkout + _dialog_c2_second_stage
├── think_silence.py     _dialog_think_silence_l2/l3 + _dialog_dispatch_inner_l2/l3
└── helpers.py           _dialog_exit_a / _dialog_unclear_final_confirmation / _build_order_summary
```
但這要在去重後再評估必要性 — 若去重後 <400 行，**單檔反而較易讀**，別硬拆。

##### 3.5 `do_action` dead parameter 清理

**【建議改】從 dialog / l5 / l2 鏈路移除 `do_action` 參數**

- L4 也未呼叫 do_action，但 `do_action` docstring 寫「動作（規格 TBD，stub 可 no-op）」— 屬於未來預留
- 依 karpathy「no premature abstraction」原則：S3 真接動作層時才把 `do_action` 加回各 layer 簽名
- 改動範圍：l4.py / l5.py / dialog.py 函式簽名 + logic.py call site + tests/conftest.py fixture
- 風險：改完跑全套 pytest 確認綠（159 tests 應該全 pass）

##### 3.6 `constants.py` 拆分

**【可不改 / 視成長判斷】239 行尚可，但接近上限**

若未來再加 1-2 個 L 層或新商品類別 → 強烈建議拆：
```
sales/constants/
├── __init__.py    re-export 全部（保 backward compat import path）
├── timing.py      WAIT_NO_RESPONSE / HAWK_INTERVAL / OPENCV_MUTE / ...
├── products.py    PRODUCTS / QTY_PROMPT_TEMPLATE / 商品相關
├── keywords.py    KEYWORDS_CONFIRM_YES/NO / nlu 純詞表（從 nlu.py 內部移過來統一）
├── l1_text.py     L1_MENU_BANNER / L1_HAWK_ENTRY_PROMPT / ...
├── l2_text.py     L2_*
├── l3_text.py     L3_*
├── l4_text.py     L4_*
└── l5_text.py     L5_*
```
現階段（S1 完成）尚不必拆，但 BDD+TDD 重啟新增 sales/ 業務時就會臨界。**現在改：可不改**。

##### 3.7 `nlu.py` 與 `_product_helpers.py` 邊界

**【建議改】把 `_PRODUCT_KEYWORD_TO_NAME` + `parse_products` + `_parse_quantity_in_window` 從 nlu.py 拉出，獨立 `sales/product_parser.py`**

理由：
- `nlu.py` 原本定位「純意圖識別」（classify_intent / parse_quantity / has_quantity）
- `parse_products` 是「商品名稱 + 數量區間綁定」屬於更上層的解析，混在 `nlu.py` 後檔案職責糊了
- 拉出後 `nlu.py` 維持「intent 純函式」，`product_parser.py` 處理商品實體解析
- `_product_helpers.py`（在 states/ 內）則維持「對話 sub-loop（含 IO callback）」職責 — 命名應改為 `_qty_followup.py` 或上面 3.3 建議的 `_l2_l3_qty_followup.py`，因為它根本不是「product helper」泛論，是「追問子迴圈」的具體實作

##### 3.8 `sales/__init__.py` 暴露 API

**【可不改】目前是純 docstring 無 re-export，剛剛好**

不要陷入「__init__.py 必須做 facade」的迷思。目前 callers (`myProgram.py` / `logic.py`) 都用 `from myProgram.sales import logic` / `from myProgram.sales import cart as cart_module` 完整路徑 import，清晰可追溯。**保持現狀**。

##### 3.9 `states/__init__.py` re-export

**【可不改】目前 re-export 5 個 run_*，合理**

提供「states.run_l1 / states.run_l4」單一進入點，給 `logic.py` 用，是合理的 facade。**保持現狀**。

##### 3.10 孤兒 .pyc 清理

**【可不改】本機 stale，下次清空 __pycache__ 自然消失**

`__pycache__/l2.cpython-314.pyc` / `l3.cpython-314.pyc` 來自 2026-05-25 合一前的 `l2.py / l3.py`，源檔已刪，pyc 還在。`.gitignore` 應已含 `__pycache__/`（從先前歷史看），本機殘留無害但可能誤導 grep。可手動 `Remove-Item -Recurse __pycache__` 清掉，或不管下次跑 pytest 自動覆蓋為新版（不會新增 l2/l3.pyc，自然消亡到 git clean 才清）。**非結構問題，標可不改**。

#### 4. 推薦目標目錄樹

```
myProgram/
├── __init__.py                          顯式 package（新加，空檔即可）
├── __main__.py                          支援 python -m myProgram（可選）
├── main.py                              S1 wire-up 入口（原 myProgram.py 改名）
├── vendor/                              廠商 SDK 隔離
│   ├── __init__.py                      docstring: Hiwonder TonyPi SDK, DO NOT MODIFY
│   ├── ActionGroupControl.py            原檔搬入
│   └── Board.py                         原檔搬入
└── sales/                               後端業務邏輯
    ├── __init__.py                      純 docstring（不動）
    ├── cart.py                          購物車資料模型（不動）
    ├── constants.py                     L0-L5 常數（暫不拆；逼近 400 行再拆）
    ├── logic.py                         主控狀態機（不動）
    ├── nlu.py                           純 intent + quantity（移除 product parsing）
    ├── product_parser.py                商品實體解析（從 nlu.py 拉出）
    └── states/
        ├── __init__.py                  re-export 5 個 run_*（不動）
        ├── l0_subroutine_a.py           原 subroutine_a.py
        ├── l1.py                        不動
        ├── l2_l3_dialog.py              原 dialog.py（去重 + 移除 do_action 參數）
        ├── _l2_l3_qty_followup.py       原 _product_helpers.py
        ├── l4.py                        移除 do_action 參數
        └── l5.py                        移除 do_action 參數
```

#### 5. 遷移計畫（建議執行順序）

每步建議獨立一輪 worktree → 一個 commit → push（hook sync）→ 跑 pytest 確認綠，符合 incremental-rebuild「每步只一變數」。

##### 階段 0：清除技術債（先做 dead code，最低風險）
1. **移除 `do_action` dead parameter**（影響：l4.py / l5.py / dialog.py / logic.py / myProgram.py / tests fixture）。跑 pytest 確認 159 tests 全綠。

##### 階段 1：廠商檔隔離（純檔案搬移，0 import 變動）
2. 建 `myProgram/vendor/` + `__init__.py`（含 DO NOT MODIFY docstring）
3. `git mv myProgram/ActionGroupControl.py myProgram/vendor/`
4. `git mv myProgram/Board.py myProgram/vendor/`
5. 更新 `.claude/hooks/` 內檔案禁改路徑（從 `myProgram/ActionGroupControl.py` 改為 `myProgram/vendor/ActionGroupControl.py`）
6. 更新 `myProgram.py` docstring 第 12 行的 import 範例字串
7. 更新 memory `vendor-files` 內的路徑引用

風險：(a) `.claude/hooks/` 內路徑 hardcode 漏改 → 廠商檔禁改保護失效。改完用一個假 Edit 測試 hook 是否仍 block。(b) Pi 上 `git pull` 後 import 路徑變了，但本專案沒 import 廠商 SDK 任何處（S1 階段），無 runtime 風險。

##### 階段 2：入口檔改名（package 顯式化）
8. `git mv myProgram/myProgram.py myProgram/main.py`
9. 補 `myProgram/__init__.py`（空檔）
10. 補 `myProgram/__main__.py`（內容 `from myProgram.main import main; main()`）— 可選
11. 更新所有外部呼叫端：跑法從 `python -m myProgram.myProgram` 改為 `python -m myProgram` 或 `python -m myProgram.main`
12. 跑 pytest 確認綠

風險：Pi 端使用者可能習慣某指令跑 — 改名後必須在 pineedtodo 寫一筆「以後跑法改為 X」。

##### 階段 3：states/ 檔名一致化（純改名）
13. `git mv` 一次到位：
    - `subroutine_a.py` → `l0_subroutine_a.py`
    - `dialog.py` → `l2_l3_dialog.py`
    - `_product_helpers.py` → `_l2_l3_qty_followup.py`
14. 更新 `states/__init__.py` 內的 import 路徑
15. 更新 tests/sales/ 內所有 import
16. 跑 pytest 確認綠

##### 階段 4：dialog 內部去重（純內部 refactor）
17. 抽 `_dialog_main_loop(play_entry_prompt: bool, ...)` 核心函式
18. `run_dialog` / `_dialog_continue_after_c2_inner` 變 thin wrapper
19. line-by-line diff 確認兩段原邏輯一致，沒有被「合併」誤刪細微分支
20. 跑 pytest 確認綠（這步 159 tests 是最大護身符）

##### 階段 5：nlu/product_parser 拆分（最後做，影響面廣但價值較低）
21. 建 `sales/product_parser.py`，搬 `_PRODUCT_KEYWORD_TO_NAME` + `parse_products` + `_parse_quantity_in_window`
22. `nlu.py` 內維持 `classify_intent` / `has_quantity` / `parse_quantity` / `_CHINESE_DIGIT_MAP`
23. 更新 callers（`states/l2_l3_dialog.py` + tests）的 import 路徑
24. 跑 pytest 確認綠

##### 相依關係與風險點總結

| 階段 | 相依 | 主要風險 | 緩解 |
|---|---|---|---|
| 0 | 無 | tests fixture 漏改 do_action | conftest.py 一次 grep |
| 1 | 無 | `.claude/hooks/` 路徑 hardcode 漏改 → 禁改保護失效 | 改完做 dummy edit 測 hook |
| 2 | 階段 1 完成（避免雙重改動） | Pi 端跑法習慣改變 | pineedtodo 一筆 |
| 3 | 階段 1+2 完成 | states/__init__.py + tests import 漏改 | git grep `from myProgram.sales.states` |
| 4 | 階段 3 完成 | 雙份邏輯藏的細微 bug 被合錯 | line-by-line diff + 159 tests |
| 5 | 階段 4 完成 | parse_products 是 NLU 最複雜函式，搬時不小心動到邏輯 | 純搬不改邏輯，只動 import |

**最高 ROI 三步：階段 0（dead code 清理） + 階段 1（廠商檔搬 vendor/） + 階段 4（dialog 去重）**。若時間有限只能做這三步，已大幅改善結構清晰度與維護性。階段 2/3/5 是「錦上添花」，可延後或併入 BDD+TDD 重啟時順手做。

**最後提醒（給後續執行者）：** 階段 1 搬廠商檔時，務必同步更新 `.claude/hooks/` 內所有 hardcode 路徑與 `vendor-files` memory 內容，否則 hook 禁改保護會失效（這是比 code refactor 更高優先級的安全網）。

---

### 4.2 視角 B：狀態機正確性審查（opus subagent #2）

#### 1. 總評

**整體正確性評分：7.5 / 10**

整體架構乾淨：4 層 cycle dispatch 是顯式的、cart invariant fail-fast 是嚴格的、`enter_hawk_immediately` 在 4 個 subroutine_a 出口都正確設置、`_dialog_checkout_confirm` 的 3-valued return 在所有 caller 都正確分流（True → L4、False/None → `_handle_checkout_confirm_result` 統一處理）。L4 是最複雜層、覆蓋了客服特殊模式 / 6 次催促 / D-final 子狀態，邏輯接合也整齊。

**最關鍵的 5 個發現：**

1. **【critical】`_dialog_checkout_confirm` 內 unclear 達上限 `return False` 之前**沒有累積 unclear**前先檢查 keyword**，而是先 `+1` 再判定 — 但更嚴重的是「達上限 return False」**沒有 speak 任何訊息**告訴顧客「我聽不懂」，顧客只會看到 cart 被清空（caller 才 speak L3_CHECKOUT_REJECT_CLEAR_NOTICE）— 在 timeline 上沒問題，但**`_handle_checkout_confirm_result(False)` 跟「明確說不對」走同樣訊息**，顧客體驗無法區分「我亂答 5 次被踢」vs「我說不對」。

2. **【high】`_dialog_c2_second_stage` 的「YES 後再呼叫 `_dialog_checkout_confirm`」會**疊加 12s + 12s** = 顧客可能被卡 24s** — C-2 已經是「最後機會」確認結帳，再進 confirm（另一個 12s 倒數 + 5 次容忍）形成雙重 timeout 漏斗。流程意圖不清。

3. **【high】L2 timeout（DnC 12s 無回應）的訊息「由於顧客沒有回應，我將繼續叫賣模式」會被顧客聽到** — 顧客明明還在現場（OpenCV 偵測到才進 dialog），對顧客講「沒有回應」+「繼續叫賣」很違和，這句更像對商家報告。

4. **【medium】`logic.py` line 105-109 的 cart-empty assert 註解「L4-B/C/D 已清 cart」遺漏 L4-C「掃碼後返回 L5」這條路徑** — `_l4_service_mode` 內 `response == "s"` 會 return `("L5", 0, 0)` 但 cart **沒被清空**，這時 logic.py 的 next_state 是 L5 不是 `L1_via_subroutine_a`，會直接走到 `_assert_cart_nonempty(cart, "進 L5")`，所以 cart 不空沒問題。**但** assert 註解誤導，且若未來有人改 `_l4_service_mode` 加新 return path 容易踩雷。

5. **【medium】`_dialog_continue_after_c2_inner` 是 `run_dialog` 主迴圈的近乎完整副本**（line 551-663，113 行幾乎複製），維護負擔大、bug fix 必須兩處同步改。已知一處差異（不重播 entry prompt）以外完全重複；任何 dialog 邏輯演進都有「漏改 inner 版」風險。

#### 2. 問題清單（按嚴重度排序）

##### Critical

**【critical】`dialog.py:708-710` ｜ `_dialog_checkout_confirm` unclear 上限 return 與「明確不對」無法區分**
- 描述：unclear 累積到 `CHECKOUT_CONFIRM_UNCLEAR_MAX (5)` 時 `return False`，跟「顧客講『不對』return False」走同一條 caller path（`_handle_checkout_confirm_result` 都 speak `L3_CHECKOUT_REJECT_CLEAR_NOTICE`）。
- 影響：顧客亂答 5 次被踢、訊息卻是「已幫您清空購物車，需要請重新購買」（語意 = 你說不對），未告知「我聽不懂太多次」，與 timeout（有專屬「由於您沒回應」前綴）不對稱。
- 建議：要不是 (a) 引入第四個 return value「unclear_exhausted」並在 `_handle_checkout_confirm_result` 加分支 speak「不好意思我聽不太懂，已取消這次結帳」，要不就直接接受「unclear 達上限 = 視為否認」當設計選擇並在 docstring 寫明。當前 docstring 已寫「亂答達上限 → return False」但行為訊息缺針對性。

##### High

**【high】`dialog.py:512-523` ｜ C-2 YES 後再進 `_dialog_checkout_confirm` = 兩個 12s 漏斗**
- 描述：`_dialog_c2_second_stage` 已經是「最後機會」strict yes/no（12s），顧客答 YES 後又進 `_dialog_checkout_confirm`（再 12s + 5 次 unclear 容忍）。
- 影響：「顧客 timeout 不回應 → 自動進 L4」（line 491），但「顧客明確說要結帳」反而被多踢一輪確認，**主動回應比不回應還慢**。且 C-2 已展示明細在 prompt 內（如果有，但實際看 `L3_C2_WARNING_TEMPLATE` 只說「請問是否要結帳」），confirm 的「總共 X 瓶 Y 杯，正確嗎」可能比較有用，但路徑直覺反向。
- 建議：要不在 C-2 YES → 直接 `return ("L4", 0)`（信任顧客 explicit 意圖），要不就把 C-2 的 prompt 改為「即將結帳 X，請說是/否」一次到位、移除後置 confirm。

**【high】`dialog.py:106-107` + `constants.py:126` ｜ `L2_TIMEOUT_TO_HAWK_VOICE` 對顧客講話語意錯位**
- 描述：訊息「由於顧客沒有回應，我將繼續叫賣模式」是第三人稱 + 機器人視角；顧客明明還在現場（OpenCV 才剛偵測到觸發 dialog）聽到「沒回應」會困惑。
- 影響：UX 問題，顧客體感不專業。
- 建議：改為對顧客語氣，例如「不打擾您了，歡迎再次光臨」或乾脆 silent 直接回 L1 hawk（hawk 的 slogan 自然涵蓋）。

**【high】`dialog.py:494` ｜ C-2 嚴格 yes/no 內 NO 判定優先於 YES，但 `KEYWORDS_CONFIRM_NO` 含「不要」「不用」「沒有」「沒了」**
- 描述：顧客在 C-2 內回「沒了」（在 L3 normal mode = 結帳意圖 = YES 語意）會被先匹配到 `KEYWORDS_CONFIRM_NO` 的「沒了」→ 視為 NO → 清 cart。
- 影響：**直接相反！** 顧客明明意圖結帳卻被當成取消，cart 被清空。同樣陷阱：「沒有了」「不要了」（隱含「不要再買了 = 結帳」）。
- 證據：`constants.py:175` `KEYWORDS_CONFIRM_NO` 含 `["不對", "錯", "改", "wrong", "不是", "沒有", "沒了", "不要", "不用"]`；NLU L3 normal mode 把這些當「結帳」（line 99-100），但 C-2 嚴格 yes/no 把它們當 NO（優先序在 NLU 前）。
- 建議：C-2 內 NO 詞表縮窄到「無歧義否認」(`["不對", "不是", "錯", "不要結帳", "不結"]`)，把「沒了 / 沒有 / 不要 / 不用」交給 YES 分支（line 510 `classify_intent == "結帳"`）。

##### Medium

**【medium】`logic.py:105-109` ｜ assert 註解「L4-B/C/D 已清 cart」漏列 L4-C 掃碼路徑**
- 描述：`_l4_service_mode` 內 `response == "s"` 會 return `("L5", 0, 0)` **不清 cart**（line 310-312），這時 logic.py 看到 next_state == L5 走 elif 不會踩 `_assert_cart_empty`，行為對。但註解只列 B/C/D 都「已清 cart」誤導未來維護。
- 影響：未來若 `_l4_service_mode` 加新「客服模式內取消但保留 cart」變體，assert 會無預警 fail。
- 建議：把註解改為「L4 非 L5 路徑必清 cart（_l4_exit_b/_l4_exit_d_forced/_l4_service_mode 退出三條皆 clear_cart；掃碼 → L5 由 L5 自身 clear）」。

**【medium】`dialog.py:551-663` ｜ `_dialog_continue_after_c2_inner` 是 `run_dialog` 主迴圈完整複製**
- 描述：113 行幾乎逐字複製 main loop body（line 94-248），唯一差別是不重播 entry prompt + unclear_count 從 0 開始。
- 影響：任何 dialog 修改（如新增意圖、改 timeout、改 unclear 流程）必須在兩處同步，漏改 inner 是常見 race source。已經有不一致風險：主迴圈 line 178 `speak(L2_B1_CLARIFY)`（cart-empty checkout-as-unclear），inner 對應 line 613 一致；但若未來分歧無法被 test 抓到。
- 建議：抽出 `_dialog_main_loop_body(cart, think_count, replay_entry: bool, initial_unclear: int)`，主迴圈與 inner 共用；或在 main loop 開頭用 `replay_entry` 旗號決定要不要 speak entry，主迴圈本身即可被 `continue_after_c2` 重入。

**【medium】`dialog.py:171-178` ｜ L2 mode（cart 空）結帳意圖累積 unclear_count，但與 B-1「無法判斷」共用同一個 counter**
- 描述：line 174 `if unclear_count >= UNCLEAR_MAX` 跟 line 230 主迴圈底部「都沒命中 → B-1」共用 `unclear_count`。
- 影響：顧客若交替「結帳意圖 + 亂答 + 結帳意圖」會更快到上限，但邏輯上兩種都「不適用 L2」，共用 counter 合理；只是 speak L2_B1_CLARIFY 兩個分支一致（line 177 + 248），顧客聽到同一句兩次的觸發條件不同，可能困惑。
- 建議：可保留現狀；若要細分，把結帳意圖分流到「`L2_CHECKOUT_NOT_APPLICABLE_CLARIFY`」獨立提示。

**【medium】`l4.py:127-132` ｜ 鏈路 D loop_count 達 `L4_MAX_LOOPS` (6) 時還是會走 `_l4_d_speak_loop_voice(7, ...)` 一次後才在下一輪進 final**
- 描述：line 130 `loop_count += 1` 後 `_l4_d_speak_loop_voice(loop_count, ...)` 內 dispatch table 只到 loop_count 5/6（WARNING），loop_count == 7 時整個 `if/elif` chain 全部不命中 → **silent**。
- 影響：第 7 次 D timeout 沒有催促語音，顧客等到下次 timeout（line 88 一進就 read 不再 speak）才會進 final。實際是「第 7 次 timeout 直接 silent 進 final」，可能違反設計意圖（看樣子設計者想最後一次有特殊語音）。
- 證據：line 207-214 `if/elif` 列 1, 2, 3-4, 5-6；line 87 主迴圈先檢查 `loop_count >= L4_MAX_LOOPS` 跳到 final-confirm 分支。但 line 130 在 loop_count++ 後立刻 speak，若 loop_count 來自 6 → 7 已超出 dispatch table。
- 建議：要不是把 `(5, 6)` 改成 `loop_count >= 5`，要不在迴圈頂端 `loop_count >= L4_MAX_LOOPS` 檢查之前先處理「剛 ++ 到上限的 voice」。

**【medium】`dialog.py:649-663` ｜ `_dialog_continue_after_c2_inner` 主迴圈 unclear 上限路徑沒有重置 think_count**
- 描述：L3 unclear 達上限進 `_dialog_unclear_final_confirmation`，顧客選「繼續」(`return None`) → line 660 `unclear_count = 0` + speak L3_ENTRY_PROMPT 繼續，但 `think_count` 在整個 inner loop 沒 reset 機制（只在 line 605 從 `_dialog_think_silence_l3` 回傳 int 時更新）。
- 影響：若顧客先在主 dialog 想了 2 次、然後進 C-2、回 continue_after_c2、又想 1 次 → think_count 達 3 → 直接踢進 C-2 第二段，**而非預期的「新一輪對話 reset」**。
- 建議：在 final confirmation 選繼續後（line 660）reset `think_count = 0`，或在規格上明確 think_count 跨子流程 persistent 的意圖。

##### Low

**【low】`l4.py:155-162` ｜ `_l4_dispatch_response` 回 None 的註解誤導**
- 描述：line 155-157 「result is None → C 繼續」，但 `_l4_dispatch_response` 還有第二個 None return（E 上限 → 客服 → 客服選繼續，line 407）。註解只列一條來源。
- 影響：純註解問題，邏輯對。
- 建議：補註解「兩條 None 來源：直接 C 鏈路選繼續 / E 達 3 進 C 後選繼續」。

**【low】`dialog.py:362-363` ｜ `_dialog_dispatch_inner_l2` 兜底 `speak(L2_B1_CLARIFY)` 與商品空 list 走 `speak(L2_B3_REASK)` 不一致**
- 描述：line 344 `products = parse_products(response)` 為空 → line 362 落入 `speak(L2_B1_CLARIFY)` — 但「parse_products 空」+「intent 都沒命中」意義 = unclear，跟主迴圈 line 248 一致。
- 影響：但 inner 版**不累積 unclear_count**（inner helper 是「沉默期一次性回應」，沒持續 counter），代表沉默期內亂答無上限保護。實際上 dispatch_inner 返 None 後回沉默期外的 main loop，main loop 自己有 counter — 還算 OK，但設計微 inconsistent。
- 建議：可接受；註解說明「inner 不維持 unclear（沉默期外 counter 接手）」。

**【low】`dialog.py:436-455` ｜ `_dialog_c2_auto_checkout` 純 wrapper 直接 forward `_dialog_c2_second_stage`**
- 描述：line 448-455 整個函式就是 `return _dialog_c2_second_stage(...)`，無任何額外邏輯。
- 影響：dead wrapper；docstring 說「第一段：印警告語音 + 等」但 second_stage 已含這兩步。
- 建議：刪除 `_dialog_c2_auto_checkout`，caller 直接呼 `_dialog_c2_second_stage`（line 109 主迴圈 / line 562 inner / line 590 inner）。

**【low】`dialog.py:466-477` ｜ `_dialog_c2_second_stage` 註解寫「啟動 wall-clock 倒數 deadline = now + AUTO_CHECKOUT_NOTICE」但 `read_customer_input(timeout=remaining)` 並未保證真的依 wall-clock**
- 描述：S1 wire-up 若 `read_customer_input` 用 `input()` 沒 timeout 機制（line 76 註解暗示），則 timeout=remaining 可能被忽略。
- 影響：取決於 wire-up，sales 模組純邏輯 OK。
- 建議：在 read_customer_input callback 規格內明示「必須遵守 timeout」並 wire-up 加守衛。

**【low】`l4.py:299` ｜ `_l4_service_mode` speak + print 同訊息**
- 描述：line 298-299 `speak(L4_C_OPTIONS_PROMPT)` + `print_terminal(L4_C_OPTIONS_PROMPT)`；line 339-340 重複。
- 影響：純樣式選擇；意圖明顯（音 + 文雙保險）。
- 建議：保留，但 docstring 補註。

**【low】`dialog.py:709-711` ｜ confirm unclear 達上限 return False 後**仍進入下一輪 while** while loop（dead code 不會走到，但 control flow 拐彎）**
- 描述：實際 `return False` 後 unreachable；line 711 `speak(prompt)` 永遠不會在 unclear 上限那輪執行。
- 影響：邏輯對；只是讀起來不流暢。
- 建議：把 `if unclear_count >= CHECKOUT_CONFIRM_UNCLEAR_MAX: return False` 提到 speak 之前清晰一些 — 當前順序是 `unclear++; if >= max: return False; speak(prompt)` 已經正確。可不改。

#### 3. Dead Code / Unreachable 列表

1. **`dialog.py:436-455` `_dialog_c2_auto_checkout`** — 完整 wrapper，所有 3 個 caller 都可以直接呼 `_dialog_c2_second_stage`。
2. **`dialog.py:765` `speak(L3_UNCLEAR_FINAL_PROMPT)`** — 在 unclear 上限 `return _dialog_exit_a` 之後，下一輪 while 開頭才 reachable，但 inner unclear_count 累積路徑代表它是 reachable 的 — 不是 dead code，誤判，留著。
3. **`l4.py:202-214` `_l4_d_speak_loop_voice`** — `loop_count == 7` (越界) silent no-op 是部分 dead behaviour，見【medium】#5。
4. **`dialog.py:296` `_dialog_dispatch_inner_l3` return tuple/int/None** — `return think_count` 路徑（line 295 in `_dialog_think_silence_l3`）邏輯 OK 但 caller line 165-166 才更新 `think_count`，這個雙路返回值（int vs None）一致性脆弱，未來易踩。
5. **`dialog.py:709`** — `return False` 後 line 711 `speak(prompt)` 在當次 iteration 不會跑（unreachable from that path），但下次 iteration 會跑 — **非 dead**，誤判。

#### 4. 建議補位的 regression test

1. **C-2 內 NO 詞表歧義** — `test_c2_keyword_meiyou_should_be_yes_not_no()` 模擬顧客在 C-2 回「沒了」/「不要再買了」，斷言進 L4 而非 cart 被清空（揭露【high】#3）。
2. **`_dialog_checkout_confirm` unclear 上限訊息區分** — `test_checkout_confirm_unclear_max_message_differs_from_explicit_no()`，斷言 caller speak 順序在 5 次亂答 vs 1 次「不對」應**不同**訊息（揭露【critical】#1）。
3. **L4 第 7 次 D timeout silent 路徑** — `test_l4_loop_count_7_no_voice_then_enters_final()`，斷言 loop_count 從 6 → 7 那次 timeout 不 speak D voice、直接走 final-confirm。
4. **C-2 YES → checkout_confirm 二度漏斗 timing** — `test_c2_yes_then_confirm_timeout_max_24s()`，斷言「顧客明確說要結帳」最壞情況下會被卡 24s（揭露【high】#2 雙漏斗）。
5. **`think_count` 跨 C-2/continue_after_c2 持續累積** — `test_think_count_persists_through_continue_after_c2()`（揭露【medium】#7）。
6. **L4-C 客服模式內掃碼 cart 未清** — `test_l4_service_scan_keeps_cart()`，斷言 `_l4_service_mode` 內 response='s' 不調 `clear_cart` — 確保 L5 拿到非空 cart（防止未來重構誤加 clear_cart）。
7. **`enter_hawk_immediately` 4 個出口 + 首次** — `test_enter_hawk_immediately_set_correctly_at_4_exits_plus_first_l1()` 5 個 scenarios 驗證 flag 在每個 path 正確 set/reset。
8. **L5 連續呼叫保證 cart 空** — `test_l5_clears_cart_even_if_called_with_extra_items()`（已有可能涵蓋，補保險）。

#### 5. 優先級排序

##### 必修（會造成顧客錯帳 / cart invariant violation / 直接 UX 失敗）
- **【high】#3 — C-2 內「沒了 / 不要」歧義匹配 NO** — 顧客意圖結帳 → cart 被清空，**直接的逆向錯誤**。最迫切。
- **【high】#2 — C-2 YES 後再進 confirm 的 24s 漏斗** — 主動回應比 timeout 慢的邏輯反直覺。

##### 建議修（影響 UX 一致性 / 維護負擔）
- **【critical】#1 — unclear 上限訊息與「明確不對」無法區分** — 改訊息或加 4-valued return。
- **【high】#4 — L2 timeout「由於顧客沒有回應」對顧客講話違和** — 改訊息即可。
- **【medium】#5 — L4 第 7 次 D 催促 silent** — `(5, 6)` → `>= 5` 一行改。
- **【medium】#7 — `think_count` 不跨 C-2 reset** — 規格決定要不要 reset，1 行改。
- **【medium】#6 — `_dialog_continue_after_c2_inner` 113 行 copy-paste** — 抽 helper，預防未來分歧。

##### 可不改（純註解 / 樣式 / dead wrapper）
- 【medium】#4 — logic.py assert 註解誤導（補一行註解即可）
- 【low】#1 — `_dialog_c2_auto_checkout` dead wrapper 可刪可留
- 【low】#2 — `_l4_dispatch_response` None 註解少列一條來源
- 其他 low 註解 / 樣式

#### 6. 補充：審查維度逐條結論

| 維度 | 結論 |
|---|---|
| 1. logic.py cycle 完整 | ✅ 4 層 + subroutine_a 顯式 dispatch；所有 next_state 都有 handler |
| 2. cart assert 覆蓋 | ✅ 進每層都 assert；註解誤導見【medium】#4 |
| 3. dialog return path | 26 個 return 全部 trace；cart 狀態與聲明一致（A 路徑會 clear、C-2 NO 會 clear、L4 路徑會 clear、L5 會 clear）|
| 4. checkout_confirm 3-valued | True / False / None 在 4 個 caller（主 dialog L3 結帳、`_dialog_dispatch_inner_l3`、C-2 YES 後、`_dialog_continue_after_c2_inner` L3 結帳）都統一走 `_handle_checkout_confirm_result` ✅ |
| 5. C-2 wall-clock 預算 | remaining ≤ 0 短路正確；read 回 None 也短路 → L4；嚴格 yes/no 中 NO 詞表歧義 → 【high】#3 |
| 6. L4 sub-state | B-1/2/3 邏輯不適用（這是 L3，作者誤標）；L4 C-1/2 與 D-1/2 邏輯完整，D 達上限的 voice 漏 7 見【medium】#5 |
| 7. L5 cart + mute_opencv | ✅ mute_opencv(THANK_DELAY) → clear_cart → sleep → return；順序正確 |
| 8. subroutine_a + opencv_mute | subroutine_a 只 mute(OPENCV_MUTE=6) ✅；wire-up 的 timestamp 互動本檔不涉及（範圍外）|
| 9. dead code | `_dialog_c2_auto_checkout` 純 wrapper 是 dead wrapper |
| 10. `enter_hawk_immediately` | 4 個出口（dialog reject/timeout: line 89、L4 cancel: line 108、L5 完成: line 123）+ 首次 False（line 54）+ 每輪消費後 reset（line 70）✅ |
| 11. NLU keyword 衝突 | L3 normal「不要」=結帳 vs C-2「不要」=NO 是設計衝突 → 【high】#3；其他 mode 切換正確 |
| 12. 異常一致性 | 純 sales 模組不接 IO，read_customer_input None = timeout 是統一語意；speak 失敗本層不 try/except（由 wire-up swallow），一致 |

**結語：** 整體架構是負責任的（cart assert + 顯式 dispatch + 統一 `_handle_checkout_confirm_result` helper），主要 bug 集中在「人類語意 vs 機器分類」交界（C-2 NO 詞表歧義、checkout_confirm unclear 上限訊息）+ 維護面（inner 副本 + dead wrapper）。**最迫切修「【high】#3 C-2 NO 詞表歧義」**（會直接造成顧客結帳被清 cart 的逆向錯誤）。

---

### 4.3 視角 C：NLU 健壯性審查（opus subagent #3）

#### 1. 總評

**健壯性評分：6.5 / 10**

整體骨架（mode-aware classify_intent / multi-product parser / per-product dedup）設計合理，已涵蓋多數真實互動情境，且使用者實機 bug 累積回饋（紅茶簡體、沒/没、L3 reject 嚴格集、no/nope 層別語意）都有對應修補。但仍存在數個**會在實機被踩到的關鍵風險**：

**最關鍵 5 個發現（依嚴重度排序）：**

1. **【高】L3 normal mode 命中 `_KEYWORDS_REJECT_L3_STRICT` 後 early `return "拒絕"`，但下一輪 fallthrough 邏輯仍會二次評估** — 實際看 code 是 early return 沒問題，但 **L3 模式下 _KEYWORDS_THINK（「想一下」「等等」「考慮」）完全不會被命中**，因為 `if mode == "normal"` 區塊在 STRICT/REJECT 後直接走通用區，而通用區 reject 又會吃掉「不想」（含 in `_KEYWORDS_REJECT`） → 結果**「想一下」「等一下」在 L3 仍可命中通用區（fine），但 L3 顧客講「我想一下、不想買」這類混合語意會被 reject path 優先吃掉**。這是設計選擇但需確認。**真正的問題在後續的 fallthrough：L3 STRICT 不命中、REJECT 不命中時，會走「通用」區的 `_KEYWORDS_REJECT` 再判一次拒絕 → 變成 L3 reject 嚴格度形同虛設**（line 99 已 return「結帳」，所以 line 103 通用 reject 走不到）。經逐行確認此處正確 — 但若未來加 mode 容易破。**屬於程式結構脆弱，非當下 bug。**

2. **【高】KEYWORDS_CONFIRM_NO 含「沒了」「沒有」「不要」「不用」 — 與 L3 normal mode 的「結帳」keyword 重疊** — 在 `_dialog_checkout_confirm` 中（dialog.py 696-711），先試 CONFIRM_NO，命中即 return False（清 cart）。`KEYWORDS_CHECKOUT` 含「沒了」「沒有了」「夠了」，但 CONFIRM_NO 也含「沒了」「沒有」。如果顧客在 checkout confirm 子狀態回「沒了」想表達「我點完了，沒其他要加，結帳吧」（語意 = YES）→ **會被誤判為 NO 而清空 cart**！這是嚴重 false positive。`沒有` 同理：「沒有錯」會被當「沒有」匹配（substring）→ 誤判 NO。

3. **【高】CONFIRM_YES 含「好」單字 + substring match → 「好像不對」「好亂」「好困惑」會被誤判為 YES**。同樣 CONFIRM_NO 含「錯」（line 175）→ 「沒錯」「不錯」會被命中：「沒錯」是肯定但會 match「錯」→ 誤判 NO；「不錯」是肯定/閒聊也會 match「錯」→ 誤判 NO。**但**因為 dialog.py line 704 先檢查 CONFIRM_NO 再 CONFIRM_YES，「沒錯」會先 hit「錯」變 NO，而「沒錯」本意是 YES → **這是已知的關鍵 false positive，必修**。

4. **【中-高】`_KEYWORDS_CHECKOUT` 含 `"tea"` 與 `"no"`，substring match 太短**：
   - `"tea"` 在 `_KEYWORDS_ICED_TEA`：顧客講「I want steak」→ 含「tea」嗎？不含，但「team」「steam」「matter」會誤命中嗎？「matter」不含 tea，「steam」不含 tea，「steak」不含 tea。看似 OK 但 STT 結果若把「ㄊㄧ」之類音節轉成「tea」可能誤判。**「tea」風險中等，建議刪除或改成「冰茶」/ 「奶茶」之類更具體**（雖然店裡只有冰紅茶但「奶茶」會誤導）。
   - `"no"` / `"nope"` 在 `_KEYWORDS_CHECKOUT`：substring match → 「nothing」「none」「now」「nominate」「known」**都含 "no"** → 在 L3 normal mode 全會被當「結帳」。實際顧客講中文為主這風險中等，但若 STT 把口語化「嗯哼」誤轉「know」之類 → 誤判結帳。

5. **【中】簡繁覆蓋只有商品，confirm/reject/checkout 全套都沒簡體變體** — 註解明寫「其他類別暫不支援簡體」是有意識的決定，但使用者實機已踩過「沒/没」要加，**意味簡體輸入是真的會出現**。CONFIRM_YES「對」對應簡體「对」、CONFIRM_NO「錯」對應「错」、CHECKOUT「結帳」對應「结账」/ 「买单」（「買單」簡體）、REJECT「不買了」對應「不买了」等都沒涵蓋。**若使用者 IME 真是簡體，這是隱性 high coverage gap**。

#### 2. 每個 keyword set 風險表

| Set 名 | 現有 keyword | 缺漏建議 | False positive 風險 | False negative 場景 |
|---|---|---|---|---|
| `_KEYWORDS_REJECT` | 不要 / 不用 / 不想 / 不買 / 不了 / 沒有 / 沒 / 没 | 加：「不行」「免了」「免」「不需要」；簡：「不买」「不想买了」「没买」 | **「不一定」含「不」不命中 OK；但「沒問題」含「沒」→ 命中「沒」→ 誤判拒絕！**「不錯」含「不」、不含 reject 詞 OK。「沒事」含「沒」→ 誤判拒絕。「不過」含「不」不命中 OK。實機顧客若說「沒事，我看看」L2 會被拒絕退場。 | 「don't want」「我才不要」（OK 命中）；「不啦」「不要啦」（OK 命中「不要」）；「免」「免了」「不需要」未含 → 漏；台語混用「免啦」漏；「unnecessary」漏 |
| `_KEYWORDS_REJECT_L3_STRICT` | 我不要了 / 不想買了 / 取消購買 / 退出 / 不買了 | 加「取消」「取消這次」「不要這些」「全部不要」「整單取消」；簡「取消购买」「不买了」「我不要了」 | substring「退出」會命中「我要退出去」（離店）OK；「不買了」會命中「我這次不買了」OK；風險低 | L3 顧客「全部刪掉」「都不要了」「都取消」未涵蓋 → 走通用 reject → 變「結帳」（錯！這時其實想清 cart）。**規格上 L3 STRICT 是「整單作廢」的安全門，缺漏會讓顧客「清空訂單」意圖被當「結帳」誤推進 L4** |
| `_KEYWORDS_THINK` | 等等 / 等一下 / 稍等 / 想想 / 考慮 / 想一下 / hold on / wait | 加「再看看」「再想想」「等我一下」「讓我想想」；簡無 think 需求（這類口語繁簡同形） | 「等等再說」OK；「不等了」含「等」？是！「不等了」→ 誤判想一下！但實際對話少見此句。風險低-中 | 「我考慮考慮」OK（「考慮」命中）；「我猶豫一下」漏；「再說」漏；「等下次」含「等」會命中 OK 但語意可能是 reject（顧客「下次再買」） |
| `_KEYWORDS_CHECKOUT` | 結帳 / 買單 / 付款 / 好了 / 就這樣 / 可以了 / 沒了 / 沒有了 / 夠了 / no / nope | 加「結」「結了」「沒別的了」「全部了」「就這些」「OK 了」「這樣就好」；簡「结账」「买单」「付款」「没了」 | **「好了」會命中「再等好了」？「再等好了」含「好了」→ 誤判結帳，但這語意是 think。中等風險**。「可以了」會命中「不可以了」？是！→ 但「不可以了」會先命中 REJECT 嗎？「不可以了」不含 reject 詞 → 命中 CHECKOUT！**重大 false positive**。「沒了」substring 太短，「沒了什麼」「沒了沒了」OK，但「沒了個 X」之類組合會誤判。`no` 短 → 已在發現 4 點出。 | 「就這樣吧」OK；「我點好了」含「好了」命中；「結一下」漏（沒「結帳」） |
| `_KEYWORDS_SERVICE` | 客服 / 聯絡 / 聯繫 / contact / 服務 | 加「店員」「老闆」「人工」「有人在嗎」「叫人」；簡「联系」「联络」「服务」 | 「服務態度好」含「服務」→ 誤判客服。「不需要服務」會先命中 REJECT 嗎？是！「不需要」未涵蓋 REJECT → 命中 SERVICE。「聯絡方式」（無上下文）OK；風險中等 | 「我要找人」「有沒有人」漏；STT 將「客服」誤轉「克服」漏 |
| `_KEYWORDS_ICED_TEA` | 紅茶 / 冰紅茶 / 红茶 / 冰红茶 / hong cha / tea | 加「茶」（太短，**不建議**）；「ice tea」「iced tea」；台語「茶仔」 | **「tea」誤命中：「steak」「matter」「team」「steam」皆不含。但「mate」「retake」「outreach」含 → 罕見英文夾雜風險低。實際更危險：STT 把「踢」「替」「題」轉拼音「ti」可能不太會出「tea」**。仍建議刪「tea」改「iced tea」 | 「冷紅茶」「茶」（光「茶」）漏；中文 STT 把「紅」聽成「宏」（同音）漏 |
| `_KEYWORDS_SCRATCH` | 刮刮樂 / 刮刮乐 / 刮刮 / 彩券 / lottery / scratch | 加「樂透」「即時樂」「刮一張」「彩卷」（錯字常見）；簡「彩券」中文兩岸同字無簡化 | 「刮鬍刀」含「刮」嗎？不含「刮刮」。「彩券」OK，「lottery」substring 在英文中算長 OK。「scratch」風險：「scratchpad」「from scratch」誤命中 — 罕見對話風險低 | 「樂透」「彩卷」（券常被打成卷）漏 |
| `_KEYWORDS_CONTINUE` | 繼續 / 接著 / 繼續買 / 繼續交易 / continue | 加「繼續付」「再付」「再來」；簡「继续」「继续买」「继续交易」 | 「不繼續」會命中「繼續」→ 誤判繼續交易！**這是 L4 客服場景重大 false positive**：顧客講「不繼續了」想退出 → 系統判為繼續 → 卡住。 | 「再來」「再付一次」漏；台語「擱繼續」OK |
| `_KEYWORDS_EXIT` | 退出 / 取消 / 離開 / 算了 / 不買了 / exit | 加「結束」「結束交易」「終止」「不付了」；簡「退出」「取消」中文同字無需，「离开」「算了」（兩岸同）；「不买了」 | 「算了吧再買」會命中「算了」→ 誤判 exit，但語意混亂時這判斷合理。「離開一下」OK。風險低 | 「不付了」「我走了」「掰掰」漏 |
| `KEYWORDS_CONFIRM_YES` | 對 / 是 / 好 / 確認 / 確定 / 沒錯 / yes / ok / correct | 加「正確」「OK」「對的」「沒問題」「行」「嗯」「ya」；簡「对」「确认」「确定」「没错」「正确」「行」 | **「好」單字 substring → 「好像不對」會先命中 NO 還是 YES？dialog.py 先檢查 NO，「好像不對」含「不對」→ NO，那「好亂」「好困惑」NO 不命中 → 走 YES 命中「好」→ 誤判 YES，清 cart 進 L4**。重大 false positive！「是」單字「是嗎」「不是」（NO 含「不是」優先命中）「是的」OK。**單字「好」「是」需要更嚴格 — 建議 require word boundary 或從 set 移除（看下面 patch 建議）** | 「正確」漏；「沒問題」漏；「嗯」漏；台語「好喔」OK（含「好」）；STT「對啊」OK；「行」漏 |
| `KEYWORDS_CONFIRM_NO` | 不對 / 錯 / 改 / wrong / 不是 / 沒有 / 沒了 / 不要 / 不用 | **減「錯」「沒了」「沒有」**（見發現 2/3）；加「不行」「重來」「重新」「修改」「不正確」；簡「不对」「错」「不是」「没有」「没了」「不要」「不用」 | **「沒錯」含「錯」→ 誤判 NO（YES 本意）！**「不錯」含「錯」→ 誤判 NO。「不改了」含「改」→ 誤判 NO（語意 = 不修改 = 確認）。「沒了」如發現 2，與 CHECKOUT「沒了」語意衝突。「沒有」含「沒有錯」「沒有問題」等肯定句 → 全誤判 NO。 | 「不正確」（沒「不對」OK 命中「錯」但「錯」誤導大；應改 keyword）；「重新確認」漏；「不」單字無 |
| `_PRODUCT_KEYWORD_TO_NAME` | 順序：冰紅茶 / 冰红茶 / hong cha / 紅茶 / 红茶 / tea / 刮刮樂 / 刮刮乐 / 彩券 / lottery / scratch / 刮刮 | 加「樂透」「彩卷」「ice tea」 | 與發現 4 同 `tea` 風險。`刮刮`是 prefix，OK（佔位排前）。 | 同 ICED_TEA / SCRATCH |

#### 3. Mode-aware Dispatch 衝突與一致性問題

##### A. L3 normal mode 的 fallthrough 假設

`classify_intent` 結構：

```python
if mode == "l4_service": ... (含 return)
if mode in ("l2", "l4"):
    if no/nope: return "拒絕"   # 不 return 就 fallthrough
if mode == "normal":
    if STRICT: return "拒絕"
    if REJECT: return "結帳"
# 通用區
if REJECT: return "拒絕"
if THINK: return "想一下"
if CHECKOUT: return "結帳"
...
```

**問題：** L3 normal mode 命中 REJECT 短詞會 return「結帳」（line 100），不會走到通用區。但是**沒命中 STRICT 也沒命中 REJECT 時，會 fallthrough 到通用區**。通用區的 `_KEYWORDS_REJECT` 又包含原本 L3 想當「結帳」的詞 → 但這段不會執行（因為若命中已 return）。**結論：邏輯正確但極為脆弱，未來若 reorder 或新增 mode 會立刻破**。建議加 `return None` 之類 guard 或重構成 dispatch table。

##### B. L2 / L4 mode 無 STRICT 概念

L2 mode 顧客若講「我不要了」→ 通用 REJECT 命中「不要」 → 「拒絕」 → 退場。OK，符合預期。
L4 mode 同理。

**但** `_KEYWORDS_REJECT` 含「沒」單字 → L2 顧客講「沒事我看看」→ 命中「沒」 → 「拒絕」退場！**這是 false positive，L2 模式比 L3 更嚴重**（L3 至少命中後是「結帳」，L4 至少有 cart 可以 confirm；L2 直接退場走 L1）。

##### C. L4_service mode 的 no/nope 優先序

L4_service 中 `_KEYWORDS_CONTINUE` 先檢查 → `_KEYWORDS_EXIT` → `["no", "nope"]` → 沒了。但 `_KEYWORDS_CONTINUE` 含「繼續」是 substring，「不繼續」會命中 → 誤判**繼續交易**（如表中 false positive 警告）。**必修**：CONTINUE 應排在 EXIT 之後，或加「不繼續」「停止」等優先比對。

##### D. l4_service mode 沒涵蓋通用「拒絕 / 客服」

`l4.py` 在 `_l4_service_mode` 中（line 324）呼叫 `classify_intent(response, "l4_service")` 後檢查 `"拒絕"` 意圖（line 330）。但 `classify_intent` 在 mode=="l4_service" 下，若不命中 CONTINUE/EXIT/no，**完全沒走通用區判定** — 因為 l4_service block 沒 fallthrough 後續。

**確認：** 重讀 nlu.py line 79-85，l4_service block 只 return CONTINUE/EXIT，不命中就 fallthrough 到 line 87+（`if mode in ("l2", "l4")` 不含 l4_service）、line 96+（mode == "normal" 不含 l4_service），最後走通用區。通用區會命中 REJECT → 拒絕。**OK，邏輯正確**。但 l4.py 的客服模式接收「拒絕」當 exit equivalent（line 330-333）— 這設計合理，但 reject 又含「沒」單字 → 顧客在 L4 客服模式若講「沒問題我看看」會被當拒絕清 cart 退場。

#### 4. Caller 端 NLU 呼叫點審查

| 位置 | mode | 是否合理 | 風險 |
|---|---|---|---|
| `dialog.py:120` 主迴圈 | `l2` / `normal` 依 cart | OK — cart 狀態驅動 mode | 與 cart 同步，無問題 |
| `dialog.py:321` `_dialog_dispatch_inner_l2` | `l2` 寫死 | OK — 只在 L2 沉默期內呼叫 | 但 docstring 註：「若顧客回應加了商品 cart 變非空」→ 此次仍用 l2，下輪才切 normal。可接受 |
| `dialog.py:382` `_dialog_dispatch_inner_l3` | `normal` 寫死 | OK | 同上 |
| `dialog.py:510` C-2 yes 檢查 | `normal` | **冗餘且風險**：`KEYWORDS_CONFIRM_YES` 已含「對/是/好/確認/確定/沒錯/yes/ok」，又呼 `classify_intent==結帳` 涵蓋「結帳/買單/付款/好了/就這樣/沒了/夠了/no/nope」。**「沒了」「nope」會被當 YES → 進 L4**。「nope」=不要的英文，居然被當 YES，這明顯違背直覺。**必修：移除 `classify_intent(...) == "結帳"` 那條，或改用 strict CONFIRM_YES only** |
| `dialog.py:571` C-2 dispatch_inner | `l2/normal` 依 cart | OK |
| `dialog.py:704-706` checkout confirm | NO 用 CONFIRM_NO，YES 用 CONFIRM_YES | 順序：NO 先 → YES 後。**「沒錯」會被當 NO**（NO 含「錯」）— 必修 |
| `dialog.py:757` final confirmation | `l4_service` | OK — 借 l4_service 的繼續/退出語意給 L3 unclear final |
| `l4.py:269` final confirmation | `l4_service` | OK |
| `l4.py:324` service mode | `l4_service` | OK — 接通用 fallthrough 的拒絕意圖 |
| `l4.py:371` dispatch_response | `l4` | OK — l4 mode 把 no/nope 轉拒絕，符合「L4 不要付」語意 |
| `_product_helpers.py:111` qty follow_up | 動態 mode | OK |

**最重大 caller-side bug：dialog.py:510 的「YES 條件含 intent==結帳」會讓「nope/no/沒了」當 YES 推進 L4 → 顧客錢包風險**。

**冗餘：** dialog.py:494 NO 先檢查含 CONFIRM_NO（含「沒了」「不要」），dialog.py:510 YES 含 intent==結帳（也含「沒了」「no」）。NO 先檢查所以「沒了」會優先變 NO（清 cart）— 反而從顧客角度也是 false positive！顧客講「沒了」本意是「沒其他要加，結帳吧」（YES）→ 卻被當 NO 清 cart。**這是 spec 衝突：CHECKOUT_KEYWORDS 設計「沒了 = 結帳」vs CONFIRM_NO「沒了 = 不結帳」**。

#### 5. 拼音 fallback / 全半形 / 大小寫處理問題

##### 大小寫
- `parse_products` line 238 對 `text_lower = text.lower()` 處理 → 大小寫不敏感 OK。
- `classify_intent` **完全沒做 lower 處理** → `KEYWORDS_CHECKOUT = ["no", "nope"]` 顧客輸入「NO」「No」「NOPE」**不命中**！必修。
- `KEYWORDS_CONFIRM_YES` 含「yes / ok / correct」也是。「YES」「Yes」「OK」「Ok」**不命中**！必修。

##### 全形 / 半形數字
- `has_quantity` line 146 `re.search(r"\d+", text)` — `\d` 在 Python re 預設**會匹配全形數字**（Unicode 屬性下「０-９」屬 Nd category）。確認：Python 3.x `re` 模組 `\d` 預設匹配 Unicode digits → **OK**。
- 終端輸入比對 `response == "1"` / `"2"` / `"s"` — **嚴格 ASCII**。顧客若在全形輸入法下打「１」「２」**不命中**！對終端輸入這風險低（使用者自己操作），但若 STT 結果含全形數字 → 比較失敗。建議 normalize 一次。

##### 全形空白
- `parse_products` 不處理 spaces；`"紅茶　1"`（全形空格）會把全形空格當分隔 → `_parse_quantity_in_window("　1")` 用 `re.findall(r"\d+", ...)` → 仍找到「1」OK。但若全形數字「１」配上 `re.findall(r"\d+", ...)` → Python 3 預設 Unicode `\d` 是命中的 → OK。

##### 拼音 fallback
- 「hong cha」「lottery」「scratch」「tea」「contact」「continue」「exit」「wait」「hold on」「yes」「ok」「correct」「wrong」「no」「nope」
- **命中率**：店家在中國台灣，顧客主要講中文 → 命中率極低。但仍**有風險**（tea / no / nope 短詞引起 false positive 如上述）。
- **建議**：
  - **刪掉**：`tea`（誤命中風險）/ `no` / `nope`（短詞 + 顧客本來就不會打英文反駁 — 留中文「不要 / 沒了」即可）
  - **保留**：`lottery` / `scratch` / `hong cha` / `continue` / `exit` / `contact` / `wait` / `hold on`（這些 substring 較長，誤命中風險低）
  - **重新評估**：`yes` / `ok` / `correct` / `wrong` — 顧客真的會說英文 confirm 嗎？建議刪除，只保留中文 CONFIRM

#### 6. 具體 Patch 建議

##### 必修（會在實機誤判錢包 / 誤判 cart）

```python
# nlu.py: 大小寫不敏感（在 _contains_any 內處理一次）
def _contains_any(text: str, keywords: list) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)
```
理由：CHECKOUT「no/nope」、CONFIRM「yes/ok」原本只匹配小寫。修這個 → 全 keyword 受惠。

```python
# constants.py: CONFIRM_NO 移除有歧義的詞，CONFIRM_YES 移除「好」單字
KEYWORDS_CONFIRM_YES: list = ["對", "是的", "確認", "確定", "沒錯", "正確", "对", "是", "确认", "确定", "没错", "正确", "yes", "ok", "okay", "correct"]
KEYWORDS_CONFIRM_NO: list = ["不對", "不正確", "不是", "不要", "不用", "重新", "重來", "wrong", "不对", "不正确", "不是", "不要", "不用"]
```
理由：
- 移除 CONFIRM_YES「好」單字 → 「好像」「好亂」不再誤命中
- 移除 CONFIRM_NO「錯」「沒了」「沒有」「改」 → 「沒錯」「不錯」「不改了」「沒有錯」「沒了（語意=結帳）」不再誤命中
- 「是」改「是的」避免「不是」/「是嗎」substring 衝突（但「是的」會被「不是的」誤判 NO？「不是的」含「不是」會先 hit NO，OK）
- 補簡體

```python
# dialog.py:510 移除 classify_intent==結帳 那條
is_yes = (
    response == "1"
    or any(kw in response for kw in KEYWORDS_CONFIRM_YES)
)
```
理由：避免「沒了 / no / nope」被當 YES 推進 L4。

```python
# nlu.py: _KEYWORDS_REJECT 移除「沒」單字
_KEYWORDS_REJECT = ["不要", "不用", "不想", "不買", "不了", "沒有", "没"]
```
理由：「沒」單字會誤命中「沒事」「沒問題」「沒空」。如果使用者實機真的需要單字「沒」，改用更安全的「沒了不要」「沒打算」之類組合。
**但**：使用者已實機踩過要加「沒」（line 20-23 註解），所以這要跟使用者確認回退條件。

```python
# nlu.py: _KEYWORDS_CONTINUE 加先排除否定
def classify_intent(text, mode="normal"):
    if mode == "l4_service":
        # 先擋「不繼續 / 不要繼續」否定組合
        if any(neg in text for neg in ["不繼續", "不要繼續", "別繼續"]):
            return "退出交易"
        if _contains_any(text, _KEYWORDS_CONTINUE):
            return "繼續交易"
        ...
```
理由：避免「不繼續」substring 命中「繼續」誤判。

```python
# nlu.py: _KEYWORDS_CHECKOUT 移除短/歧義詞
_KEYWORDS_CHECKOUT = ["結帳", "買單", "付款", "結了", "結一下", "就這樣", "可以了", "沒了", "沒有了", "夠了", "结账", "买单", "付款", "没了", "够了"]
```
理由：移除「no / nope」（移到 L2/L4 各 mode 各自處理；L3 normal 不應靠 no/nope）；移除「好了」（誤命中「再等好了」）；加簡體。

##### 建議修（覆蓋率 + 一致性）

```python
# nlu.py: _KEYWORDS_REJECT_L3_STRICT 補強
_KEYWORDS_REJECT_L3_STRICT = [
    "我不要了", "不想買了", "取消購買", "退出", "不買了",
    "全部取消", "全部不要", "都不要", "都取消", "整單取消",
    "取消", "取消订单", "不买了",  # 含簡體
]
```
理由：L3 顧客講「全部取消」「都不要了」是「整單作廢」的常見表達，缺漏會走到通用 reject → 變「結帳」誤推進 L4。

```python
# nlu.py: _KEYWORDS_ICED_TEA 刪「tea」改更具體
_KEYWORDS_ICED_TEA = ["紅茶", "冰紅茶", "红茶", "冰红茶", "hong cha", "iced tea", "black tea"]
```

```python
# nlu.py: 全形數字 normalize（給終端 1/2 對比用）
def _normalize_digits(text: str) -> str:
    """全形數字 → 半形（給 == "1" / "2" / "s" 直接比對用）"""
    return text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

# caller 在比 response == "1" 前先 normalize
```

##### 商品 alias 抽到 constants

**建議**：`_PRODUCT_KEYWORD_TO_NAME` 應該移到 `constants.py` 命名為 `PRODUCT_ALIASES`，理由：
- 新增商品時只動 constants（PRODUCTS dict + PRODUCT_ALIASES 同檔）
- NLU 模組純函式語意更清楚
- 測試可獨立 import alias 表

不必修但會讓未來新增商品更乾淨。

#### 7. 優先級排序

##### 必修（影響交易正確性）
1. **移除 `dialog.py:510` 的 `classify_intent==結帳` 條件**（C-2 yes 判定）— 防止「no/nope/沒了」誤推進 L4。
2. **CONFIRM_NO 移除「錯 / 沒了 / 沒有 / 改」**（constants.py）— 防止「沒錯 / 不錯 / 不改了」誤清 cart。
3. **CONFIRM_YES 移除「好」單字 / 改用「好的」**（constants.py）— 防止「好像不對 / 好亂」誤推進 L4。
4. **_contains_any 加 `.lower()` 處理**（nlu.py）— 大小寫不敏感，CHECKOUT/CONFIRM 英文 keyword 才能真正生效。
5. **`_KEYWORDS_CONTINUE` 加否定守衛**（nlu.py l4_service）— 防止「不繼續」誤判繼續交易。

##### 建議修（覆蓋率 / 邊角）
6. **`_KEYWORDS_REJECT_L3_STRICT` 補「全部取消 / 都不要 / 整單取消 / 取消」**（防 L3 整單作廢誤判結帳）。
7. **`_KEYWORDS_REJECT` 重新評估「沒」單字風險**（先跟使用者確認實機案例 vs 「沒事 / 沒問題」誤判風險）。
8. **`_KEYWORDS_CHECKOUT` 移除「好了 / no / nope」**（短詞高誤命中）。
9. **`_KEYWORDS_ICED_TEA` 刪「tea」改「iced tea」**。
10. **全形數字 normalize**（在 caller 端對 response 做 `translate`）。
11. **CONFIRM_YES / CONFIRM_NO / CHECKOUT / REJECT 補簡體常用詞**（对 / 错 / 没 / 不买 / 结账 / 买单）。

##### 可不改（風險低或設計選擇）
12. 商品 alias 抽到 constants — 重構為主，不修當下 bug。
13. classify_intent 重構成 dispatch table — 美化結構，當下邏輯正確。
14. 拼音 fallback 全部刪除 — 與其全刪不如逐個審查，且 lottery/scratch/contact/exit/wait 風險低。
15. tkinter / threading 相關 — 與本次 NLU 審查無直接關聯（路徑規範 / 多線程規範自動載入但不適用於純函式 NLU）。

**底線總結：** NLU 本身骨架 OK，但**確認/檢視子狀態的 keyword 跟主流程 keyword 有不可忽視的語意衝突**（特別是「沒了」在 CHECKOUT 與 CONFIRM_NO 雙重歸屬），加上「好 / 錯」單字 substring 命中過於寬鬆，會在實機顧客自然語言下產生 2~3 種「錢包風險 / cart 風險」誤判。**第 1-5 項必修**完成後健壯性可拉到 8.5/10；後續覆蓋率與簡體補強拉到 9+。

---

### 4.4 視角 D：橫切面 /review 適配版審查（主 agent）

> **註：** `/review` 內建 skill 原設計為 GitHub PR 審查（`gh pr list/view/diff`），與「審查當前分支 myProgram/ 資料夾」不契合（且使用者 scope arg 被當 PR 號傳入）。改採 /review 五大維度（**正確性 / 慣例 / 效能 / 測試 / 安全**）對 myProgram/ 做適配審查，**避開** 3 個 opus subagent 已深挖的「結構/檔名 / 狀態機 / NLU」三大區塊，補上**橫切面**（wire-up 層 / 例外一致性 / 風格 / 效能 / 安全）。

無 open PR；審查標的：current main branch (db1dcf3), 14 個 .py 檔（含 2 個廠商檔，read-only 黑盒，不審內容）。

#### 1. 總覽

myProgram/ 是「Pi 上跑的互動式銷售輔助機器人 S1 wire-up + sales 業務邏輯」。S1 階段純單線程、無 threading、無真實 IO、所有對外動作以 `[標記]` 文字印出。**設計選擇明確（callback 注入、廠商隔離、cart-state-driven dialog），實作品質中上**。

**橫切面評分（5 維度）：**

| 維度 | 分數 | 摘要 |
|---|---|---|
| 正確性（含 wire-up）| 7.5/10 | wire-up state mutation 邏輯一致；C-2 / CONFIRM keyword 歧義是已知風險（其他 subagent 細列） |
| 慣例遵守 | 8/10 | 繁中字串完整；snake_case 全用；docstring 詳盡；少數簡體字滲入註解 |
| 效能 | 7/10 | substring `in` heavy 但 O(N) 可接受；單線程 input() 是 blocking 限制（已知，S4 處理） |
| 測試覆蓋（觀察性） | N/A | tests/sales/ 在 scope 外（172 tests 安全網）；wire-up 層無單元測試屬合理 |
| 安全 | 6/10 | `sys.exit(0)` 從 customer 層出口、`input()` raw 直接傳入 NLU 無 sanitize、廠商檔位置隔離不足 |

#### 2. 正確性 — wire-up 層細審

`myProgram/myProgram.py` 是橫切重點（其他 subagent 沒覆蓋）。

##### 2.1 `_S1State` mutable state 一致性 ✅

`opencv_enabled` / `opencv_dwell` / `opencv_mute_until` 三個欄位的 mutation 邏輯統一在 6 個 callback 內（enable / disable / mute / unmute / dwell_seconds / read_terminal_key）。Mutation 集中、closure 共享 state 設計乾淨。

##### 2.2 【medium】`unmute_opencv` 與 `mute_opencv` 對稱性微缺

```python
def mute_opencv(seconds):
    state.opencv_enabled = False   # 同時關 enabled
    state.opencv_dwell = 0.0       # 清 dwell
    state.opencv_mute_until = ... + seconds

def unmute_opencv():
    state.opencv_enabled = True    # 開 enabled
    state.opencv_mute_until = 0.0  # 清 mute_until
    # ❌ 沒清 state.opencv_dwell — 不對稱
```

若 unmute 時剛好有殘留 `opencv_dwell ≥ OPENCV_DWELL`（雖然 mute 時已清，但若呼叫順序是 `mute → 後續邏輯設 dwell（理論上 mute 期間 dwell_seconds 已擋住，但若有人在 mute_until 過期後手動 set dwell 再 unmute）→ unmute`，dwell 殘留），unmute 後立即觸發 detection。**S1 階段 `unmute_opencv` 從 logic.py 沒被呼叫**（見 grep `unmute_opencv` only 出現在 myProgram.py 內），但 callback 留著給 future（子例程 A 方案 A 不呼叫，docstring 已說明）。**建議：unmute 內補 `state.opencv_dwell = 0.0` 對稱**，即使現在無 caller 也預防未來踩雷。

##### 2.3 【low】`read_terminal_key` 的 'c' 鍵 return 邏輯非直覺

```python
if raw == "c":
    state.opencv_dwell = OPENCV_DWELL + 0.5
    ...
    return ""  # 不返回有效鍵；由 L1 hawk 主迴圈下次 check opencv
```

side-effect 設 dwell + return 空字串，迫使呼叫者下次 iteration 走 opencv check 分支。設計合理（避免 'c' 被當 menu key 解析），但 docstring 已標註「不返回有效鍵」算清楚。**Pass，但若未來 L1 主迴圈重構，這個隱性 contract 容易踩**。

##### 2.4 【medium】`read_customer_input` 的 `q` 直接 `sys.exit(0)` — 越層退出

```python
def read_customer_input(timeout):
    ...
    if raw == "q":
        print("[系統] 程式結束（顧客層 q 退出）")
        sys.exit(0)  # ❌ 從 callback 直接 sys.exit，繞過 logic.py 主迴圈所有 invariant
```

問題：
1. `sys.exit` 走 `SystemExit` 例外，會跳過 dialog/L4/L5 內**所有 cart cleanup 邏輯**。若顧客 q 時 cart 非空（在 L3 / L4 / L5），cart 還在 state 內（雖然 process exit，無 leak，但**違反 cart invariant 設計精神**）。
2. `main()` 雖然有 `except SystemExit: pass` 接著，但 `try` 內已是 logic.run 結束才會收 — sys.exit 立即上拋無問題，但 cart 結束狀態混亂。
3. 跟 `exit_program` callback（L1 商家 q）做的事一樣，但路徑不同：商家 q 走 `run_l1 → exit_program`（cart 此時應已 empty by assert），顧客 q 走 `read_customer_input → sys.exit`（cart 可能在任何狀態）。**兩條 exit 路徑語義不對稱**。
4. docstring 說「production 不會有人講『q』當顧客語音」承認這是 S1 trick — OK，但 S4 接 STT 後若 STT 輸出含 「q」字母（如「I need a Q」之類），會誤觸發。

**建議：** 顧客 q 改用「return 特殊 sentinel + logic 層 handle」或保持但加 cart 清理（`cart_module.clear_cart(...)` — 但 callback 看不到 cart，需另外注入）。**S1 階段可接受，標 medium 記錄 future-S4 必修**。

##### 2.5 【low】`sleep` / `schedule` callback 是 stub「印訊息但不真等待」

```python
def sleep(seconds):
    print(f"[等待] {seconds}s（S1 跳過實際 sleep，立即返回）")
def schedule(seconds, fn):
    print(f"[schedule] 排程 {seconds}s 後執行 {fn.__name__}（S1 不真排程，立即跳過）")
```

S1 stub 合理（docstring 解釋為何不 `time.sleep` — 避免卡住主線程 q 退出）。但**`schedule` 在 logic.py 從未被呼叫**（grep 確認），是 dead callback。**建議：S1 階段乾脆從 callback dict 拿掉**，S4 真用 timer 時再加；符合 karpathy「no premature abstraction」（同 opus subagent #2 的 `do_action` dead parameter 發現）。

##### 2.6 wire-up 層日誌噪音（observability）

print prefix 慣例：`[商家]` / `[顧客]` / `[系統]` / `[語音]` / `[動作]` / `[opencv]` / `[等待]` / `[schedule]` / `[模擬]` / `[模擬提示]` — **10 種 prefix，已開始失控**。實機接 OpenCV / 真語音後，部分 prefix 會消失，但 `[模擬]` / `[模擬提示]` 屬 S1-only 噪音。**建議 S4 過渡前統一一次**：產出 production print 與 S1 模擬 print 分流（如 `_s1_print()` helper 內部抑制 / 加 env 旗號），現在留註記即可。

#### 3. 慣例遵守

##### 3.1 繁中 ✅
所有 user-facing 字串（print / speak / docstring）都是繁中。CLAUDE.md 規範完美遵守。

##### 3.2 【low】部分註解滲入簡體字 — 修一下
`nlu.py` 內有「在 _l4_service 中（line 324）呼叫 classify_intent 后」這類繁簡混用註解（grep 結果）。使用者 IME 設定簡體（user_environment memory），偶爾漏轉。**建議：commit hook 加簡繁檢測**（如偵測常用簡體字 [对 / 错 / 后 / 没 / 这 / 来] 在 .py 註解內 → 警告），自動防漏。

##### 3.3 ✅ snake_case 全用
prod code 函式 / 變數命名一致；私有 helper 一律 `_` 前綴；常數 SCREAMING_SNAKE。

##### 3.4 ✅ docstring 詳盡（甚至過度）
所有公開函式都有 docstring，含 Args / Returns / 設計理由。部分 docstring 達 30+ 行（如 `_dialog_continue_after_c2_inner`），對「規格還在演化」階段合理；穩定後可考慮 trim 重複內容。

##### 3.5 【low】import 順序非 PEP8 嚴格
`myProgram.py` line 21-25：stdlib (sys, time) → 自家 module (logic, constants)，✅ OK。
`logic.py` line 25-26：兩個自家 import 都 from absolute path，✅ OK。
**整體 OK**，但無 `isort` / `ruff` 自動化保護。建議 future 階段加。

#### 4. 效能

##### 4.1 【low】NLU substring matching O(N×M)
`classify_intent` 對每次 customer input 做 `for kw in _KEYWORDS_X: if kw in text` × 多個 set。當前 keyword 總量 ~80 個，input 字串典型 <20 字 → 每呼叫 ~1600 個 char comparison，**對話頻率 1 Hz 以下完全可接受**。若未來 keyword 爆量（>500）才需考慮 trie / aho-corasick。**當前無問題**。

##### 4.2 【medium】`input()` blocking 是已知 S1 限制
單線程 `input()` 卡住主迴圈，「商家層 q」依賴使用者輸入才能退出。`sleep` / `schedule` callback 是 stub 規避。**S4 上 threading + queue 處理**（threading-conventions 規範），無 action item。

##### 4.3 ✅ cart dict 操作 O(1)
`add_item` / `get_quantity` / `is_empty` / `clear_cart` 全 dict 原生操作，無 list scan，乾淨。

##### 4.4 【low】logic.py 4 層迴圈無 yield / 無 instrumentation
無 metrics / no profiling hook。S1 階段 OK；S4+ 真實際時序時建議在每層進入時記 timestamp，事後分析瓶頸。

#### 5. 測試（觀察性）

myProgram/ 內**無內聯測試** — 全部在 `tests/sales/` (user scope 外)。

##### 5.1 ✅ Wire-up 層無單元測試是合理的
`myProgram.py` 全是 IO callback（input/print），測試需大量 mock — 違反 testing-anti-patterns。172 個 tests/sales/ 測**業務邏輯**而非 wire-up，正確分層。

##### 5.2 【low】wire-up 缺整合 smoke test
若有「跑一個固定腳本（c → 1 → 冰紅茶 → Enter → 是 → 結束）斷言不 crash」的 smoke test，可預防 wire-up regression。但 stdin mock 麻煩，**S1 階段標 nice-to-have**。

##### 5.3 ✅ Production code 自身無 `print` debug 殘留
grep `myProgram/sales/` 無 `print(` 殘留（除註解），全靠 callback 注入。clean。

#### 6. 安全

##### 6.1 【medium】customer 輸入 raw 字串直接進 NLU，無 sanitize / 長度限制
```python
raw = input(...).strip()
return None if raw == "" else raw
```
無上限長度、無控制字元剔除。S1 stdin OK（使用者自己打）；S4 接 STT 後若 STT 結果含換行 / 控制字元 / 超長字串（如 10MB 雜訊），會：
- print 整段污染 log
- substring match 變慢（4.1 提到的 O(N×M) 變大）
- 若未來接 HTTP / WebSocket 傳 STT result，無 length cap 是 DoS vector

**建議：** `read_customer_input` 加 `raw = raw[:200]`（200 字上限對話夠用）+ strip 控制字元。**S4 wire-up 必修**。

##### 6.2 【low】customer q 直接 sys.exit（見 2.4）
S1 trick 已接受，但 S4 接 STT 後須改 — 已記。

##### 6.3 ✅ 廠商檔內容禁改 + S1 不 import
myProgram.py docstring line 11 明寫「S1 階段不 import 廠商 SDK」；grep 全 myProgram/sales/ 無 `import.*ActionGroupControl|Board`。**良好隔離**。

##### 6.4 【medium】廠商檔位置安全性
`ActionGroupControl.py` / `Board.py` 與業務碼平鋪於 `myProgram/` root。`.claude/hooks/` 用路徑 hardcode 禁改保護。**若有人重構搬位置但漏改 hook → 禁改保護失效**。同 opus subagent #1 結論：應搬到 `myProgram/vendor/` + hook 路徑同步更新，作為「明顯不該動」的視覺隔離 + 給安全保護一個可預測的路徑前綴。

##### 6.5 【low】無 secrets / credentials in code ✅
grep `password|secret|token|api_key` 在 myProgram/ 全無命中。✅

##### 6.6 【low】`sys.exit(0)` 在兩處 callback（exit_program / read_customer_input 的 q）
兩處都是設計性 exit，無 dead code 路徑。OK。

#### 7. 具體改進建議（按優先級）

##### 必修（與 opus subagent 們發現的重疊以及 wire-up 獨有的）
1. **C-2 / CONFIRM keyword 歧義**（**3 個 opus subagent 報告中至少 2 個已詳細列**）— 顧客錢包風險。
2. **`unmute_opencv` 補 `state.opencv_dwell = 0.0` 對稱**（myProgram.py:127）— 一行 fix，預防未來踩雷。

##### 建議修（風格 / dead code / 安全前置）
3. **移除 `schedule` callback 與 `do_action` callback**（S1 dead，karpathy「no premature abstraction」）— 留 stub 簽名待 S3/S4 真用時加。
4. **`read_customer_input` 加長度上限 `raw[:200]` + 控制字元 strip**（S4 接 STT 前必修，但 S1 加無害）。
5. **simplified-zh detector hook**（防註解漏轉）— 短期可手動 grep `[对错后没这来]` 修。
6. **廠商檔搬 `myProgram/vendor/`**（opus subagent #1 已建議；安全與可讀性雙贏）。

##### 可不改（架構決策 / S4 才處理）
7. wire-up `print` prefix 10 種噪音 — S1 模擬期接受。
8. wire-up 缺整合 smoke test — 接受（172 unit tests 已足）。
9. customer q sys.exit 越層 — S1 trick，已 documented。

#### 8. 與 3 個 opus subagent 報告的關係

| 維度 | 本報告覆蓋 | 已由 opus subagent 覆蓋 |
|---|---|---|
| 結構 / 檔名 | — | ✅ #1 結構審查（含廠商檔搬 vendor/） |
| 狀態機正確性 | — | ✅ #2（含 C-2 NO keyword 歧義 / D loop 7 silent / inner copy-paste） |
| NLU 健壯性 | — | ✅ #3（含「沒了」雙重歸屬 / 「好」單字 substring） |
| wire-up 層細節 | ✅ 本報告 §2 | — |
| 慣例 / 風格 | ✅ §3 | — |
| 效能 | ✅ §4 | — |
| 測試觀察性 | ✅ §5 | — |
| 安全 | ✅ §6 | — |

整體無顯著漏網。**最大共識點：「廠商檔位置應隔離」+「dead callback / dead parameter 應清理」+「customer-input 路徑（NLU + wire-up）有歧義 / sanitize 不足」**。

---

## 5. 建議執行 Roadmap

按「風險最小、修一條測一條、incremental rebuild 精神」分階段。每階段獨立 worktree + commit + push（hook sync）+ pytest 確認綠 + 使用者實機驗收才開下一階段。

### 階段 P0：keyword 歧義急救（最高優先 — 顧客錢包）

涵蓋必修 M1, M2, M3, M4, M5, M6。

**動作：**
1. `constants.py` — 縮窄 `KEYWORDS_CONFIRM_NO`（移除「錯/沒了/沒有/改」）；縮窄 `KEYWORDS_CONFIRM_YES`（「好」改「好的」）；補簡體變體
2. `dialog.py:510` — 移除 `classify_intent==結帳` 條件
3. `nlu.py` — 加 `_contains_any` helper 做 `.lower()` 統一處理
4. `nlu.py l4_service` 分支 — 加「不繼續/不要繼續」否定 guard 排在 CONTINUE 前
5. `nlu.py _KEYWORDS_REJECT` — 與使用者確認「沒」單字風險權衡（先列 trade-off 給使用者選）

**測試：** 補 4 個 regression test（B#4 列的測試 1 + 2 + 4 + 7）；既有 172 tests 必須全綠

**Pi 端：** 無 — 純 code

### 階段 P1：dead code 清理（最低風險，最高 ROI）

涵蓋必修 M7（廠商檔搬位置）+ 建議修 S7（do_action / schedule dead）。

**動作：**
1. 移除 `do_action` callback 從 dialog/l4/l5 簽名 + logic.py call site + myProgram.py _build_callbacks
2. 移除 `schedule` callback 同上
3. 移除 `_dialog_c2_auto_checkout` dead wrapper（3 caller 改直呼 `_dialog_c2_second_stage`）
4. 移除 dead pyc：`Remove-Item -Recurse __pycache__`（local 清理）
5. 建 `myProgram/vendor/` + `__init__.py` (DO NOT MODIFY docstring)
6. `git mv` 廠商檔到 `vendor/`
7. **同步更新 `.claude/hooks/` 內 hardcode 路徑**（block-vendor-edit.ps1）
8. 更新 `myProgram.py` docstring import 範例字串
9. 更新 memory `vendor-files`（pineedtodo？或主 agent 自己更新 memory？— memory 更新不走 worktree）
10. 跑 pytest 確認 172 tests 綠
11. 改完 dummy edit 廠商檔測試 hook 仍 block

**Pi 端：** 無（廠商檔路徑變但 sales/ 沒 import 廠商 SDK）

### 階段 P2：dialog inner 去重 + L4 第 7 次 silent 修補

涵蓋建議修 S4 + S5。

**動作：**
1. `l4.py` — `_l4_d_speak_loop_voice` dispatch 從 `(5, 6)` 改 `>= 5`
2. `dialog.py` — 抽 `_dialog_main_loop(play_entry_prompt: bool, initial_unclear: int)` helper；`run_dialog` 與 `_dialog_continue_after_c2_inner` 變 thin wrapper
3. line-by-line diff 確認原邏輯一致
4. 跑 pytest 確認綠

**Pi 端：** 無

### 階段 P3：checkout confirm UX 對齊

涵蓋建議修 S1, S2, S3, S6, S16。

**動作：**
1. `_dialog_checkout_confirm` 改 4-valued return（True/False/None/"unclear_exhausted"）
2. `_handle_checkout_confirm_result` 加 unclear_exhausted 分支 speak 專屬訊息
3. C-2 YES 後**直接** `return ("L4", 0)`，移除疊加 `_dialog_checkout_confirm`（取消雙漏斗）
4. `constants.py L2_TIMEOUT_TO_HAWK_VOICE` 改顧客語氣（如「不打擾您了，歡迎再次光臨」）
5. `_dialog_continue_after_c2_inner` final confirmation 選「繼續」後同步 reset `think_count = 0`
6. `logic.py:105-109` 改 assert 註解，正確列出三條 L4 清 cart 路徑 + 一條 L5 不清

**Pi 端：** 無（純邏輯）

### 階段 P4：keyword 覆蓋率補強

涵蓋建議修 S13, S14, S15。

**動作：**
1. `nlu.py _KEYWORDS_CHECKOUT` — 移除「no/nope/好了」；補「結了/結一下/就這些」；補簡體
2. `nlu.py _KEYWORDS_REJECT_L3_STRICT` — 補「全部取消/都不要/整單取消/取消」；補簡體
3. `nlu.py _KEYWORDS_ICED_TEA` — 「tea」改「iced tea」「black tea」
4. 對應 test 補

**Pi 端：** 無

### 階段 P5：wire-up 層健壯化（S4 過渡前）

涵蓋建議修 S10, S11, S12。

**動作：**
1. `myProgram.py unmute_opencv` 補 `state.opencv_dwell = 0.0` 對稱
2. `myProgram.py read_customer_input` 加 `raw = raw[:200]` 長度上限 + 控制字元 strip
3. `myProgram.py` 加 `_normalize_digits` helper 處理全形數字 → 半形（用在 `response == "1"/"2"/"s"` 比對前）
4. customer "q" 改 return sentinel（如 `"__customer_quit__"`），logic 層 handle 走正常 cart cleanup 路徑 — 此項較大，可延後

**Pi 端：** 無

### 階段 P6（選擇性）：結構命名一致化

涵蓋建議修 S8, S9（風險中、ROI 中）。

**動作：**
1. `git mv myProgram/myProgram.py myProgram/main.py` + 補 `myProgram/__init__.py`（空檔）+ 可選 `__main__.py`
2. `git mv` states/ 內 3 檔：`subroutine_a.py` → `l0_subroutine_a.py`、`dialog.py` → `l2_l3_dialog.py`、`_product_helpers.py` → `_l2_l3_qty_followup.py`
3. 更新 `states/__init__.py` + tests/ 內 import paths
4. 跑 pytest 確認綠

**Pi 端：** ⚠️ 跑法改變 — 寫 pineedtodo 一筆：「以後跑 `python -m myProgram` 或 `python -m myProgram.main`」

### 階段 P7（選擇性）：nlu/product_parser 拆分

涵蓋建議修 S18。

**動作：** 抽 `sales/product_parser.py` 出來。

**Pi 端：** 無

### 階段 P8（選擇性，逼近時做）：constants.py 拆 subpackage

涵蓋建議修 S17。**現階段不必**，constants.py 仍 239 行可接受；待逼近 400 行或新增 L 層時才動。

### 不做的部分（明確標 L1-L15 可不改項目）

見 §3.3 表格。包含：孤兒 pyc / `__init__.py` 現況 / 各種註解誤導 / dead wrapper / inner unclear 不累積 / wall-clock 註解 / speak+print 雙保險 / wire-up smoke test / O(N×M) 效能 / 拼音 fallback 部分保留 / print prefix 10 種 / PEP8 嚴格化。

---

## 6. 風險與緩解總表

| 階段 | 主要風險 | 緩解 |
|---|---|---|
| P0 | 改 keyword 後實機可能漏 / 多命中 | 每改一條補 1-2 個 regression test；使用者實機跑 5 分鐘對話驗證 |
| P1 | hook 路徑漏改 → 廠商檔禁改保護失效 | 改完用 dummy edit 廠商檔測試 hook 是否仍 block |
| P2 | dialog inner 去重時細微邏輯被合錯 | line-by-line diff + 172 tests 守住 |
| P3 | checkout 雙漏斗移除後使用者期待落差 | 規格說明先寫；實機跑前先 walk-through |
| P4 | keyword 改動連鎖影響其他 mode | tests/sales/test_nlu.py 涵蓋率高，跑 pytest 守 |
| P5 | customer q sentinel 影響 logic 層接收路徑 | sentinel 改動較大，獨立分階段做 |
| P6 | 跑法改變影響使用者習慣 | pineedtodo 記錄 + sync 後通知使用者 |
| P7 | parse_products 是最複雜函式，搬時手抖 | 純搬不改邏輯只動 import |

---

## 7. 附錄

### 7.1 已派出 agent 詳細元資料

| Agent | 模型 | tokens | duration | tool uses | agentId |
|---|---|---|---|---|---|
| 結構審查 (A) | opus | 103364 | 208s | 17 | a31e19b446214e34c |
| 狀態機審查 (B) | opus | 100773 | 247s | 15 | aa0e218fa660d92ac |
| NLU 審查 (C) | opus | 94798 | 258s | 7 | a08cf1ffbdaeaea19 |
| 橫切 (D) | 主 agent | — | 直接 | — | — |

如需 follow-up 同 agent 釐清，可用 SendMessage 帶 agentId 繼續對話。

### 7.2 規範對齊核對

本次審查全程遵守：
- ⛔ 範圍嚴格限制於 `myProgram/`，未審 tests/ / resources/ / .claude/ / 根目錄腳本
- ⛔ 未修改 / 未提議修改 vendor 檔內容（僅建議搬位置）
- ⛔ 未對任何檔案做 Edit / Write / commit
- ⛔ 未跑 `git add -A`
- 🌏 全程繁體中文輸出
- ✍️ 4 agent 都受 SubagentStart hook 自動注入規範約束 + prompt 內補強 task-specific 規則

---

**報告完。** 7 階段 P0-P5 為必修 / 建議修，P6-P8 為選擇性。最高 ROI 三步：**P0（keyword 急救）→ P1（dead code + vendor 搬位置）→ P2 (dialog 去重 + L4 第 7 次)**。
