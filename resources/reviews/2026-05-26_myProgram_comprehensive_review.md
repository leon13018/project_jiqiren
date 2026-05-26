# myProgram/ 程式碼全面審查統整報告

> **產出日期**：2026-05-26
> **審查標的**：`C:/Users/LIN HONG/Desktop/Project_01/myProgram/`（不含 `vendor/` — 廠商 SDK 禁改）
> **審查當下分支 / commit**：`main` @ `f970a81 feat(l2,l3,nlu): 「想買無商品」intent — 顧客肯定詞無具體商品名溫和引導`
> **規範前提**：絕對遵守 CLAUDE.md ⛔ 規則 1 — **不修改 `myProgram/vendor/ActionGroupControl.py` 與 `myProgram/vendor/Board.py`**(廠商 Hiwonder TonyPi SDK)
> **使用者原始任務**：派 1 個 `/review` 內建工具 + 並行派 3 個 opus 4.7 xhigh subagent 從三個不同方向審查整個 `myProgram/`,主 agent 統整。
> **數量說明**：使用者要求中提到「統整這 6 個 agent 調研結果」,主 agent 視為筆誤 — 實際派發 = 1 `/review` 來源 + 3 個 subagent 來源 = **4 個獨立審查來源**。若使用者本意是 6 個,請指示,可再補 2 個方向。

---

## 0. 目錄

- [1. 來源摘要](#1-來源摘要)
- [2. 高優先 findings(跨來源合併去重)](#2-高優先-findings跨來源合併去重)
- [3. 來源 A — 架構與模組設計(subagent,opus,17 條 finding)](#3-來源-a--架構與模組設計subagentopus17-條-finding)
- [4. 來源 B — 正確性、健壯性、多線程安全(subagent,opus,22 條 finding)](#4-來源-b--正確性健壯性多線程安全subagentopus22-條-finding)
- [5. 來源 C — 業務邏輯與對話流程(subagent,opus,23 條 finding)](#5-來源-c--業務邏輯與對話流程subagentopus23-條-finding)
- [6. 來源 D — /review skill 視角(test coverage / conventions / performance / security)](#6-來源-d--review-skill-視角test-coverage--conventions--performance--security)
- [7. 統合優先處理順序(跨來源整合)](#7-統合優先處理順序跨來源整合)
- [8. 統合風險評估](#8-統合風險評估)
- [9. 觀察到的好實踐(值得保留 / 推廣)](#9-觀察到的好實踐值得保留--推廣)
- [10. 對話腳本 / NLU 盲點清單(補 BDD scenarios 用)](#10-對話腳本--nlu-盲點清單補-bdd-scenarios-用)
- [11. 文案品質速覽](#11-文案品質速覽)

---

## 1. 來源摘要

| 編號 | 角色 / 工具 | 模型 / effort | finding 數 | 聚焦面向 |
|---|---|---|---|---|
| A | subagent (general-purpose) | opus / xhigh effort | 17 | 分層 / 模組職責 / vendor 邊界 / dead code / 命名 / 過度工程 / 業務↔IO 分離 |
| B | subagent (general-purpose) | opus / xhigh effort | 22 | race / sticky flag 守衛 / timeout / confirm default / 邊界 / encoding / NLU 健壯性 |
| C | subagent (general-purpose) | opus / xhigh effort | 23 | L0-L5 狀態流轉 / NLU intent / cart 業務 / 文案繁中 / 對話 UX / 商品 catalog |
| D | `/review` skill(主 agent 套用) | Claude Opus 4.7 | ~15(含好實踐 + 規範) | test coverage / project conventions / performance / security / 規範遵守度 |

**全部 findings 總數約 77 條**(去重前;統合後實際獨立議題約 60-65 條)。

---

## 2. 高優先 findings(跨來源合併去重)

按嚴重度 + 影響範圍 + 跨來源共識度排序。**Critical / High 的 finding 列在此處**;其餘按來源歸位於後續章節。

### HP-1:NLU substring 誤命中 — 多條來源(B1 / C1)共識

**位置**:`myProgram/sales/nlu.py:35-38`

**現狀**:`_KEYWORDS_REJECT` 含「沒有」/「沒了」substring,「沒有問題」「沒有錯」「等不了」「受不了」等口語會被誤判為拒絕。L4 與 L2 mode 均有風險。

**影響**:L4 顧客本意「等我掃碼」被當「取消交易」清 cart;L2 顧客本意「想買」被當「不買」謝客;L4 顧客抱怨「等不了」被當取消。

**綜合建議**:
- 把「沒有 / 没有」從 substring 集移到 `_KEYWORDS_REJECT_STRICT_SHORT`(只在 `text.strip() == "沒有"` 才算 reject)
- 把「不了」從 substring 集移除或改 strict-short(明確完整表達如「不買了 / 我不要了」已在白名單)
- L4 mode ACK keyword 補入「沒有問題 / 没有问题」
- 補對應 unit tests 至 `tests/sales/test_nlu.py`

### HP-2:NLU `_KEYWORDS_CONTINUE` negation guard 不完整 — B2

**位置**:`myProgram/sales/nlu.py:156-165`

**現狀**:l4_service mode 的 negation guard 只覆蓋「不繼續 / 不要繼續 / 別繼續 / 停止」;「我不想繼續」「沒打算繼續」會 fallthrough 到 `_KEYWORDS_CONTINUE` substring match 命中「繼續」→ 返「繼續交易」。

**影響**:違反 `confirm-default-must-be-conservative` 規範 — 顧客取消意圖被當繼續。L3 `_dialog_unclear_final_confirmation` 也用 `l4_service` mode,所以 L3 unclear final 取消同樣被吞。

**綜合建議**:
- 用 regex / pattern「不|別|沒|休 + 繼續」做更寬鬆的 negation 偵測
- 或改判定順序:先測 `_KEYWORDS_EXIT`,再測 `_KEYWORDS_CONTINUE`

### HP-3:L3 normal mode qty followup 把講「不要」的顧客困住 — B3

**位置**:`myProgram/sales/states/_l2_l3_qty_followup.py:99-121`

**現狀**:L3 顧客已有 cart 講「再來一杯紅茶」缺數量 → 進 qty 追問 sub-loop,`classify_intent_mode="normal"`。L3 normal mode 下「不要 / 不用」被當「結帳」而非「拒絕」。qty sub-loop fallthrough → 再 speak clarify → 無限循環。終止條件只剩「timeout(默默加 1 個顧客本想拒絕的商品)」或「顧客講明確的數量」。

**影響**:顧客錢包風險(多加 1 個刮刮樂 = 180 元)+ UX 災難(被困住)。

**綜合建議**:
- qty sub-loop 內顯式檢查 `follow_intent == "結帳"` → 也視為「不追加此商品」return False
- 或強制 qty sub-loop 走 `classify_intent_mode="l2"`(短 reject 詞被當拒絕)
- 同時加 attempts cap(如 3 次後自動 skip 商品 + 不默默加 1)— 與 B4 同步處理

### HP-4:L4 ACK 漏「等等」單詞 — C2

**位置**:`myProgram/sales/constants/keywords.py:67-76`

**現狀**:L4 `KEYWORDS_L4_ACK_OR_WAIT` 含「等等我」「等我」「稍等」「等一下」但**漏「等等」獨立詞**。顧客在 L4 找手機掃碼最常脫口的「等等」會走 `_KEYWORDS_THINK` 返「想一下」→ 在 L4 dispatch 沒對應 → unclear → 催促 → 連 3 次「等等」自動進客服模式。

**綜合建議**:
- 把「等等」加入 `KEYWORDS_L4_ACK_OR_WAIT`
- 或在 L4 mode 內把「想一下」intent 也視為 ACK gentle

### HP-5:L3 結帳前 confirm 文案沒列總金額 — C10

**位置**:`myProgram/sales/constants/l3_text.py:33` + `states/l2_l3_dialog.py:680-686`

**現狀**:`L3_CHECKOUT_CONFIRM_TEMPLATE = "您即將結帳,總共 {summary},正確嗎?..."` 只列商品數量摘要,沒列「合計多少元」。顧客在 confirm 看不到金額,到 L4 才驚覺貴 → 進 L4-B 取消。confirm 失去主要功能。

**綜合建議**:
- 改 `_build_order_summary` 把 `calc_total(cart)` 也算進來
- 文案改為「您即將結帳,總共 6 瓶冰紅茶、1 張刮刮樂,**合計 342 元**(已享九折優惠),正確嗎?」

### HP-6:`l2_l3_dialog.py` 神模組 / `unmute_opencv` dead callback / `QTY_PROMPT_TEMPLATE` dead import — A2 / A5 / A6 / C3

**位置**:
- `myProgram/sales/states/l2_l3_dialog.py:1-687`(687 行 / 10+ 內部函式)
- `myProgram/main.py:135-141, 172` + `myProgram/sales/logic.py:37`(dead callback)
- `myProgram/sales/states/_l2_l3_qty_followup.py:23, 68` + `myProgram/sales/constants/products.py:19`(dead import + magic string)

**綜合建議**:
- A5 / A6 / C3:純清理 dead code(無風險)
- A2:把 dialog 拆 5 個檔(main_loop / think_silence / c2_second_stage / checkout_confirm / unclear_final),每檔 < 150 行
- A6 / C3:`QTY_PROMPT_TEMPLATE` 升級為 `"請問{product}要幾{unit}?"` 並用回常數(取代 line 68 的 inline f-string)

### HP-7:hawk 排程沒有 cancel 介面 — B9(S4+ critical)

**位置**:`myProgram/sales/states/l1.py:194-200` + `myProgram/main.py:157-159`

**現狀**:`_schedule_hawk_l1` recursive callback 註冊 timer 後沒有 cancel handle;callback 介面 `schedule(seconds, fn)` 也缺對應 `cancel`。S1 階段 schedule 是 no-op 不出問題;S4+ 接 `threading.Timer` 後,顧客 OpenCV 偵測進 L2 時 hawk 已註冊的 timer 仍會 fire,**打斷正在進行的對話**;連續客戶累積 timer chain 同一刻多個叫賣 slogan 重疊播放。

**綜合建議**:S4 前必須先補:callback 介面新增 `cancel_all_hawk()` 或 `schedule(seconds, fn) → handle` + `cancel(handle)`;`_run_l1_hawk` 在 return(轉 L2 / 退出)前 cancel;`_invoke_subroutine_a` 前後也 cancel。

### HP-8:`read_terminal_key` 在 hawk 主迴圈是 blocking,與註解「non-blocking」矛盾 — B10(S4+ critical)

**位置**:`myProgram/sales/states/l1.py:181-191` + `myProgram/main.py:55-79`

**現狀**:S1 chat-driven OK;實機接 OpenCV 後,dwell 由背景 thread 推 state,主執行緒卡在 `input()` → dwell 永遠不被 check → 顧客在相機前停留 ≥1.5s 但系統永遠不轉 L2。

**綜合建議**:S4+ 時 `read_terminal_key` 改 worker thread + `queue.Queue(maxsize=1)` + `queue.get(timeout=0.1)`;同步修正註解口徑。或改 select-based stdin polling(Linux 可行)。

### HP-9:vendor SDK 封裝層尚未建立 — A15(S3+ critical)

**位置**:尚不存在的 `myProgram/sales/hardware.py`

**現狀**:目前 sales/ + main 完全沒 import vendor — 隔離乾淨。但 S3+ 接入時若散落呼叫 `Act.runAction` / `Act.stopAction` / `Board.setBuzzer`,sticky flag 守衛模式(`if Act.runningAction: stopAction()`)會散落漏寫。

**綜合建議**:S3 前先建 `myProgram/sales/hardware.py`:
```python
from myProgram.vendor import ActionGroupControl as _Act
from myProgram.vendor import Board as _Board

def run_action_safe(name: str, lock_servos: str = ""):
    _Act.runAction(name, lock_servos)

def stop_action_safe():
    if _Act.runningAction:
        _Act.stopAction()

def buzzer(state: int):
    _Board.setBuzzer(state)
```
sales/ 與 main 只 import 此層 — 守衛邏輯只寫一次。同時為未來 HTML UI / FastAPI 對接鋪路(hardware 層可獨立 mock)。

### HP-10:Test coverage 缺口 — `tests/sales/test_logic.py` 不存在 — D1 / D6

**位置**:`tests/sales/` 目錄

**現狀**:`tests/sales/` 內有 `test_cart.py / test_constants.py / test_product_parser.py / test_nlu.py / test_states.py` 5 個 unit test 檔,但 `myProgram/sales/logic.py` 對應的 `test_logic.py` **不存在**。`logic.py` 是 4 層狀態機主控(cycle dispatch + cart invariant assert + `enter_hawk_immediately` 旗號消費 + L5 退出後子例程 A 觸發),是業務最核心的編排層卻完全沒被 unit test。BDD 規範 `.claude/rules/bdd-tdd-workflow.md` 自己就在「tests/ 目錄結構」段列出 `test_logic.py` 是預期結構,但實際未建立。

**綜合建議**:補 `tests/sales/test_logic.py`,至少覆蓋:
1. cart invariant 違反時 raise AssertionError(_assert_cart_empty / _assert_cart_nonempty)
2. L1 result=None → run 返回
3. dialog 返 `L1_via_subroutine_a` → cart 應已空 + 觸發子例程 A
4. L4 非掃碼退出 → cart 應已空 + 觸發子例程 A + 設 `enter_hawk_immediately = True`
5. L5 退出後 cart 應已空 + 觸發子例程 A
6. `enter_hawk_immediately` 在 `subroutine_a` 後設 True,消費後 reset

所有 callback 全 stub,純 logic 編排測試。

---

## 3. 來源 A — 架構與模組設計(subagent,opus,17 條 finding)

### 來源 A:總體摘要

整體架構處於「incremental rebuild S1 階段完成度高 + 過渡期妥協痕跡明顯」的狀態。**vendor 隔離(選項 C)執行徹底,零洩漏**,這是最大優點;分層方向正確(main.py → logic → states → cart/nlu/product_parser → constants),cart 為唯一可變 cycle state 且有 fail-fast invariant 守衛,是好設計。但**模組邊界封裝**(跨模組大量 import 底線私名)、**檔案肥大**(`l2_l3_dialog.py` 687 行包 8 個內部函式)、**常數歸位錯位**(`SERVICE_PHONE`/`DIALOG_VAGUE_BUY_REASK` 放錯子模組)、**dead callback / dead import**(`unmute_opencv`、`QTY_PROMPT_TEMPLATE`、`schedule` 在 S1 階段純佔位)形成可見的技術負債。S1 階段保留 `schedule` recursive callback 設計、L4 ENTRY「QR 刷新」散落 6 處等則是不必要的提前抽象。

### 來源 A:整體架構觀察

**層次圖(依依賴方向,由外到內):**

```
__main__.py
   ↓
main.py (S1 wire-up;持有 _S1State / 11 個 callback)
   ↓ logic.run(**callbacks)
sales/logic.py (4 層 state machine + cart invariant)
   ↓ states.run_l1 / run_dialog / run_l4 / run_l5 / run_subroutine_a
sales/states/*.py (具體層邏輯)
   ↓ classify_intent / parse_products / cart_module.add_item
sales/nlu.py + sales/product_parser.py + sales/cart.py
   ↓ from ... import 常數
sales/constants/*.py (8 子模組純常數)

vendor/  ← 完全未被 sales/ + main 引用(S1 隔離)
```

**依賴方向乾淨**:由上至下單向依賴,無反向(無 `states/ import logic/`)。**但有兩個側向跨模組存取私名**:
- `product_parser.py` 從 `nlu.py` import `_CHINESE_DIGIT_MAP` / `_KEYWORDS_ICED_TEA` / `_KEYWORDS_SCRATCH`
- `states/l2_l3_dialog.py` 從 `nlu.py` import `_contains_any` / `_equals_strict_short`

是底線契約的破壞。

**重心**:`sales/states/l2_l3_dialog.py`(687 行)+ `sales/states/l4.py`(439 行)兩檔吃掉約 1100 行業務邏輯;`nlu.py`(278 行)次之;`cart.py` / `l5.py` 各 < 60 行。

**多線程現況**:完全純單線程,S1 階段如預期。`schedule` / `sleep` 在 main.py 是 no-op stub;states 內 `_schedule_hawk_l1` 仍以 recursive callback 形式預先設計遞迴排程(S4+ 才生效)。

### 來源 A:Finding 列表

#### A1:跨模組 import 底線私名 — 違反 Python 私有契約
- **嚴重度**:High
- **類別**:封裝邊界 / 模組職責
- **位置**:
  - `myProgram/sales/product_parser.py:22`
  - `myProgram/sales/states/l2_l3_dialog.py:59`
- **證據**:
  ```python
  # product_parser.py:22
  from myProgram.sales.nlu import _CHINESE_DIGIT_MAP, _KEYWORDS_ICED_TEA, _KEYWORDS_SCRATCH
  # l2_l3_dialog.py:59
  from myProgram.sales.nlu import classify_intent, _contains_any, _equals_strict_short
  ```
- **問題說明**:Python 慣例「底線開頭 = module-private」是契約,目前兩處跨模組 import 底線符號 = 宣告「這些是 module-private 但實際是 package-internal API」。`nlu.py` 重構這些符號 → product_parser silently 壞掉,IDE 不會警告。違反 karpathy「surface assumptions」原則。
- **建議**:把這些符號提升為公開(移底線),或搬到 `constants/keywords.py`(資料層歸資料層)。結構建議:constants 主管「資料」,nlu 主管「判斷函式」,product_parser 兩者都 import — 避免 nlu/product_parser 互相借私名。

#### A2:`l2_l3_dialog.py` 變成 dialog 神模組 — 687 行 / 10 個內部函式
- **嚴重度**:High
- **類別**:SRP / cohesion / 檔案肥大
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:1-687`
- **證據**:單檔 10 個函式,職責跨主迴圈 / L2 沉默分派 / L3 沉默分派 / C-2 第二段 / checkout confirm / unclear final / summary 組裝。
- **問題說明**:「B 方案 L2/L3 合一 cart-state-driven」設計動機合理,但實作把 5 個子狀態的 14 個 helper 全塞同檔;讀者要理解一條鏈路得在檔內上下跳 5-6 次。
- **建議**:拆 5 個獨立子狀態各自抽出檔:
  ```
  states/dialog/
    __init__.py            # 暴露 run_dialog
    main_loop.py           # run_dialog + _dialog_main_loop + _dialog_exit_a
    think_silence.py       # L2/L3 想一下沉默期 helper
    c2_second_stage.py     # L3 C-2 嚴格 yes/no
    checkout_confirm.py    # C-1 confirm + _handle_checkout_confirm_result + _build_order_summary
    unclear_final.py       # L3 B-1 unclear final
  ```
  每檔 < 150 行,閱讀範圍明確。BDD spec 也好對應。

#### A3:`states/` 命名前綴混亂 — 編號制 / dialog / 底線私有規則不一致
- **嚴重度**:Medium
- **類別**:命名一致性
- **位置**:`myProgram/sales/states/` 目錄
- **證據**:
  ```
  l0_subroutine_a.py       ← 編號 + snake_case
  l1.py                    ← 純編號
  l2_l3_dialog.py          ← 編號合併 + 副詞描述
  _l2_l3_qty_followup.py   ← 底線開頭 + 編號合併 + 副詞
  l4.py                    ← 純編號
  l5.py                    ← 純編號
  ```
- **建議**:選一條 convention 走到底。推薦:
  ```
  states/
    subroutine_a.py        (run_subroutine_a)
    mode_select.py         (run_mode_select)
    dialog.py              (run_dialog)
    checkout.py            (run_checkout)
    thanks.py              (run_thanks)
    _qty_followup.py       (resolve_and_add_products)
  ```
  或保留 L 編號則統一 prefix:`l0_*` / `l1_*` / `l4_*`,並讓函式名也一致 `run_l0` / `run_l1` / `run_l4`。

#### A4:跨層狀態轉移 contract 不一致 — 4 種 return shape
- **嚴重度**:Medium
- **類別**:分層 / 接口契約
- **位置**:
  - `myProgram/sales/states/__init__.py:22-26`
  - `myProgram/sales/states/l5.py:38-41`
- **證據**:
  ```python
  run_subroutine_a → None
  run_l1           → str | None
  run_dialog       → tuple[str, int]
  run_l4 / run_l5  → tuple[str, int, int]
  ```
  `logic.py:114-119` 為了沿用 shape 硬塞兩個無語意 0:
  ```python
  next_state, _, _ = states.run_l5(...)  # _ _ 永遠 0
  ```
- **問題說明**:違反 karpathy 「為一致性引入無意義欄位」。未來加 L6 / 拆 L4 sub-state,logic 的 unpack 順序就得跟著改。
- **建議**:用統一的 dict 或 dataclass 表達跨層轉移:`{"next_state": "L4", "counters": {"think_count": 0}}`。L5 不再需要假塞兩個 0。

#### A5:Dead callback `unmute_opencv` — wire-up 提供但 logic 收下後不傳
- **嚴重度**:Medium
- **類別**:dead code / 過時抽象
- **位置**:
  - `myProgram/main.py:135-141, 172`
  - `myProgram/sales/logic.py:37`
- **證據**:`unmute_opencv` 在 logic.py / states/*.py 完全沒被呼叫(grep 確認);`l0_subroutine_a` docstring 自承「不再 unmute」。
- **建議**:直接刪 — 三個位置同步移除(main.py 定義 + register、logic.py 簽名)。

#### A6:`QTY_PROMPT_TEMPLATE` import 但未使用 — Dead import + 雙重 prompt
- **嚴重度**:Medium
- **類別**:dead code
- **位置**:
  - `myProgram/sales/states/_l2_l3_qty_followup.py:23, 68`
  - `myProgram/sales/constants/products.py:19`
- **證據**:常數 import 但實作改用 inline f-string,常數本身全 grep 只在 import 與定義段出現。
- **建議**:刪 `QTY_PROMPT_TEMPLATE` 或升級為 `"請問{product}要幾{unit}?"` 並啟用回常數。

#### A7:`SERVICE_PHONE` / `DIALOG_VAGUE_BUY_REASK` 常數歸位錯位
- **嚴重度**:Medium
- **類別**:常數歸位 / 命名一致性
- **位置**:
  - `myProgram/sales/constants/l1_text.py:29`
  - `myProgram/sales/constants/l3_text.py:53-56`
- **證據**:`SERVICE_PHONE` 在 l1_text 但被 5 個檔(含 l4/l2/dialog/qty_followup)共用;`DIALOG_VAGUE_BUY_REASK` 命名 `DIALOG_*` 但放 `l3_text`。
- **建議**:新增子模組 `constants/shared.py`(或 `common_text.py`),把跨層共用文案搬過去,並把 `__init__.py:18-25` wildcard import 補上。

#### A8:`_dialog_main_loop` 與 `_dialog_continue_after_c2_inner` 是無功能的薄包裝
- **嚴重度**:Low
- **類別**:過度工程 / 過度抽象
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:546-566`
- **證據**:function body 只是把參數 forward 給 `_dialog_main_loop`。
- **建議**:直接刪 `_dialog_continue_after_c2_inner`,把唯一 caller 改成直接 call `_dialog_main_loop(...)`。

#### A9:L1 `_schedule_hawk_l1` recursive 排程是 S1 階段未生效的提前架構
- **嚴重度**:Low
- **類別**:過度工程(提前抽象)
- **位置**:
  - `myProgram/sales/states/l1.py:194-200`
  - `myProgram/main.py:157-159`
- **證據**:S1 schedule 是 no-op,recursive 自我重排機制完全無作用,hawk_index 永遠只跑 1 次。
- **建議**:S1 階段改 stub 註釋 + `TODO(S4+)`,等真進 S4 階段時根據實際 worker thread 接口設計(可能跟現在 recursive 不一樣)。

#### A10:`opencv_disable` 防呆呼叫散落 — 4 層 + 子鏈路內 6 處重複
- **嚴重度**:Low
- **類別**:分層職責 / 重複
- **位置**:
  - `myProgram/sales/states/l1.py:74, 122, 140`
  - `myProgram/sales/states/l2_l3_dialog.py:91`
  - `myProgram/sales/states/l4.py:79`
- **建議**:把 opencv enable/disable 策略集中到 logic.py,states 各層 signature 去掉 `opencv_disable` 參數(除 L1 因 hawk 還是需要 enable)。

#### A11:`opencv_disable=lambda: None` default 把測試耦合塞進 prod 簽名
- **嚴重度**:Low
- **類別**:測試耦合 / 介面汙染
- **位置**:
  - `myProgram/sales/states/l2_l3_dialog.py:71`
  - `myProgram/sales/states/l4.py:49`
- **建議**:移除 default → keyword-only required arg;測試自己給 `opencv_disable=lambda: None`。或採用 A10 建議完全移除參數。

#### A12:`_S1State.opencv_dwell` / `opencv_mute_until` 在 wire-up 層管理,但語意屬「OpenCV 模擬器狀態」
- **嚴重度**:Low
- **類別**:分層 / SRP
- **位置**:`myProgram/main.py:29-39`
- **建議**:改名為 `_OpenCVSimulator` 並把相關 callback(`opencv_enable` / `opencv_disable` / `opencv_dwell_seconds` / `mute_opencv` / `unmute_opencv` / `read_terminal_key` 內的 'c' 觸發)封進 class 方法。

#### A13:L4 ENTRY「QR 刷新」邏輯散落 6 處 — 應抽 helper / 改 sentinel pattern
- **嚴重度**:Low
- **類別**:重複 / SRP
- **位置**:`myProgram/sales/states/l4.py:83, 114, 135, 145, 170, 179`
- **建議**:把「主迴圈每次回到等待 read_customer_input 前」抽成一個 phase,或集中在末端 `_l4_refresh_or_skip` helper。

#### A14:`__init__.py` 暴露程度不一致 — sales / vendor 無 `__all__`,constants / states 有
- **嚴重度**:Low
- **類別**:import 表面 / 規範
- **位置**:
  - `myProgram/sales/__init__.py:1-6`
  - `myProgram/sales/constants/__init__.py:18-25`
  - `myProgram/sales/states/__init__.py:40-46`
- **建議**:每個 `constants/<sub>.py` 加 `__all__`,或取消 wildcard 改 explicit re-export。

#### A15:vendor 邊界封裝層尚未建立 — S3+ 接入時將直接散落 ⚠️
- **嚴重度**:Low(S1 階段;S3+ 升 High — 見 HP-9)
- **類別**:封裝 / 未來可擴展性
- **位置**:尚不存在的 `myProgram/sales/hardware.py`(建議)
- **建議**:見 HP-9。

#### A16:業務邏輯與 IO 分離有 leak — `print_terminal` 在 states 內直接被呼叫
- **嚴重度**:Low
- **類別**:業務 / IO 邊界 / 未來可擴展性
- **位置**:
  - `myProgram/sales/states/l1.py:117-123`
  - `myProgram/sales/states/l2_l3_dialog.py:194, 271, 482`
  - `myProgram/sales/states/l4.py:182-217`
- **建議**:未來 HTML UI 接入時,把 callback 分離成兩種:`notify_customer(event: dict)` + `print_terminal(text)`。S1 階段先做最小改動:把 `_l4_print_entry_detail` 拆「組裝 model」+「format to text」兩函式。

#### A17:`Cart = dict` type alias 是 lossy aliasing — IDE 看不到型別
- **嚴重度**:Low
- **類別**:型別 / 可讀性
- **位置**:`myProgram/sales/cart.py:14-17`
- **建議**:用 `TypeAlias`:
  ```python
  from typing import TypeAlias
  Cart: TypeAlias = dict[str, int]
  ```
  或直接 `dict[str, int]` 寫在簽名。

### 來源 A:優先處理順序

| 順序 | Finding | 理由 |
|---|---|---|
| 1 | A5 - Dead `unmute_opencv` | 純刪除,無風險 |
| 2 | A6 - Dead `QTY_PROMPT_TEMPLATE` | 純 import 清理 |
| 3 | A7 - 常數歸位 | 新增 `constants/shared.py` 純搬遷 |
| 4 | A1 - 底線私名跨模組 | 影響擴大前先封死 |
| 5 | A11 - `opencv_disable=lambda: None` default | 揭露真實呼叫 contract |
| 6 | A8 - dead forwarder | 直接 inline 進唯一 caller |
| 7 | A14 - constants `__all__` | 規範新增常數行為 |
| 8 | A17 - `Cart = dict` TypeAlias | 一行改動,IDE/mypy 立即受益 |
| 9 | A15 - vendor 封裝層 | **S3+ 接入前必做** |
| 10 | A12 - `_S1State` → `_OpenCVSimulator` | 重構 main.py 結構 |
| 11 | A10 - opencv_disable 散落 6 處 | 配合 A11 + A12 |
| 12 | A13 - L4 QR 刷新 6 處 | l4 主迴圈 dispatch 結構調整 |
| 13 | A3 - states/ 命名前綴 | 大型重新命名 |
| 14 | A4 - return shape 統一 | 跨層 contract 變動 |
| 15 | A2 - `l2_l3_dialog.py` 拆檔 | 最高收益但工作量最大 |
| 16 | A9 - `_schedule_hawk_l1` recursive | 等 S4 階段時一併重設計 |
| 17 | A16 - 業務 / IO 分離 | HTML UI 階段啟動時動 |

---

## 4. 來源 B — 正確性、健壯性、多線程安全(subagent,opus,22 條 finding)

### 來源 B:總體摘要

`myProgram/sales/` 在 S1 純單線程 chat-driven 階段,主流程(狀態機、cart 不變式、wall-clock 預算、confirm 子狀態 default、vendor SDK 隔離)整體寫得謹慎,**沒有 race condition、沒有寬泛 except、沒有 vendor sticky flag 違規**。最大風險集中在 **NLU substring 比對的誤命中**(多處 substring 短詞會吞掉長句語意,例如「沒有問題」被「沒有」吃成 reject、「我不想繼續」被「繼續」吃成 continue),以及 **`_qty_follow_up_sub_loop` 對 L3 normal mode「不要」會把顧客困死**。其次是 **calc_total 無上限保護**、**中文數字「十二」解析為 2**、**hawk 排程不可取消** 等問題。S1 階段大部分風險為 latent(要 S4+ 接 threading / 真實 TTS / 真實 OpenCV 才會引爆),但 NLU 誤命中即使在 S1 chat-driven 已可重現。

### 來源 B:風險全景圖

- **已封堵良好**:cart invariant fail-fast assert / L4 wall-clock 60s 預算 / `_dialog_checkout_confirm` confirm default = cancel(保護錢包)/ vendor sticky flag 沒有被 sales/ 任何地方呼叫(嚴格隔離選項 C)/ Unicode normalize(全形數字 + 控制字元)/ `_S1State.opencv_mute_until` 設計細緻。
- **中度風險**:NLU substring 誤命中(B1/2/3/4)、qty followup 在 L3 mode 困住、`parse_products` 視窗誤吃下個商品的描述詞、中文複合數字「十二/二十」失效、`add_item` 無 qty 上限/型別檢查。
- **S4+ latent bug**:hawk 排程不可取消、`read_terminal_key` 在 hawk 是 blocking 與註解「non-blocking」矛盾、`_S1State` 無 threading lock、sales/ 內無 except 包覆、`_l4_service_mode` 60s timeout 突破 L4 主迴圈 60s wall-clock budget。

### 來源 B:Finding 列表

#### B1:NLU substring 誤命中 — 「沒有問題」被當「拒絕」/「結帳」 ⚠️(見 HP-1)
- **嚴重度**:High
- **位置**:`myProgram/sales/nlu.py:35-38`、`myProgram/sales/nlu.py:188-193`
- **詳細**:見 HP-1。

#### B2:NLU negation guard 不完整 — 「我不想繼續」被當「繼續交易」 ⚠️(見 HP-2)
- **嚴重度**:High
- **位置**:`myProgram/sales/nlu.py:156-165`
- **詳細**:見 HP-2。L3 `_dialog_unclear_final_confirmation`(line 669)也用 `l4_service` mode,所以 L3 unclear final 同樣受影響。

#### B3:`_qty_follow_up_sub_loop` 在 L3 normal mode 把講「不要」的顧客困住 ⚠️(見 HP-3)
- **嚴重度**:High
- **位置**:`myProgram/sales/states/_l2_l3_qty_followup.py:99-121` + `myProgram/sales/nlu.py:185-189`
- **詳細**:見 HP-3。

#### B4:`qty_follow_up_sub_loop` 無 attempts cap / wall-clock budget — DoS 風險
- **嚴重度**:Medium
- **類別**:邊界 / 無限循環
- **位置**:`myProgram/sales/states/_l2_l3_qty_followup.py:99-121`
- **證據**:fallthrough 到 line 121 speak clarify,無 attempts cap、無 continue / break / counter。
- **影響**:佔用主執行緒無法返回;L4 wall-clock budget 在此 helper 內無法生效。
- **建議**:加 `attempts` 計數,達上限(如 3 次)→ speak「商品略過」+ return False。

#### B5:中文複合數字「十二/二十一/二十五」全部被解析為個位
- **嚴重度**:Medium
- **類別**:邊界 / 數量解析
- **位置**:`myProgram/sales/nlu.py:222-247` + `myProgram/sales/product_parser.py:54-71`
- **證據**:「十二」→ dict loop 命中「二」→ 返 2。同理「二十/二十一/三十五」都被解析為個位。
- **建議**:先嘗試解析複合中文數字(regex),再 fallback 到單字 map。或限制單一中文數字字 keyword 必須是 `text.strip()` 完全等於才算(搭配阿拉伯數字優先)。

#### B6:`cart.add_item` 無 qty / product 邊界檢查
- **嚴重度**:Medium
- **類別**:邊界 / fail-fast 缺失
- **位置**:`myProgram/sales/cart.py:25-33, 49-62`
- **證據**:
  ```python
  def add_item(cart: Cart, product: str, qty: int) -> None:
      cart[product] = cart.get(product, 0) + qty   # 無檢查
  def calc_total(cart: Cart) -> int:
      ...
      unit_price = PRODUCTS[product]["實際"]   # KeyError 風險
  ```
- **建議**:`add_item` 加 `assert product in PRODUCTS, f"Unknown product: {product}"` 與 `assert 0 < qty <= MAX_QTY_PER_ITEM`(如 50)。

#### B7:`parse_products` 視窗解析誤吃前面的不要 / 否定詞數字
- **嚴重度**:Medium
- **位置**:`myProgram/sales/product_parser.py:136-142`
- **證據**:「冰紅茶不要 3 瓶 我改要 5 瓶」→ 視窗 = 「不要 3 瓶 ...」→ 阿拉伯先抓「3」→ cart 加 3 瓶。本意 5 瓶。
- **建議**:在視窗內若偵測到「不要 / 改 / 改成 / 算了」更正詞,跳過該數字、找下一個。或標 qty=None 進追問。

#### B8:`_l4_service_mode` 60s timeout 與 L4 主迴圈 60s wall-clock budget 衝突
- **嚴重度**:Medium
- **類別**:timeout / budget 設計
- **位置**:`myProgram/sales/states/l4.py:300-360, 88-95`
- **證據**:
  ```python
  deadline = time.monotonic() + L4_TOTAL_BUDGET  # 60s
  response = read_customer_input(timeout=L4_SERVICE_TIMEOUT)  # 60s
  ```
- **觸發情境**:顧客進 L4 → 5s 後講「客服」→ 進 service mode → 等 59s 後選「繼續」→ 回主迴圈 `remaining = -4` → 立即 forced exit + 清 cart。
- **影響**:顧客在 service mode 內主動選「繼續」反而立刻被強制退出。
- **建議**:service mode 進入時延長 deadline(`extend by L4_SERVICE_TIMEOUT`),或進 service mode 時跳出主迴圈 budget 限制。**建議與使用者對齊規格意圖**。

#### B9:hawk 排程沒有 cancel 機制 — 多次進出 hawk 會累積 timer chain ⚠️(見 HP-7)
- **嚴重度**:High(S4+)/ Low(S1 — schedule 是 no-op)
- **詳細**:見 HP-7。

#### B10:`read_terminal_key` 在 hawk 主迴圈是 blocking,與註解「non-blocking」矛盾 ⚠️(見 HP-8)
- **嚴重度**:High(S4+ 必壞)/ Medium(S1 OK)
- **詳細**:見 HP-8。

#### B11:think_count 跨 L2/L3 cart-state mode 累積,可能瞬間觸發 C-2 自動結帳
- **嚴重度**:Medium
- **類別**:狀態機 / 計數器語意
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:414-452`
- **觸發情境**:L2 顧客「等等」think_count=1 → 加品 cart 變非空進 L3 → 再「等等再說」think_count=2 → 再「再想想」think_count=3 → 直接 C-2 自動結帳。**think_count 從 L2 詢問需求累積過來**。
- **建議**:L2→L3 mode 切換時 reset `think_count = 0`。位置在 `_dialog_main_loop` line 498-508 或 `_dialog_dispatch_inner_l2` line 210-215。

#### B12:confirm 子狀態 timeout 傳 `remaining` 可能為極小 float — production STT 來不及回應
- **嚴重度**:Low(S1)/ Medium(S4+)
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:322` + `l4.py:99, 139`
- **觸發情境**:`remaining = 0.5s` 傳給 STT callback → STT 只給 0.5s 收音 → 收不到 → 視為 timeout → 自動推進。
- **建議**:給 read_customer_input 一個 minimum timeout(如 1.0s),或在 `remaining < threshold` 時直接走 timeout 分支不再 read。

#### B13:`L4_TOTAL_BUDGET` 可被 sub-helper 消耗超出 — `_l4_final_confirmation` 重 prompt 重給 6s × 3 次
- **嚴重度**:Low(INTENTIONAL 設計)/ 仍需驗證
- **位置**:`myProgram/sales/states/l4.py:271-297`
- **觸發情境**:60s 預算可能實際被花到 60 + 18 = 78s。docstring 寫「60s 防 ack spam」但 final_confirmation 把它繞掉。
- **建議**:final_confirmation 內也用 `deadline = caller_deadline - now` 計算 remaining。或文件化「60s 預算 + 最壞 18s buffer」。

#### B14:`_dialog_c2_second_stage` timeout default 推進 L4 — INTENTIONAL 但鏈條要驗
- **嚴重度**:Low(INTENTIONAL)
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:316-325`
- **觸發情境**:L3 dialog timeout → C-2 12s → L4 60s → 最壞 72s 仍 forced exit + clear cart。
- **建議**:保留現行設計,在文件加註鏈條總時長與保守結果。

#### B15:sales/ 內無 try/except 保護 — production callback raise 會殺掉狀態機
- **嚴重度**:Medium(S4+)
- **位置**:`myProgram/sales/states/l4.py:84-179`、`l2_l3_dialog.py:382-543`、`l1.py:70-114`
- **建議**:sales/ 內不包 except(fail-fast 原則對業務 bug 有益),但 main.py 的 `try: logic.run(**callbacks)` 應加更寬的 except 區塊處理 callback 故障(log + 嘗試 clear cart + 嘗試 vendor stopAction with 守衛 + 重啟主迴圈或安全退出)。或 callback 自身在 main.py 包成 robust wrapper。

#### B16:`parse_quantity` 對「0/-1/0 元」失效但 fallback 為 1 — 隱性默默加 1
- **嚴重度**:Low
- **位置**:`myProgram/sales/nlu.py:250-277`
- **建議**:若 has_quantity 返 True 但所有阿拉伯數字都是 0 → 應視為「明確 0 → 視為拒絕」而非 fallback 1。

#### B17:`_S1State` shared state 在 S4+ 加 OpenCV detector thread 後無 lock 保護
- **嚴重度**:Low(S1)/ Medium(S4+)
- **位置**:`myProgram/main.py:29-39, 101-141`
- **建議**:S6 上線 OpenCV detector 時為 `_S1State` 加 `threading.Lock`。或用 `queue.Queue(maxsize=1)` 推 dwell event 給主執行緒(單 queue 偏好原則)。

#### B18:註解寫「Non-UTF-8 byte → return None」但 Python `input()` 不會 raise UnicodeDecodeError on Windows console
- **嚴重度**:Low
- **位置**:`myProgram/main.py:63-67, 89-93`
- **建議**:保留現行 except,加註「Linux Pi 端可能 fire」。

#### B19:hawk loop 是 busy poll — production 不 sleep 會 100% CPU
- **嚴重度**:Low(S1 chat-driven 因 input blocking 不會 spin)/ Medium(S4+ 非阻塞 read 後會 spin)
- **位置**:`myProgram/sales/states/l1.py:182-191, 144-154`
- **建議**:S4+ 加 `time.sleep(0.05)` 或 `queue.get(timeout=0.1)` 自然 block 0.1s 釋 CPU。

#### B20:`add_item` 對同商品累加無上限
- **嚴重度**:Low
- **位置**:`myProgram/sales/cart.py:25-33`
- **建議**:加 `MAX_QTY_PER_PRODUCT = 50` cap。

#### B21:`print_terminal` 內 `if text == L1_HAWK_ENTRY_PROMPT` 緊耦合常數值
- **嚴重度**:Low
- **位置**:`myProgram/main.py:48-53`
- **建議**:改用 substring 比對或語意 flag(caller 顯式呼叫一個獨立 callback `show_hawk_help()`)。

#### B22:`_dialog_main_loop` 沒有 wall-clock budget — 顧客可無限「想一下」/ 商品加減
- **嚴重度**:Low(INTENTIONAL — 主動加單沒理由限時)
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:382-543`
- **建議**:低優先,可加 `DIALOG_TOTAL_BUDGET`(如 300s 或 600s)作為上限保護。或保留現行設計。

### 來源 B:Critical / High 優先列表

1. **B1(High)**:NLU 「沒有問題」被當 reject — L4 顧客錢包 / 體驗風險
2. **B2(High)**:NLU negation guard 不完整 — 「不想繼續」被當「繼續交易」
3. **B3(High)**:`_qty_follow_up_sub_loop` L3 mode 「不要」困住顧客 + 默默加 1
4. **B9(High for S4+)**:hawk 排程無 cancel
5. **B10(High for S4+)**:read_terminal_key blocking 但註解寫 non-blocking
6. **B5(Medium)**:中文「十二」被解析為 2
7. **B4(Medium)**:qty followup 無 attempts cap — DoS
8. **B8(Medium)**:客服模式 60s 突破 L4 主迴圈 60s budget

---

## 5. 來源 C — 業務邏輯與對話流程(subagent,opus,23 條 finding)

### 來源 C:總體摘要

整體業務邏輯設計成熟,cart 狀態驅動的 L2/L3 合一是漂亮的架構決策;L4 wall-clock 預算 + ACK gentle 路徑兼顧禮貌與超時保護;L3 結帳前 confirm 區分 timeout / 明確拒絕 / 亂答耗盡三種 NO 路徑也展現對 UX 細節的用心。197 個測試是強力 regression 安全網。

但深入掃過後仍有十餘個對顧客體驗有實際影響的 bug 與盲點:(1) NLU 關鍵字白名單對「沒有問題」「等等」「不了」這類常見口語短語有誤判風險;(2) 商品 catalog 只含 2 項但商家 demo 場景叫賣詞已暗示更廣品項,缺貨/未列商品的顧客追問沒任何兜底;(3) `QTY_PROMPT_TEMPLATE` 常數被導入但實作改用 inline f-string,magic string 違反集中化;(4) L3 清空 cart 的通知文案語法有兩處不通順「需要請重新購買」應改寫;(5) L1 / L4 不同子狀態都使用相同的 "1" / "2" 終端輸入但語意不同 — 顧客 / 商家容易混淆。

### 來源 C:狀態機全貌觀察

L0(子例程 A 12s mute 緩衝)→ L1(叫賣 / 待機 / 客服 三鏈路;2026-05-26 加 `enter_hawk_immediately` 直接連續叫賣)→ dialog(L2/L3 合一,cart 狀態驅動)→ L4(結帳,60s wall-clock 預算 + 4 階段催促 + 客服特殊模式 + 最終確認子狀態)→ L5(致謝,純序列無分支)→ 子例程 A 回 L1。

**亮點**:cart 狀態驅動的 dialog 層讓「未來加刪除商品」的擴展不需要新增 transition;L4 多層子狀態(service / final_confirmation)職責清晰;NLU mode(normal / l2 / l4 / l4_service)讓同一輸入字串在不同上下文有對應語意;L4 ACK 路徑(2026-05-26 加)顯著改善了顧客講「好」/「等一下」時 unclear spam 的舊問題。

**盲點**:(1) 商品 catalog 僅 2 項,缺乏「現場有哪些商品」的引導;(2) L1 主選單到 dialog 的轉場沒有「請問是商家還是顧客」的角色辨識,依賴 OpenCV 偵測即進入對話;(3) L4 catalog 沒列數量上限。

### 來源 C:Finding 列表

#### C1:NLU REJECT 子集含「沒有」會誤判常見肯定詞「沒問題 / 沒有問題」為拒絕 ⚠️(見 HP-1)
- **嚴重度**:High
- **位置**:`myProgram/sales/nlu.py:35-38`
- **詳細**:見 HP-1。

#### C2:L4 ACK 列表漏「等等」單詞 ⚠️(見 HP-4)
- **嚴重度**:High
- **位置**:`myProgram/sales/nlu.py:58` + `myProgram/sales/constants/keywords.py:67-76`
- **詳細**:見 HP-4。

#### C3:`QTY_PROMPT_TEMPLATE` 常數被 import 卻沒被使用,實作改用 inline f-string ⚠️(同 A6)
- **嚴重度**:Medium
- **位置**:`myProgram/sales/states/_l2_l3_qty_followup.py:23, 68`
- **詳細**:見 A6。

#### C4:L3 清空 cart 通知文案「需要請重新購買」語法不通順
- **嚴重度**:Medium
- **位置**:`myProgram/sales/constants/l3_text.py:37, 41`
- **證據**:
  ```python
  L3_CHECKOUT_REJECT_CLEAR_NOTICE: str = "已幫您清空購物車,需要請重新購買,您好,請問需要購買什麼東西嗎?"
  L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE: str = "由於您沒回應,已幫您清空購物車,需要請重新購買,您好,請問需要購買什麼東西嗎?"
  ```
- **問題**:「需要請重新購買」語法奇怪;緊接「您好」突兀。
- **建議**:改為「已幫您清空購物車。如需重新選購,請告訴我您想買什麼?」;timeout 版本前綴「由於您沒回應,」。

#### C5:NLU `_KEYWORDS_REJECT` 含「不了」會誤判「受不了 / 好不了 / 等不了」等慣用語 ⚠️(見 HP-1)
- **嚴重度**:Medium
- **位置**:`myProgram/sales/nlu.py:36`
- **詳細**:見 HP-1。

#### C6:`KEYWORDS_WANT_TO_BUY_SHORT = ["有", "要"]` 在 L2 mode 全形 / OCR 雜訊下可能誤命中
- **嚴重度**:Medium
- **位置**:`myProgram/sales/constants/keywords.py:99`
- **建議**:保留現狀(strict-short 已是好設計),補 unit test「STT 雜訊」案例(如「有。」、「要!」),確認 `_equals_strict_short` 對含標點輸入行為符合預期;若不行則考慮在 `normalize_input` 內補移除尾端標點。

#### C7:「等一下」既在 `_KEYWORDS_THINK` 又在 `KEYWORDS_L4_ACK_OR_WAIT`,L4 同字不同意維護負擔
- **嚴重度**:Low
- **位置**:`nlu.py:58` + `keywords.py:72`
- **建議**:在 `keywords.py` 加註釋說明 cross-mode 行為,或抽出 `KEYWORDS_WAIT_TIME` 共用名稱。

#### C8:L4 主迴圈 ACK 路徑不重置 `loop_count`,顧客真誠等等後仍可能瞬間被催促
- **嚴重度**:Medium
- **位置**:`myProgram/sales/states/l4.py:128-130, 162-164`
- **建議**:ack 後重置 `loop_count = 0`(但保留 wall-clock 預算)。

#### C9:商品 catalog 只有 2 項,但叫賣詞已暗示「全場」「冷飲彩券」更廣範圍 — 顧客追問其他商品無兜底
- **嚴重度**:Medium
- **位置**:`myProgram/sales/constants/products.py:12-15` vs `keywords.py:13-20`
- **建議**:(1) 新增 NLU intent「詢問商品列表」,命中時 speak「我們今天有冰紅茶(27 元/瓶)和刮刮樂(180 元/張),請問您要哪一種?」;(2) 或調整叫賣詞別說「全場」,改為「特賣『冰紅茶』與『刮刮樂』,全場九折!」。

#### C10:L3 結帳前 confirm 文案沒列**總金額** ⚠️(見 HP-5)
- **嚴重度**:High
- **位置**:`myProgram/sales/constants/l3_text.py:33` + `states/l2_l3_dialog.py:680-686`
- **詳細**:見 HP-5。

#### C11:`add_item` / `calc_total` 對缺貨 / 限量 / 數量上限完全無業務防護
- **嚴重度**:Medium
- **位置**:`myProgram/sales/cart.py:25-33`
- **詳細**:見 B6。

#### C12:「沒問題 / 沒事」這類 L4 ACK 詞,但在 L2/L3 不被識別為任何 intent
- **嚴重度**:Low
- **位置**:`myProgram/sales/constants/keywords.py:67-76`
- **建議**:把「沒問題 / 沒事」也加入 `_KEYWORDS_CHECKOUT`(含簡體變體)— L3 mode 視為結帳意圖。

#### C13:「考慮」/「想想」這類雙字詞在 L3 mode 被分為「想一下」累計 think_count,可能誤觸 C-2 自動結帳
- **嚴重度**:Medium
- **位置**:`myProgram/sales/nlu.py:58` + `states/l2_l3_dialog.py:414-452`
- **建議**:把 C-2 第二段 prompt 改更明確「您似乎還在猶豫,請問要結帳(說『是』)還是繼續想想(說『不要』)?...」;或思考次數從 3 → 4。

#### C14:L1 主選單按 `q` 立即 exit_program 沒有任何確認 — 商家手滑風險
- **嚴重度**:Low
- **位置**:`myProgram/sales/states/l1.py:82-84, 146-148, 188-190`
- **建議**:按 q → 印「確定要退出?再按一次 q 確認 / 任何其他鍵取消」→ 第二次 q 才退出。或 q 改為「Ctrl+C」。

#### C15:L4 service mode 60s timeout 沒任何中途提示,顧客 / 客服久通話會被默默砍掉
- **嚴重度**:Medium
- **位置**:`myProgram/sales/states/l4.py:300-360`
- **建議**:(1) timeout 拉長到 180s;(2) 30s 時 speak「您還在嗎?需要更多時間請說『繼續』」做中途點名;(3) 或每 30s 重 speak `L4_C_OPTIONS_PROMPT` 提醒選項。

#### C16:`_dialog_c2_second_stage` 視窗內「商品 / 想一下 / 客服」一律 silently 忽略,沒回應顧客
- **嚴重度**:Medium
- **位置**:`myProgram/sales/states/l2_l3_dialog.py:316-361`
- **建議**:12s 倒數第一次亂答時 speak 一次提醒「請說『是』或『否』」(不重置 deadline);第二次起 silently 忽略。讓顧客知道系統「有聽到,但不懂」而非「卡住」。

#### C17:HAWK_SLOGANS 與商品實際定價不同步(價格寫死在叫賣詞內)
- **嚴重度**:Low
- **位置**:`myProgram/sales/constants/keywords.py:13-20`
- **建議**:改成 f-string 模板 `"冰紅茶清涼一夏,只要 {price} 元!".format(price=PRODUCTS["冰紅茶"]["實際"])`;或維持原樣但加 unit test 斷言叫賣詞含當前實際價字串。

#### C18:「了」單字 strict-short 沒處理,「好了」/「對了」這類純語助詞會走 unclear
- **嚴重度**:Low
- **位置**:`myProgram/sales/nlu.py:135-215`
- **建議**:把「好了」加入 `KEYWORDS_CONFIRM_YES` substring 集;或在 normalize 階段把「了 / 啦 / 啊」純尾助詞剝除(注意保留「沒了」「不買了」這類含意義「了」的詞)。

#### C19:商品別名 / 暱稱完全缺失(如「冰茶 / 冷飲 / 茶飲」根本不在 catalog)
- **嚴重度**:Low(catalog 只 2 項,但展開後是 High)
- **位置**:`myProgram/sales/product_parser.py:31-51`
- **建議**:加入「冰茶」「冷飲」「茶」(注意不要 substring 衝突);加上「我口渴 / 我想喝點什麼 / 給我喝的」fuzzy intent 引導到品項列表。

#### C20:L5 致謝層後 sleep `THANK_DELAY = 3s` + 子例程 A mute 6s,顧客連續購買銜接不順
- **嚴重度**:Low
- **位置**:`myProgram/sales/states/l5.py:42-54` + `l0_subroutine_a.py:32`
- **建議**:(1) L5 致謝後 speak「還需要其他東西嗎?」+ 5s 容忍期;(2) 或直接在 L5 後問「需要再買其他嗎?」當 retention upsell。

#### C21:L4 entry print 用「s + Enter 模擬掃碼成功」對顧客語意混亂
- **嚴重度**:Low
- **位置**:`myProgram/sales/states/l4.py:215`
- **建議**:把「終端輸入 s + Enter 模擬掃碼成功」抽出為 `L4_QR_MOCK_HINT` 常數,未來 S2+ 改成 `""` 或拿掉就只動一處。

#### C22:parse_products dedup 規則 3 累加策略,重複品 dedup 規則 3 與業務直覺可能衝突
- **嚴重度**:Low
- **位置**:`myProgram/sales/product_parser.py:101-105`
- **建議**:dedup rule 3 應該改為「保留最後一個 entry」(覆寫前一次);或加 unit test 明確期望「2 + 3 = 5」是設計選擇而非 bug。

#### C23:L2/L3 「想買無商品」溫和引導 `DIALOG_VAGUE_BUY_REASK` 只列「冰紅茶或刮刮樂」沒列價
- **嚴重度**:Low
- **位置**:`myProgram/sales/constants/l3_text.py:56`
- **建議**:「好的,請告訴我您想買的商品 — 冰紅茶(27 元/瓶)或刮刮樂(180 元/張)」。

### 來源 C:優先處理建議

#### Priority 1(強烈建議優先修,直接影響交易成功率)
- **C1** 沒有問題誤判 REJECT
- **C10** L3 confirm 沒列總金額
- **C2** L4 ACK 漏「等等」單詞
- **C5** 「不了」substring 誤判
- **C4** 「需要請重新購買」語法不通

#### Priority 2(建議在下個 demo 前修,改善體驗質感)
- **C8** L4 ACK 後 loop_count 不重置
- **C9** catalog 廣度 / 商品詢問 intent
- **C11** cart 無業務防護
- **C13** 「想想 / 考慮」累計 think_count 觸發 C-2 風險
- **C16** C-2 倒數內顧客講話完全沒反應
- **C15** L4 service 60s timeout 太短且無中途提示

#### Priority 3(架構整理 / 維護性,可累積修)
- **C3** `QTY_PROMPT_TEMPLATE` 死常數
- **C7** 「等一下」跨 mode 不同意
- **C17** HAWK_SLOGANS 內 hardcode 27 元
- **C12** L4 ACK 詞在 L2/L3 失效
- **C18** 「好了 / 對了」等口語助詞缺處理
- **C19** 商品別名擴展
- **C20** L5 → L1 mute 6s 阻擋連續購買
- **C21** L4 entry「s + Enter 模擬」抽常數
- **C22** parse_products dedup 規則 3 累加策略
- **C23** vague_buy reask 加上價格
- **C14** L1 q 退出無 confirm

---

## 6. 來源 D — /review skill 視角(test coverage / conventions / performance / security)

### 來源 D:總體摘要

主 agent 套用 `/review` skill 的 5 個標準審查角度(correctness / conventions / performance / test coverage / security),補 A/B/C subagent 較少觸及的面向。最大發現:**`tests/sales/test_logic.py` 完全不存在**,業務最核心的編排層 `logic.py`(cart invariant + cycle dispatch)缺單元測試覆蓋,且 BDD 規範自己列出此檔但未建立 — 此項已升為 HP-10。其餘 finding 多為微優化(performance)、規範遵守度檢核(多為正面)、邊界 security 確認(多已封堵)。

### 來源 D:Finding 列表

#### D1:Test coverage 缺口 — `tests/sales/test_logic.py` 不存在 ⚠️(見 HP-10)
- **嚴重度**:High
- **類別**:test coverage / 規範遵守
- **位置**:`tests/sales/` 目錄
- **證據**:`tests/sales/` 內有 `test_cart.py / test_constants.py / test_product_parser.py / test_nlu.py / test_states.py` 5 個 unit test 檔,但 `myProgram/sales/logic.py` 對應的 `test_logic.py` **不存在**。`logic.py` 是 4 層狀態機主控(cycle dispatch + cart invariant assert + `enter_hawk_immediately` 旗號消費 + L5 退出後子例程 A 觸發),是業務最核心的編排層卻完全沒被 unit test。
- **詳細**:見 HP-10。

#### D2:Performance — `_contains_any` 每次呼叫對 keyword 做 .lower()
- **嚴重度**:Low
- **位置**:`myProgram/sales/nlu.py:94-97`
- **證據**:
  ```python
  def _contains_any(text: str, keywords: list) -> bool:
      text_lower = text.lower()
      return any(kw.lower() in text_lower for kw in keywords)
  ```
- **問題**:keyword 是 module-level 常數不會變,每次呼叫重 `.lower()` 是 redundant。L4 mode 一輪 classify_intent 可能 5+ 次呼叫 × 10+ keywords = 50+ 次 redundant lower()。在 Pi 4 上 micro 級但累積。
- **建議**:把所有 keyword 集合預先 `.lower()` 過再存(module-level constants);或維持現狀承認累積成本可忽略(更傾向後者,符合 karpathy「surgical」精神)。

#### D3:Security — `sys.exit(0)` 在顧客輸入路徑可被觸發
- **嚴重度**:Medium(S2+ production)/ Low(S1)
- **位置**:`myProgram/main.py:95-97`
- **證據**:
  ```python
  def read_customer_input(timeout):
      ...
      if raw == "q":
          print("[系統] 程式結束(顧客層 q 退出)")
          sys.exit(0)
  ```
- **問題**:S1 chat-driven 模式下顧客輸入路徑接受「q」直接退出整個程式。production 顧客是語音 STT 不太可能傳「q」,但若 STT 把語音「Q」/「kiu」誤識別 → 程式退出。或商家測試時手滑誤打 q。註解承認「production 不會有人講『q』」但沒在 production wire-up 階段提醒移除。
- **建議**:在 main.py 加 TODO「S2+ 真 STT 接入時移除顧客層 q 處理」;或改為「需要連按 3 個 q」確認模式。

#### D4:Performance — `parse_products` 三層巢狀循環在 long input 時 O(k×n×occupied)
- **嚴重度**:Low
- **位置**:`myProgram/sales/product_parser.py:115-128`
- **證據**:18 個 keyword × `text.find()` loop × occupied overlap check(線性掃所有 occupied)。
- **問題**:200 字 input × 18 keyword × find() × overlap check 約幾千 op,Pi 4 上仍 << 1ms。
- **建議**:保留現狀(已 normalize 限 200 字);可加 unit test 覆蓋 worst case「200 字 + 重複 keyword × 10」確認 < 50ms。

#### D5:Convention — `Cart = dict` 違反 karpathy「surface assumptions」(同 A17)
- **嚴重度**:Low
- **位置**:`myProgram/sales/cart.py:17`
- **詳細**:見 A17。

#### D6:規範遵守 — BDD 規範自己列出的 `tests/sales/test_logic.py` 不存在(同 D1)
- **嚴重度**:High
- **位置**:`.claude/rules/bdd-tdd-workflow.md` 「tests/ 目錄結構」段 + `tests/sales/`
- **證據**:bdd-tdd-workflow.md 明示:
  ```
  tests/sales/
  ├── test_cart.py
  ├── test_nlu.py
  ├── test_logic.py    ← 規範列出,但實際不存在
  └── test_states.py
  ```
- **建議**:見 HP-10 / D1。

#### D7:規範遵守 — 廠商 SDK 隔離(CLAUDE.md 紅線 #1)執行得非常乾淨 ✅
- **嚴重度**:N/A(好實踐)
- **位置**:sales/ + main.py 全樹
- **證據**:grep 確認完全沒 `import myProgram.vendor.*`、沒 `ActionGroupControl|Board|runAction|stopAction` 任何使用點。
- **意義**:是本專案最值得保護的紀律 — 一旦 break 會直接導致 Windows 端整個套件無法 import(vendor 含 Pi-only path / pigpio / RPi.GPIO)。
- **建議**:S3+ 接入時走 hardware.py 封裝層(A15 / HP-9),保持隔離成本最小。

#### D8:規範遵守 — 繁中規範(CLAUDE.md「輸出語言規範」)全部 speak/print 文案 ✅ 簡體 keyword 註明合理
- **嚴重度**:N/A(好實踐)
- **位置**:`constants/` 各 *_text.py
- **證據**:所有 speak / print 文案繁中;nlu.py 內簡體 keyword 都明確標「使用者 Windows IME 簡體」、「使用者實機踩過簡體輸入」。
- **意義**:產出物嚴守繁中,輸入處理寬鬆接受簡體 — 是務實的策略選擇(最終成果在台灣展示,使用者測試環境是簡體 IME)。

#### D9:Code correctness — `_CHINESE_DIGIT_MAP` dict iteration 順序語意未明示
- **嚴重度**:Low
- **位置**:`myProgram/sales/nlu.py:222-233, 272-274`
- **證據**:
  ```python
  _CHINESE_DIGIT_MAP: dict = {
      "一": 1, "壹": 1, "兩": 2, "二": 2, "貳": 2, ...
  }
  for char, value in _CHINESE_DIGIT_MAP.items():
      if char in text:
          return value
  ```
- **問題**:Python 3.7+ dict iteration 依插入順序,是確定的。但 docstring 沒說明「優先序 = 插入順序」這個事實。
- **建議**:docstring 加註「dict iteration 依插入順序,依此優先序」;或改用 list of tuples 明示順序。

#### D10:Code correctness — `parse_quantity` 對中文複合數字(「十二」「一百」「兩千」)失效但 fallback = 1(同 B5)
- **嚴重度**:Medium
- **位置**:`myProgram/sales/nlu.py:250-277`
- **詳細**:見 B5。
- **/review 補充**:fallback = 1 是 silent failure,顧客明確說「100 瓶」卻只加 100(OK)但說「一百瓶」卻加 1。falsey defaults 易掩蓋 bug。

#### D11:Security — input() 在 Linux Pi 端從 pipe / stdin redirection 接資料時可能被注入超長 line / binary
- **嚴重度**:Low
- **位置**:`myProgram/main.py:64, 90`
- **證據**:`normalize_input` 截 200 字 + 移控制字元 → OK。
- **建議**:保留現狀;未來 STT 接入時注意 STT API 也應有長度上限。

#### D12:規範遵守 — `karpathy-guidelines` 在 IO 邊界保留 defensive except 是合理但 unreachable
- **嚴重度**:Low(綜合判斷:保留即可)
- **位置**:`myProgram/main.py:65, 91`(UnicodeDecodeError except)
- **證據**:Windows console 不會 raise UnicodeDecodeError(已在 B18 提到),但保留 except 是 defensive。
- **建議**:保留(IO 邊界例外);加註「Linux Pi 端可能 fire」。

#### D13:型別 hint — `classify_intent` 回傳 str 而非 `Literal[...]` enum
- **嚴重度**:Low
- **位置**:`myProgram/sales/nlu.py:135-215`
- **證據**:回傳 9 種固定 intent 字串(「拒絕」/「想一下」/「結帳」/「客服」/「商品:冰紅茶」/「商品:刮刮樂」/「繼續交易」/「退出交易」/「無法判斷」/「等待安撫」/「想買無商品」共 11 種),但 type hint 是 `str`。
- **問題**:caller dispatch 時打錯字串(如 `"客 服"` 比對失敗)IDE / mypy 不會警告。
- **建議**:用 `typing.Literal`:
  ```python
  from typing import Literal
  Intent = Literal["拒絕", "想一下", "結帳", "客服", "商品:冰紅茶", ...]
  def classify_intent(text: str, mode: str = "normal") -> Intent: ...
  ```
  或定義 IntEnum / StrEnum。

#### D14:規範遵守 — `__init__.py` 規範不一致(同 A14)
- **嚴重度**:Low
- **詳細**:見 A14。

#### D15:Test coverage 觀察 — tests/spec/ 是 BDD 規範產出但不含實作 import — 是 good practice ✅
- **嚴重度**:N/A(好實踐)
- **位置**:`tests/spec/`
- **證據**:6 個 L0-L5 scenarios.py 檔僅含 BDD 注解骨架(`def test_...(): pass`),不 import 任何 prod 模組,作為「規格的可執行版」靜止存在。
- **意義**:BDD spec 永久當「規格書的可執行版」存活;後續修規格時 spec 跟著修。這是務實的選擇 — 避免 spec/ 與 sales/ tests 重複維護。
- **建議**:保留現行模式;若未來新增 sales/ 業務邏輯(BDD+TDD 重啟條件),記得同步更新 spec/ 對應檔。

---

## 7. 統合優先處理順序(跨來源整合)

依「**顧客錢包 / UX 即時風險**」→「**S4+ 必修隱患**」→「**架構整理 / 維護性**」三層分級。

### 第一層:立即修(顧客錢包 / UX 即時風險,S1 階段已可重現)

| 順序 | Finding | 來源 | 嚴重度 | 主要動作 |
|---|---|---|---|---|
| 1 | NLU「沒有」substring 誤判 | B1 / C1 / HP-1 | High | nlu.py:35-38 移「沒有 / 没有」到 strict-short |
| 2 | NLU `_KEYWORDS_REJECT` 含「不了」 | C5 / HP-1 | Medium-High | nlu.py:36 移除「不了」或改 strict-short |
| 3 | L4 ACK 漏「等等」單詞 | C2 / HP-4 | High | keywords.py:67-76 補入「等等」 |
| 4 | L3 結帳前 confirm 沒列總金額 | C10 / HP-5 | High | _build_order_summary 加 calc_total,L3_CHECKOUT_CONFIRM_TEMPLATE 文案改 |
| 5 | qty followup L3 mode 「不要」困死 | B3 / HP-3 | High | _l2_l3_qty_followup.py:111-121 顯式檢查 follow_intent == "結帳" return False + 加 attempts cap |
| 6 | NLU negation guard 不完整 | B2 / HP-2 | High | nlu.py:158 改 regex 涵蓋「不|別|沒|休 + 繼續」 |
| 7 | L3 清空 cart 文案語法不通 | C4 | Medium | l3_text.py:37, 41 改寫 |
| 8 | 中文「十二/二十」解析為 2 | B5 / D10 | Medium | nlu.py 加複合中文數字 regex |
| 9 | qty followup 無 attempts cap (DoS) | B4 | Medium | 加 attempts 計數,3 次後 skip 商品 |
| 10 | cart 無業務邊界檢查 | B6 / C11 / B20 | Medium | add_item 加 assert product in PRODUCTS + qty 上限 |

### 第二層:S3+ / S4+ 上線前必修(latent 但會炸)

| 順序 | Finding | 來源 | 嚴重度(S4+)| 主要動作 |
|---|---|---|---|---|
| 11 | vendor 封裝層 hardware.py | A15 / HP-9 | High | 建 sales/hardware.py,封裝 runAction / stopAction with sticky guard |
| 12 | hawk 排程 cancel 介面 | B9 / HP-7 | High | callback 介面加 cancel;states 進 L2 前 cancel hawk timers |
| 13 | read_terminal_key 非阻塞化 | B10 / HP-8 | High | S4+ 改 worker thread + queue.Queue + queue.get(timeout=0.1) |
| 14 | sales/ 外層 try/except 包覆 | B15 | Medium | main.py logic.run 外層加 wrapper + log + clear cart |
| 15 | hawk busy poll 加 sleep | B19 | Medium | S4+ 加 time.sleep(0.05) / queue.get(timeout=0.1) |
| 16 | `_S1State` 加 threading.Lock | B17 | Medium | S6 OpenCV detector 上線時補 |
| 17 | L4 service mode 60s 突破 budget | B8 | Medium | 與使用者對齊規格意圖:延長 deadline or 跳出 budget |
| 18 | `loop_count` 在 L4 ack 後重置 | C8 | Medium | l4.py:128 ack 後 loop_count = 0 |

### 第三層:補測試 + 架構整理(無風險小步推進)

| 順序 | Finding | 來源 | 嚴重度 | 主要動作 |
|---|---|---|---|---|
| 19 | 補 tests/sales/test_logic.py | D1 / D6 / HP-10 | High | 至少 6 個核心測試 |
| 20 | 補 NLU 邊界 unit tests | B 整體 / C 整體 | High | tests/sales/test_nlu_boundary.py 覆蓋「沒有問題」「不了」「十二」「0 瓶」等 |
| 21 | 刪 unmute_opencv dead callback | A5 | Medium | 三處同步刪除 |
| 22 | 刪 QTY_PROMPT_TEMPLATE dead import | A6 / C3 | Medium | 啟用回常數或刪 |
| 23 | 常數歸位 constants/shared.py | A7 | Medium | 把 SERVICE_PHONE / DIALOG_VAGUE_BUY_REASK 搬出 |
| 24 | 跨模組底線私名提升為公開 | A1 | High | nlu.py 提升 `_contains_any` etc.,或搬到 constants/keywords.py |
| 25 | `Cart` 改 TypeAlias | A17 / D5 | Low | 一行改動,IDE/mypy 立即受益 |
| 26 | classify_intent 回傳改 Literal | D13 | Low | 用 typing.Literal 限定回傳值 |
| 27 | opencv_disable=lambda default 移除 | A11 | Low | 改 keyword-only required |
| 28 | dead forwarder _dialog_continue_after_c2_inner 刪 | A8 | Low | inline 進唯一 caller |
| 29 | constants 子模組加 __all__ | A14 / D14 | Low | 每個子模組加 __all__ |
| 30 | L3 confirm 12s 倒數靜默改為提示一次 | C16 | Medium | 第一次亂答 speak「請說『是』或『否』」 |
| 31 | think_count 跨 L2/L3 切換時 reset | B11 | Medium | _dialog_main_loop / _dialog_dispatch_inner_l2 加 reset |

### 第四層:大型重構(等其他完成後再動)

| 順序 | Finding | 來源 | 嚴重度 | 主要動作 |
|---|---|---|---|---|
| 32 | l2_l3_dialog.py 拆 5 檔 | A2 | High | states/dialog/{main_loop,think_silence,c2_second_stage,checkout_confirm,unclear_final}.py |
| 33 | states 命名一致化 | A3 | Medium | 統一前綴或語意名 |
| 34 | 跨層 return shape 統一 | A4 | Medium | 改用 dict 或 dataclass,logic 統一 unpack |
| 35 | _S1State → _OpenCVSimulator class | A12 | Low | 重構 main.py |
| 36 | opencv_disable 散落 6 處集中 | A10 | Low | 配合 A11 + A12 |
| 37 | L4 QR 刷新 6 處抽 helper | A13 | Low | l4 主迴圈 dispatch 結構調整 |
| 38 | _schedule_hawk_l1 等 S4 重設計 | A9 | Low | S4 階段重設計,現在改 stub + TODO |
| 39 | 業務↔IO 分離(L4 entry detail)| A16 | Low | HTML UI 階段啟動時做 |

### 第五層:UX 補強 / 文案 / 商品 catalog 擴展

- **C9** 商品 catalog 廣度 / 詢問商品 intent
- **C13** 「想想 / 考慮」累計 think_count 觸發 C-2 風險
- **C15** L4 service 60s timeout 太短且無中途提示
- **C12** L4 ACK 詞在 L2/L3 失效
- **C18** 「好了 / 對了」等口語助詞缺處理
- **C19** 商品別名擴展
- **C20** L5 → L1 mute 6s 阻擋連續購買
- **C21** L4 entry「s + Enter 模擬」抽常數
- **C22** parse_products dedup 規則 3 累加策略確認
- **C23** vague_buy reask 加上價格
- **C14** L1 q 退出無 confirm
- **C7** 「等一下」跨 mode 不同意(加註釋)
- **C17** HAWK_SLOGANS hardcode 27 元(改 f-string)
- **B12** confirm timeout `remaining` 太小(加 minimum 1.0s)
- **B13** L4_TOTAL_BUDGET 被 final_confirmation 突破 18s(文件化或補保護)
- **B14** L2/L3 dialog timeout 鏈條 72s(文件化)
- **B16** parse_quantity「0 瓶」silently fallback 1(加明確 0 處理)
- **B18** UnicodeDecodeError 註解 vs 實際行為(加註)
- **B21** print_terminal hawk help magic string(改 callback flag)
- **B22** dialog 無 wall-clock budget(加上限)
- **D2** _contains_any 重複 .lower()(micro 優化)
- **D3** sys.exit('q') production 隱患(加 TODO)
- **D4** parse_products O(k×n) 加 worst-case test
- **D9** _CHINESE_DIGIT_MAP iteration 順序語意(docstring 補註)
- **D11** input() pipe injection(保留 normalize 即可)
- **D12** UnicodeDecodeError defensive except(保留)

---

## 8. 統合風險評估

### 修法可能引入的新風險表

| 修改範圍 | 引入風險 | 緩解策略 |
|---|---|---|
| **第一層 1-10(NLU 細修)** | 既有 197 tests 多數覆蓋 nlu / cart / product_parser;補 unit tests 後即可信 | 修一條 → 跑 `python -m pytest tests/sales/test_nlu.py -v` → 全綠 → 下一條 |
| **第二層 11(vendor 封裝層)** | S3+ 接入時 sticky flag 守衛漏寫的 bug 會回來 — 風險很高 | **強烈建議 S3 開工前完成**,且第一個用此封裝層的 commit 在 Pi 上實機驗證 runAction + stopAction 各跑一次 |
| **第二層 12-13(hawk cancel + 非阻塞 read)** | 改非阻塞 read 後 hawk 主迴圈會 busy poll → 同步加 sleep | 同 commit 一併做(B19 跟 B10 是配對) |
| **第二層 14(sales/ 外層 except)** | 包過寬的 except 可能掩蓋業務 bug — sales/ 內部仍 fail-fast,except 只在 main.py 邊界 | except 內必 log + 嘗試 clear cart + 嘗試 vendor stopAction(with 守衛) |
| **第三層 19-20(補 test_logic.py / nlu_boundary)** | 純測試,無 prod code 風險 | 純加法 |
| **第三層 21-29(dead code 清理 / TypeAlias / Literal)** | 純刪除或型別精化,已 grep 確認無其他使用點 | 修完跑全 pytest 確認綠 |
| **第四層 32(l2_l3_dialog.py 拆 5 檔)** | 大型重構,import 表面變動 — **有 regression 風險** | (a) 先跑現有 197 tests baseline;(b) 一次只拆一個檔;(c) 每次完成跑 pytest 確認綠燈 |
| **第四層 33-34(命名 / return shape)** | 跨層 contract 變動,影響 logic.py + 所有 states.run_xxx;要重跑全 197 tests | 一個 commit 完成單一改名(不混搭) |
| **第四層 35-37(main.py 重構)** | 影響 wire-up,可能漏接 callback | main.py 改動後手動跑 `python -m myProgram` 走一輪 L1→L2→L3→L4→L5 |
| **第五層(UX / 文案)** | 大多純文案 + 微邏輯 | 安全 |

### 跨來源觀察:未列入 finding 但值得關注的議題

1. **規格與實作差異未審查**:本次審查未深入比對 `resources/plans/業務程式邏輯規劃/L0-L5.md` 與 sales/ 實際實作的差異(C 來源僅快速掃過)。若使用者要進一步發現實作偏離規格的情況,建議專門派一輪「規格 ↔ 實作 diff 審查」。
2. **TDD coverage 真實深度**:197 個 tests 數量豐富,但分布如何?是否有「測試聚集在 nlu/product_parser 邊界 case,而 states 主流程測試淺」的問題?需要實際看 coverage 報告(如 `pytest --cov`)才能精準回答。
3. **`logic.py` 不僅缺 unit test,整合測試也只能靠使用者實機跑**:選項 C 架構決策(Windows 不接 vendor)讓整合測試斷層,這是已知妥協 — 但配合 incremental-rebuild S1-S7 應該可控。
4. **CLAUDE.md 規範執行度高分**:⛔ 禁止項(vendor 禁改、git add 限制)+ 繁中規範 + Linux 絕對路徑 + 廠商 SDK 隔離選項 C,**全部嚴格遵守**。CLAUDE.md 三層架構(pointer → rules → memory)也運作良好(規則文件存在且齊全)。

---

## 9. 觀察到的好實踐(值得保留 / 推廣)

從 B 與 D 來源彙整:

1. **`logic.py` cart invariant fail-fast assert**(line 132-145):每進新層強制檢查 cart 是否符合預期,bug 發生時立即定位,採用 surgical defensive programming。
2. **L4 wall-clock 60s 預算實作(line 88-95)**:deadline 用 `time.monotonic()`(不會被系統時鐘調整影響),每次主迴圈起始 check `remaining <= 0` 早退。設計嚴謹。
3. **`_dialog_checkout_confirm` 四態 sentinel(line 569-615)**:明確區分 yes / no_explicit / no_unclear_exhausted / timeout,且全部非-yes 路徑都 cancel + clear cart,**完全符合 confirm-default-must-be-conservative 規範**。
4. **`_S1State.opencv_mute_until` 時間戳設計(main.py line 110-122)**:用 `time.monotonic()` 比較取代「mute flag + background timer」,避免 timer race + sticky flag 污染,比舊版優雅。
5. **`_KEYWORDS_REJECT_STRICT_SHORT` / `KEYWORDS_CONFIRM_YES_STRICT_SHORT` 雙路設計**:substring 集 + strict-short 集分開,能避免「好」/「沒」單字 substring 誤命中 — 這個 pattern 值得在所有 keyword set 普及(修 HP-1)。
6. **vendor SDK 嚴格隔離(選項 C)**:sales/ 整個樹(含 logic.py)grep `ActionGroupControl|Board|runAction|stopAction` 完全沒命中。
7. **`normalize_input` 在 IO 邊界一次性消毒(main.py line 68, 94)**:含長度截斷、控制字元移除、全形數字轉換。sales/ 內部不必再次 normalize,分層乾淨。
8. **L4 `min(WAIT_NO_RESPONSE, remaining)` 等待上限**(l4.py:99, 139):confirm 等待不會超過 wall-clock budget — 避免 budget 漏算的細緻 detail。
9. **`_assert_cart_empty` / `_assert_cart_nonempty` ctx 訊息**(logic.py line 132-145):違反時 error message 帶 `ctx` 標識「哪段 transition 失敗」,debug 友善。
10. **`enter_hawk_immediately` 旗號採 consume-after-use 模式**(logic.py line 69):在 `run_l1` 後立即 `= False`,避免狀態漂移;每次需要才顯式設 True,明確流程意圖。
11. **繁中產出物 vs 簡體輸入容忍**:產出物嚴守繁中(CLAUDE.md 規範),輸入處理寬鬆接受簡體 keyword(適應使用者 Windows IME 簡體環境)— 務實策略。
12. **BDD spec 永久存活模式**:`tests/spec/` 內 6 個 L0-L5 scenarios.py 是「規格的可執行版」純注解骨架,跟 `tests/sales/` unit test 並存 — 是務實的雙軌做法,避免重複維護。

---

## 10. 對話腳本 / NLU 盲點清單(補 BDD scenarios 用)

以下顧客可能講的話,目前 NLU 漏接或誤判(來自 C 來源):

1. **「沒問題」/「沒事」** — 在 L2/L3 走 unclear;在 L4 OK(ACK 命中)。L2/L3 應視為 OK / 結帳。
2. **「等等」單字** — L4 漏列,會走 unclear;L2/L3 走「想一下」OK。
3. **「等不了 / 受不了 / 忘不了」** — 在 L4 全會誤判 REJECT(含「不了」substring)。
4. **「來罐紅茶」/「拿瓶飲料」/「有冷的嗎?」** — parse_products 無命中。
5. **「我口渴 / 我餓 / 給我喝的」** — fuzzy 需求無 intent 對應。
6. **「我要 7 號」/「3 號商品」** — 商品編號未支援(如果商家貼價格牌貼編號)。
7. **「優惠多少?」/「打幾折?」** — 沒有「詢問折扣」intent,會走 unclear。
8. **「現金可以嗎?」/「我沒有手機」** — 沒有「替代付款」intent,走 unclear。
9. **「我未成年能買刮刮樂嗎?」** — 沒有年齡 / 法律限制提示,刮刮樂台灣法規未成年禁買。
10. **「來看看」/「逛逛」** — L2 入口顧客回應,會走 unclear。台灣口語很常見。
11. **「對了,順便加一瓶」** — L3 想加單時的口語,「對了」substring 不在任何 keyword 集。
12. **「便宜一點啦」/「老闆算我便宜點」** — 議價語意完全無覆蓋。
13. **「全部 / 都要 / 兩種都要」** — 多商品 fuzzy 指代,parse_products 找不到具體商品。
14. **「給我看看」/「給我商品列表」** — 商家詢問商品列表 intent 缺失。
15. **「上次買過的那個」** — 個人化記憶(本期不支援,但 demo 阿伯可能會這樣講)。
16. **「謝謝 / 不好意思 / 對不起」** — 客套詞無對應,會走 unclear(在 L2/L3);L4 有 ACK gentle 路徑但「謝謝」不在 list。

**建議**:把上述 16 個盲點全寫成 BDD scenarios 進 `tests/spec/dialog_blindspots_scenarios.py`,逐步補完 NLU 與文案 — 這份文件本身也是未來迭代的 backlog。

---

## 11. 文案品質速覽

### 語法 / 通順問題
- **`l3_text.py:37,41` 「需要請重新購買,您好,請問需要購買什麼東西嗎?」** — 「需要請」連用語法奇怪,「您好」夾在中間像 bot 卡住。**已在 C4 詳述**。
- **`l3_text.py:51` 「請問是否要結帳?...如果沒回應,{seconds} 秒後將為您結帳」** — 「如果沒回應」較冷淡,台灣慣用「若未收到回應」或「您若沒回應的話」。**Minor**。
- **`l4_text.py:27` 「因為都沒有付款,系統即將取消這次交易」** — 「因為都沒有付款」「都」字位置奇怪,「因為一直沒有付款」更通順。
- **`l5_text.py:11` 「謝謝您的光臨,歡迎再度光臨」** — 「再度光臨」較書面,台灣口語更自然是「歡迎再來」或「歡迎下次再來」。

### 標點 / 格式
- **大量使用全形「,」/「。」/「?」/「()」** — 符合台灣繁中慣例 ✅。
- **「『 』」(單書名號)做引語** — 台灣繁中慣用 ✅;TTS 不會念書名號,差別只在終端 print 顯示。
- **`l1_text.py:11` `L1_MENU_BANNER` 結尾「> 」** — 終端 prompt 風格 ✅。

### 文案長度
- **`L3_CHECKOUT_CONFIRM_TEMPLATE`**(46 字)— confirm 必要訊息密度 OK,但**漏總金額**(HP-5 / C10)。
- **`L4_D_FINAL_PROMPT`**(59 字)— 最長文案。對 TTS 約需 8-10 秒念完,配 6s timeout 不夠 → 顧客還在聽 prompt 就 timeout 了。**潛在問題**:若 wire-up 正確「timeout 從 TTS 結束起算」就 OK。
- **`L4_ENTRY_PROMPT_TEMPLATE`**「(已享全品項九折優惠)」中括弧內容可拿掉,金額明細 print 已說明。

### 語氣一致
- **`L2_REJECT_THANKS` =「謝謝光臨」** vs **`L3_REJECT_THANKS` =「好的,取消這次購物,謝謝光臨」** — L2 過短,建議「好的,謝謝光臨」平衡語氣。
- **`L4_B_CANCEL_THANKS` =「好的,取消這次交易,謝謝光臨」** — 「取消這次交易」聽起來像系統訊息,改「好的,這次先不交易,謝謝光臨」更人性化。
- **`L5_THANKS` =「謝謝您的光臨,歡迎再度光臨」** — 偏正式。台灣便利商店風格通常更口語:「謝謝光臨,歡迎再來」。

### 簡繁體一致性
- ✅ 沒有發現簡體殘留在最終 speak / print 文案中。簡體都在 NLU keyword 集(為輸入支援),這是正確策略。

---

## 報告結束

**主 agent 總結**:

本次審查由 4 個獨立來源(3 個 opus subagent + 主 agent 套用 /review skill)並行進行,共產出約 77 條 finding,去重後實際獨立議題約 60-65 條。

**最重要的 3 條(顧客錢包 / UX 立即風險,當前 S1 chat-driven 已可重現)**:
1. **HP-1**:NLU 「沒有問題」「等不了」這類含「沒有 / 不了」substring 的口語被誤判拒絕 — 改 strict-short 集
2. **HP-3**:L3 normal mode qty followup「不要」困住顧客 + 默默加 1 個本想拒絕的商品 — 修 follow_intent 處理
3. **HP-5**:L3 結帳前 confirm 沒列總金額 — 顧客 confirm 階段看不到金額,違反 confirm 設計初衷

**最重要的 3 條(S3+ / S4+ 上線前必修,現在 latent)**:
4. **HP-9**:vendor SDK 封裝層 `hardware.py` 尚未建立 — S3+ 散落 sticky flag 守衛 bug 會回來
5. **HP-7**:hawk 排程無 cancel 介面 — S4+ 對話被叫賣打斷 / timer chain 累積
6. **HP-8**:`read_terminal_key` blocking 與註解「non-blocking」矛盾 — S4+ 實機接 OpenCV 必壞

**最重要的 1 條(測試覆蓋)**:
7. **HP-10**:`tests/sales/test_logic.py` 不存在 — `logic.py` 主控狀態機完全無 unit test(BDD 規範自己列出但未建立)

**整體評估**:sales/ 業務邏輯主體骨架健康;廠商 SDK 隔離 + 繁中規範 + cart invariant + L4 wall-clock 預算 + confirm conservative default 都是好實踐。可見的技術負債(dead code / 命名混亂 / 私名跨界 / 過早抽象)多屬累積到 S1 v2 + P0-P8 refactor 之後的妥協痕跡,**多為低風險高收益的清理工作**。NLU 是中央阻塞點,建議集中修一輪。

**6 個 vs 4 個 agent 數量問題提醒**:使用者原指令提到「6 個 agent」但實際描述列出的是 1 個 /review + 3 個 subagent = 4 個。本報告按 4 個來源整合。若使用者本意是 6 個,可再補 2 個方向(如「規格 ↔ 實作 diff 審查」+「效能 / Pi 4 實機資源分析」)。
