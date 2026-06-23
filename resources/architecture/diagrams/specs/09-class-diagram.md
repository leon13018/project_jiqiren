# 09 · 類別圖（spec + 畫圖計畫）

> 報告系統圖⑨。風格＝ report-design-system 淺色蠟筆風（**不在此重述**，見 `diagram-crayon.md` + 三基準）。本檔＝**主題 spec（要表達什麼 + 逐項核對過的碼事實）＋畫圖計畫（UML 版面/主角/關係/座標/色彩語意/signature）**。交付 `diagrams/09-class-diagram.{html,png,svg}`。

## 1. Thesis（這張要表達什麼）

`SalesMachine` 的 **State pattern** 類別骨架（machine.py W5 重構：把 `logic.py` 主迴圈的字串 tuple 魔法值 `("L4",0)`/`("L1_enter_hawk",…)` + if/elif 調度鏈，改寫成教科書 State pattern）。

**主角（protagonist）＝ `State`(ABC) 繼承三角 + `SalesMachine` 聚合 4 個 State + `Transition` 回傳契約**。`SalesMachine.run()` 迴圈 dispatch 4 個具體 `State`，每個 `run(machine)` 回傳一個 `Transition` 值物件（取代字串 tuple），machine 讀 `next_state`/`enter_hawk` 決定下一層。

> 與圖②區別：② 畫**行為**（L0–L5 狀態怎麼轉移、cart 驅動、enter_hawk 回流）；⑨ 畫**類別結構**（實作這個狀態機的 OOP 骨架：誰繼承誰、誰持有誰、方法簽名）。

## 2. 逐項核對過的碼事實（鐵則 1 — 已讀 `states/machine.py` `cart.py` `dialog_io.py` `nlu.py`，勿捏造欄位/簽名）

### 2a. `Transition`（`machine.py`，frozen dataclass）
```python
@dataclass(frozen=True)
class Transition:
    next_state: str            # "dialog" / "l4" / "l5" / "l1"
    enter_hawk: bool = False   # True = 下輪 L1 直接 hawk（交易完成後續連續叫賣）
```

### 2b. `State`(ABC)（`machine.py`）
- 類別屬性：`entry_invariant: str`（"empty"/"nonempty"）、`entry_ctx: str`（assert 訊息語境字串）。
- 抽象方法：`@abstractmethod def run(self, machine) -> "Transition | None"`（None ＝ 程式終止，run_l1 的 None）。

### 2c. 4 個具體 State（`machine.py`，皆 `class XState(State)`）
| 類別 | entry_invariant | entry_ctx | run 內呼叫（晚綁定 `states.run_*`） | 回傳 |
|---|---|---|---|---|
| `L1State` | "empty" | "進 L1" | `states.run_l1(...)`（傳 enter_hawk_immediately；呼後 reset False） | `None`（result is None）或 `Transition("dialog")` |
| `DialogState` | "empty" | "進 dialog" | `states.run_dialog(...)` → `(next_state,_think)` | `Transition("l1", enter_hawk=True)`（next=="L1_enter_hawk"，先 `_assert_cart_empty`）或 `Transition("l4")` |
| `L4State` | "nonempty" | "進 L4" | `states.run_l4(...)` → `(next_state,_,_)` | `Transition("l1", enter_hawk=True)`（next=="L1_enter_hawk"，先 `_assert_cart_empty`）或 `Transition("l5")` |
| `L5State` | "nonempty" | "進 L5（從 L4-A 帶 cart）" | `states.run_l5(...)`（回傳值忽略） | 先 `_assert_cart_empty`，恆 `Transition("l1", enter_hawk=True)` |

### 2d. `SalesMachine`（`machine.py`）
- `__init__(self, callbacks: dict, cart, start_hawk: bool = False)`。
- 欄位：`callbacks: dict`、`cart`、`enter_hawk_immediately: bool`（初值＝start_hawk）、`_states: dict[str, State]` ＝ `{"l1":L1State(), "dialog":DialogState(), "l4":L4State(), "l5":L5State()}`。
- 方法：
  - `_emit(self, current: str) -> None`：查 `_PHASE_BY_STATE`（`{"l1":"standby","dialog":"ordering","l4":"checkout","l5":"thankyou"}`），`paid = cart_module.calc_total` 僅 l5，`disp(phase, dict(cart), paid)`；`display` 為 None（終端模式）則跳過。
  - `run(self) -> None`：主迴圈 —— 取 `_states[current]`；依 `entry_invariant` 進場 `_assert_cart_empty`/`_assert_cart_nonempty`（A4-c fail-fast）；`_emit(current)`；`result = state.run(self)`；`None`→return；`result.enter_hawk`→`enter_hawk_immediately=True`；`current = result.next_state`。
- 模組級 helper（machine.py）：`_assert_cart_empty(cart, ctx)` / `_assert_cart_nonempty(cart, ctx)`（用 `cart_module.is_empty`）。
- 模組常數：`_PHASE_BY_STATE`（機台層→web phase 映射）。

### 2e. `Cart`（`cart.py`）—— 「型別別名 + 模組純函式」，**不是 class**
- `Cart: TypeAlias = dict[str, int]`（商品名→數量）；`QtyVerdict: TypeAlias = Literal["at_cap","zero","over_limit","ok"]`。
- 純函式：`new_cart()`/`add_item(cart,product,qty)`/`get_quantity`/`remaining_capacity`/`classify_qty`/`calc_total`/`clear_cart`/`is_empty`。無 IO。
- SalesMachine 持 `cart`（其唯一 cycle state，由 logic 注入 `new_cart()`），並呼 `cart_module.is_empty/calc_total`。

### 2f. `DialogIO`（`dialog_io.py`，frozen dataclass）—— IO callback 束
```python
@dataclass(frozen=True)
class DialogIO:
    speak: Callable
    read_customer_input: Callable
    print_terminal: Callable = None
    do_action: Callable = None
    speak_and_wait: Callable = None
    display: Callable = None
    def speak_blocking(self, text) -> None: ...   # speak_and_wait or speak fallback
```
states 私有函式 / 子狀態把 callback 束成單一 `io` 收參（machine 不直接建 DialogIO；run_* facade 內注入）。與 SalesMachine 持有的 `callbacks` dict 同源 callable。

### 2g. `nlu`（`nlu.py`）—— 「模組純函式」，**不是 class**
純函式（無 IO/副作用）：`classify_intent(text, mode)`、`parse_quantity(text, default)`、`normalize_input`、`has_quantity`、`split_at_quantity`、`expand_fusion`、`find_quantity_spans` 等；`Intent`/`Literal` 型別。被 states 層使用。

### 2h. `states.run_*`（`states/__init__.py` re-export）—— 模組函式
`run_l1`/`run_dialog`/`run_l4`/`run_l5`（各在 `states/l1.py`/`l2_l3_dialog.py`/`l4.py`/`l5.py`）。4 個具體 State 的 `run` **晚綁定**呼叫 `states.run_*`（mock seam ＝ 模組屬性；測試 monkeypatch.setattr 替換）。

## 3. 畫圖計畫（UML 類別圖 · 版面 / 關係 / 色彩語意 / signature）

### 3a. UML 類別框元件（⑨ signature ＝ 三格框）
本圖需新增 **UML 類別框** 卡型（有別於①②③的 eyebrow/name/desc 卡）：每個類別框三格直疊 —
1. **名格**：類別名（mono 粗體）+ «stereotype»（`«abstract»`/`«dataclass»`/`«type alias»`/`«module»`）；ABC 名用斜體表「抽象」。
2. **欄位格**（細分隔線之上下）：fields（mono 小字，型別標註）。
3. **方法格**：methods（mono 小字，含簽名與回傳）。
分隔線用淺色 rule（蠟筆風可用 `::before` 細線或內部 `<hr>`-like div）。框外框仍走蠟筆 `::before` + Rough hachure 填色（沿用基準）。

### 3b. 色彩語意（6 色 + 珊瑚 hero）
- **珊瑚 coral（hero）**：`SalesMachine`（驅動引擎）。
- **blue**：`State`(ABC) + 4 個具體 `L1State`/`DialogState`/`L4State`/`L5State`（State pattern 階層）。
- **purple**：`Transition`（值物件）。
- **orange**：`Cart`（型別別名 + 資料操作純函式）。
- **cyan**：`DialogIO`（IO callback 束 seam）。
- **green**：`nlu`（純函式模組）。
- **gray**：`states.run_*`（模組函式 facade）。

### 3c. 版面（UML 教科書佈局）
建議 `.stage` 1960×~1140（**最終 trim 貼內容**；無下半死空白）。

```
[ legend/關係圖例 左上 ]                標題 FIG.09（置中）

          ┌──────────────┐   SalesMachine ◆──(_states 持4)──▷ State
          │ SalesMachine │                                    △ (generalization)
 (coral   │ «engine»     │              ┌──────┬──────┬──────┬──────┐
  HERO,   │ +callbacks   │           L1State DialogState L4State L5State   ← blue 4 具體一排
  左)     │ +cart:Cart   │              （各 ..calls..▷ states.run_*）
          │ +enter_hawk  │
          │ +_states     │     State (ABC, blue, 主角頂)   Transition «dataclass» (purple, 右)
          │ run() _emit()│       +entry_invariant            +next_state +enter_hawk
          └──────────────┘       run(machine)→Transition|None  ← State.run ..returns..▷ Transition
                │
   ┌── 協作層（底帶） ───────────────────────────────────────────────┐
   │ Cart «type alias» dict[str,int]   DialogIO «dataclass»   nlu «module» 純函式   states.run_* «module»│
   │ (orange) new_cart/add_item/...    (cyan) speak/read.../   (green) classify_intent  (gray) run_l1/  │
   │                                   speak_blocking()        parse_quantity/...        run_dialog/... │
   └──────────────────────────────────────────────────────────────────┘
[ note 所以呢 三鐵則 填白區 ]
```

主角區優先：`State`(ABC) 在上、4 具體在下一排、generalization 三角開口箭頭朝上匯到 State；`SalesMachine` 左側用 **聚合菱形** 邊連到 State（`_states` 持 4）；`Transition` 右側、`State.run` 與 `SalesMachine` 各一條 dependency 朝它。協作層（Cart/DialogIO/nlu/run_*）置底帶，用 `«uses»` 虛線從 states 階層或 SalesMachine 牽出（避免線太密：每個協作者只牽 1 條代表線 + 文字）。

### 3d. 關係邊（UML 語意 + 對應 marker/線型）
- **generalization（繼承）**：4 具體 State → `State`(ABC)，**空心三角**箭頭頭（需自訂一個 `#tri` marker：空心三角、墨色描邊白填）。線 `.flow` 墨實線。
- **aggregation（聚合）**：`SalesMachine` ◆—→ `State`（`_states` dict 持 4 instance），起點**空心菱形**（自訂 `#diamond` marker）。
- **dependency / «calls» / «returns» / «uses»**：`.async` 虛線 + 開放箭頭（`#ah`）：
  - `State.run` ..returns..▷ `Transition`；`SalesMachine` ..reads..▷ `Transition`。
  - 各 `*State` ..calls(晚綁定)..▷ `states.run_*`。
  - states 階層 ..uses..▷ `DialogIO` / `nlu` / `Cart`；`SalesMachine` ..uses..▷ `Cart`（is_empty/calc_total）。
- 主角階層那幾條（generalization + aggregation）可用珊瑚 `.hawk` 或加粗墨線突顯；其餘協作 `.async` 安靜虛線。線↔箭頭頭同色，標籤（«calls»/«uses»/_states 等）落框間空白。

> ⚠ 自訂 marker（空心三角 generalization / 空心菱形 aggregation）是 UML 正確性所需；務必讓 marker 隨線被蠟筆濾鏡、且 GetPixel 驗描邊色＝線色。

### 3e. legend（左上）
**雙區**：①關係圖例（▷ generalization 繼承 / ◆ aggregation 聚合·持有 / ⇢ dependency 依賴·呼叫）；②色彩語意（引擎 hero / State 階層 / 值物件 / 資料 Cart / IO 束 / 純函式 nlu / 模組 facade）。

### 3f. note（所以呢 · State pattern 三鐵則，填白區）
- **State pattern**：字串 tuple 魔法值（`("L4",0)`）→ `Transition` 值物件 + 4 個 `State` 子類別（machine.py W5）。
- **entry_invariant fail-fast**：每進新層 `assert` cart 空/非空（A4-c）—— 違反即系統 bug 立刻爆。
- **run_\* 晚綁定**（`states.run_*` 模組屬性）：mock seam ＝ 模組屬性，測試 monkeypatch 替換；tuple 魔法值死在各 `run_*` 內、對外 shape 不變。

### 3g. signature
教科書 UML：斜體 `State`«abstract» 頂 + `run(machine)→Transition|None {abstract}` + **空心三角繼承扇**到 4 具體 State，全部以手繪蠟筆渲染。珊瑚只給 `SalesMachine` 引擎 + 主角階層邊。

## 4. 來源檔（核對用）
`sales/states/machine.py`（全部類別在此）、`sales/cart.py`、`sales/dialog_io.py`、`sales/nlu.py`、`sales/states/__init__.py`（run_* re-export）；doc `resources/architecture/20*.md`。
