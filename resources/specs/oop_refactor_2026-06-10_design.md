# myProgram OOP 重構 — 傘狀設計（2026-06-10）

> 多 wave 重構的**架構契約**：總原則、類別介面形狀、wave 切分、不變式守護。
> 每個 wave 開工時依 SDD 另寫該 wave 專屬 `specs/<wave>_<date>_spec.md` + `plans/<wave>_<date>_plan.md`；實作細節以 wave spec 為準，與本檔衝突時先回頭修本檔再動工。

## 1. 背景與動機

myProgram（vendor 除外，約 3,900 行）存在系統性重複，依影響排序：

| # | 重複 | 規模 |
|---|---|---|
| 1 | 跨層 confirm 子狀態家族同一 wall-clock 骨架（`cancel_confirm` / `service_confirm` / `invalid_qty_cancel_confirm`；變體：`_dialog_c2_second_stage` / `invalid_qty_reask`） | 5 處 |
| 2 | `_speak_blocking = speak_and_wait if speak_and_wait is not None else speak` | 8 處 |
| 3 | `contains_any(x, KW) or equals_strict_short(x, KW_STRICT)` 雙呼叫 | 11+ 處 |
| 4 | L2/L3 意圖分派三胞胎（`_dialog_main_loop` / `_dialog_dispatch_inner_l2` / `_l3`）+ `_dialog_think_silence_l2`/`_l3` 雙胞胎 | `l2_l3_dialog.py` 944 行主因 |
| 5 | callback 參數鏈 7-8 個參數 × 20+ 呼叫點逐一手傳 | 行數最大單一來源 |
| 6 | worker 三胞胎（tts / action / input_reader）：daemon thread + FIFO queue + drain + singleton 平行結構 | 3 檔 |
| 7 | 小型：`_l4_exit_b` vs `_l4_exit_d_forced`（只差文案）；`parse_quantity` vs `_parse_quantity_in_window`（只差 fallback）；main.py 倒數 loop ×2、finally shutdown ×3 | 零散 |

決議（user 2026-06-10）：教科書 OOP 重寫，多 wave，嚴格 SDD → TDD。

## 2. 總原則

1. **絞殺者 facade**：既有公開函式（`run_*` / `cancel_confirm` / `service_confirm` / `invalid_qty_cancel_confirm` / `logic.run` / `tts.speak` / `action.do` / `input_reader.read` …）保留原名原簽名，內部委派新類別。既有 sales 測試（總數以 SessionStart 快照為準）與所有呼叫端**零修改、不刪不改**——既有測試全綠即重構等價性證明。
2. **每 wave 一輪完整 SDD → TDD**，獨立合併回 main；任一 wave 結束都是穩定可展示狀態，可隨時停。
3. **C++ 概念對應**：虛函式多型 → `ABC` + override（Template Method / State / Strategy 三模式）；泛型 → duck typing + 參數化設定物件。語法只用 `ABC` + `dataclass`（Pi 端舊版 Python 安全），不用新語法。

## 3. 目標類別地圖

```
myProgram/
├── sales/
│   ├── dialog_io.py（新）        DialogIO — callback 束（W2）
│   ├── keyword_group.py（新）     KeywordGroup 類別 + 比對原語（W1）
│   ├── constants/keywords.py     KG_* 組合實例（W1；既有 list 常數全保留）
│   ├── states/
│   │   ├── _timed_confirm.py（新）TimedConfirm(ABC) Template Method（W3）
│   │   │     ├── CancelConfirm(6s) / ServiceConfirm(24s+scan) / InvalidQtyCancelConfirm(6s)
│   │   ├── machine.py（新）       State(ABC) + Transition + SalesMachine（W5）
│   │   └── l2_l3_dialog.py 內部   ModePolicy(ABC) + L2Policy/L3Policy + DialogSession（W4）
│   └── cart / nlu / product_parser 維持純函式（無重複問題，不強制類別化）
├── queue_worker.py（新）          QueueWorker(ABC)：TtsWorker / ActionWorker 繼承（W6）
└── main.py                        TerminalSim 類別（bound methods 當 callbacks）+
                                   _tick_countdown helper + shutdown 迴圈（W6）
```

四個教科書模式各對應一類重複：**Template Method** 收 confirm 家族（#1）、**Strategy** 收 L2/L3 三胞胎（#4）、**State** 收 logic.py 主迴圈、**封裝**（DialogIO / KeywordGroup）收參數鏈與雙呼叫（#2 #3 #5）。

## 4. 核心類別介面

### 4-1. KeywordGroup（W1；類別與比對原語在新檔 `sales/keyword_group.py`、組合實例在 `constants/keywords.py`、`nlu.py` re-export 原語保 caller 相容）

```python
@dataclass(frozen=True)
class KeywordGroup:
    """keyword 雙集封裝：substring 比對集 + 嚴格相等集（防短詞 substring 誤命中）。"""
    substrings: tuple
    strict_short: tuple = ()
    def matches(self, text: str) -> bool:
        return contains_any(text, self.substrings) or equals_strict_short(text, self.strict_short)
```

既有 list 常數全保留（`test_constants` 直接檢查），旁邊加組合實例（如 `CANCEL_YES = KeywordGroup(KEYWORDS_CANCEL_CONFIRM_YES, KEYWORDS_CANCEL_CONFIRM_YES_STRICT_SHORT)`）；呼叫點改 `CANCEL_YES.matches(response)`。

### 4-2. DialogIO（W2，新檔 `sales/dialog_io.py`）

```python
@dataclass(frozen=True)
class DialogIO:
    """對話層 IO callback 束。只裝 IO，不裝業務狀態（cart / 計數器仍獨立傳）。"""
    speak: Callable
    read_customer_input: Callable
    print_terminal: Callable = None   # 部分注入：confirm 類子狀態僅持有部分 callback
    do_action: Callable = None        # （如 cancel_confirm 無 print_terminal），缺欄位者不得使用
    speak_and_wait: Callable = None   # production 必傳；None fallback 給測試
    def speak_blocking(self, text: str):
        (self.speak_and_wait if self.speak_and_wait is not None else self.speak)(text)
```

> W2 修正：`print_terminal` / `do_action` 加 `= None` 預設（部分注入需求，理由如上註解）；`speak_blocking` 用 `is not None` 判斷（保留 8 處 fallback 三元式語意一字不差，非 truthiness）。

公開 `run_*` 簽名不變，facade 內建 `DialogIO`；私有函式收 `io` 一參取代 5-6 個 callback 參數。**cart 與計數器不進 IO**（避免 God Object）。

### 4-3. TimedConfirm 家族（W3，新檔 `sales/states/_timed_confirm.py`）

```python
class TimedConfirm(ABC):
    """計時確認子狀態 Template Method：on_enter → speak_blocking(prompt) →
    wall-clock 迴圈（超時/沉默→on_timeout；keyword→return；亂答→on_unclear 不重置）。"""
    prompt: str
    timeout: float
    def run(self, io): ...            # 共用骨架（唯一一份 wall-clock 迴圈）
    @abstractmethod
    def classify(self, response): ... # 覆寫點 1：keyword → 結果（None=亂答）
    @abstractmethod
    def on_timeout(self): ...         # 覆寫點 2：保守 default
    def on_enter(self, io): pass      # 覆寫點 0（預設 no-op）
    def on_unclear(self, io): pass    # 覆寫點 3（預設 silent 消耗預算）
```

| 子類別 | timeout | classify（行序＝規格） | on_timeout | on_unclear | on_enter |
|---|---|---|---|---|---|
| `CancelConfirm` | 6s | NO 群先→`False`；YES 群→`True` | `True`（取消） | silent | — |
| `ServiceConfirm(allow_scan)` | 24s | scan→`"scan"`；NO 先→`"no"`；YES→`"yes"` | `"no"` | speak 聽不懂 | 印客服電話 |
| `InvalidQtyCancelConfirm` | 6s | CONTINUE 先→`"cancel_overlimit"`；EXIT→`"exit"` | `"cancel_overlimit"` | 重播 prompt | — |

既有三函式變 facade（建 `DialogIO` + 子類別 → `.run(io)`）。

### 4-4. ModePolicy + DialogSession（W4，`l2_l3_dialog.py` 內部）

```python
class ModePolicy(ABC):
    """L2/L3 差異點全集中（Strategy）。資料欄 = class attrs；行為差異 = 5 hook。"""
    nlu_mode: str                  # "l2" / "normal"
    read_timeout: float            # DNC / DYC
    entry_prompt: str
    clarify: str                   # B-1 文案
    reask: str                     # 沉默重問 / 商品全 skip 重問文案
    cancel_declined_resume: str    # cancel_confirm NO 後合成 voice
    think_limit: int               # L2=3 / L3=4
    service_yes_prompt: str        # service_confirm YES 後重啟文案
    silence_think_writeback: bool  # 沉默鏈 think 增量是否回寫主迴圈（L2 False / L3 True；quirk Q1）
    @abstractmethod
    def on_timeout(self, session): ...           # L2 hawk voice 退 L1 / L3 進 C-2
    @abstractmethod
    def on_think_exhausted(self, session): ...   # L2 退場 / L3 進 C-2
    @abstractmethod
    def on_checkout_main(self, session): ...     # 主迴圈語境（碰 unclear）
    @abstractmethod
    def on_checkout_inner(self, session): ...    # 沉默期語境（不碰 unclear；quirk Q2）
    @abstractmethod
    def on_unclear_exhausted(self, session): ... # L2 退場 / L3 最終確認子狀態

class DialogSession:
    """持 io + cart + 計數器（think_count / unclear_count）；統一意圖分派迴圈（取代三胞胎）。"""
    def policy(self) -> ModePolicy:
        return L2_POLICY if cart_module.is_empty(self.cart) else L3_POLICY
```

**policy 每輪迴圈從 cart 即時推導、不存放**——保住「世界狀態驅動、非動作歷史驅動」核心決定。統一 dispatch 優先序（拒絕→想一下→結帳→客服→想買無商品→商品→unclear）只寫一次，差異下放 policy。checkout 拆成 `on_checkout_main` / `on_checkout_inner` 兩 hook——保留沉默期語境不碰 unclear 的既有不對稱（主迴圈 L2 結帳 unclear++，inner L2 結帳不動）。

### 4-5. State / SalesMachine（W5，新檔 `sales/states/machine.py`）

```python
@dataclass(frozen=True)
class Transition:
    """取代 ("L4", 0, 0) 魔法 tuple。"""
    next_state: str            # "dialog" / "l4" / "l5" / "l1"
    via_subroutine_a: bool = False

class State(ABC):
    entry_invariant: str       # "empty" / "nonempty"（machine 進場前驗，A4-c）
    entry_ctx: str             # assert 訊息語境字串（原樣保留）
    @abstractmethod
    def run(self, machine) -> "Transition | None": ...   # None = 程式終止（run_l1 的 None）

class SalesMachine:
    """L1→dialog→L4→L5 主迴圈；持 cart；每次進狀態先驗 cart invariant。"""
```

W5 初版各 State 子類別薄包既有 `run_*`（tuple ↔ Transition 轉換），`logic.run` 變 facade；tuple 魔法值死在 machine 內部，對外測試照舊。machine 持 callbacks dict（L1 callback 集與 dialog 側不同構，不入 DialogIO）。

### 4-6. QueueWorker（W6，新檔 `myProgram/queue_worker.py`）+ TerminalSim（main.py）

```python
class QueueWorker(ABC):
    """daemon worker 模板：FIFO queue + thread + 兜底 catch + drain。"""
    thread_name: str
    def submit(self, item): ...        # 子類別可覆寫（TtsWorker 加 _pending 記帳）
    def _loop(self):
        self.on_thread_start()          # 覆寫點：ActionWorker lazy import vendor
        while True:
            item = self._q.get()
            try:
                self._process(item)     # 覆寫點（必填）：synth+play / runAction
            except Exception as e:
                self.on_error(item, e)  # 預設 noisy print + 繼續下一輪
            finally:
                self.on_done(item)      # 覆寫點：TtsWorker dec _pending + notify
    def shutdown(self):
        self.on_shutdown()              # 覆寫點：terminate mpg123 / 守衛 stopAction
        self.drain()                    # 共用：清 queue
```

`wait_idle` / `_proc` lock 留在 `TtsWorker` 子類別。main.py：`_S1State` + 13 個 closure → `TerminalSim` 類別（`callbacks()` 回 dict 餵 `logic.run(**...)`）；兩個倒數 loop 抽 `_tick_countdown(total, label, wait_tick)`（wait_tick 注入：可中斷版 / `time.sleep` 版）；finally 三段 shutdown 改迴圈。

## 5. Wave 切分

| Wave | 內容 | 收掉的重複 | 風險 | 依賴 |
|---|---|---|---|---|
| **W1 地基** | KeywordGroup；parse_quantity 與 `_parse_quantity_in_window` 合併（`default=` 參數）；`_l4_exit_b`/`_l4_exit_d_forced` 合併 | #3 #7 | 🟢 低 | 無 |
| **W2 DialogIO** | callback 束；sales/ 私有函式改收 io；公開簽名不變 | #2 #5 | 🟢 低-中 | 無 |
| **W3 TimedConfirm** | Template Method 基底 + 三子類別；三 confirm 函式變 facade | #1 | 🟡 中-低 | W2 |
| **W4 ModePolicy** | Strategy + 統一 dispatch，收三胞胎 + think_silence 雙胞胎 | #4 | 🔴 高 | W2 W3 |
| **W5 SalesMachine** | State pattern + Transition；logic.run 變 facade | logic 主迴圈 | 🟡 中 | W2（不必等 W4） |
| **W6 Worker + main** | QueueWorker 基底；TerminalSim；倒數 helper；shutdown 迴圈 | #6 + #7 main 部分 | 🟡 中（多線程） | 無 |

- **W4 是唯一紅色**，可延後或砍掉不阻塞其他 wave（W5 直接包既有 `run_dialog`）。展示日期逼近 → 跑完 W1-W3 先停。
- **W6 合併後必須 Pi 實機驗證**（Windows 測不到真 mpg123 / servo 時序）→ 寫 pineedtodo，實機驗證後才關閉。

### 每 wave 標準流程（嚴格 SDD → TDD）

```
1. EnterWorktree worktree-<wave名>
2. 主 agent 寫 wave spec.md + plan.md（plan 每步 TDD 排序：failing test → RED →
   最小實作 → GREEN → facade 切換 → 既有測試全綠 → commit）
3. spec self-review 4 點 → user approval → commit spec/plan（worktree 首 commit）
4. 派 sales-coder（opus）依 spec+plan 實作
5. Iron Law：主 agent 親跑 python -m pytest tests/sales/ + git branch --contains
6. spec-reviewer（sonnet）→ code-quality-reviewer（opus）
7. 新檔案 → 更新該層 code_map.md
8. ExitWorktree → ff-merge → push（Stop hook sync Pi）
9. user 驗收 → 說繼續才開下一 wave
```

## 6. 測試策略

1. 既有 sales 測試 = 行為等價性證明（打的全是 facade 保留名），不改不刪、每 wave 全綠才合併。
2. 新類別 TDD 新增測試：`test_keyword_group.py` / `test_dialog_io.py` / `test_timed_confirm.py` / `test_machine.py` / `test_queue_worker.py`。重點測多型覆寫點：classify 行序（NO 先於 YES）、on_timeout 保守 default、scan fast path、speak_blocking fallback、Transition 轉換、QueueWorker 兜底 catch（注入會 raise 的 fake `_process`）。
3. W6 限制：Windows 測 queue / drain / shutdown / 兜底邏輯（fake process fn）；真播放 / servo 走 Pi 實機驗證。

## 7. 領域不變式守護清單（每 wave spec 附此對照，reviewer 逐條核）

| # | 不變式 | 主要受影響 wave |
|---|---|---|
| 1 | confirm 類 ambiguous（timeout/亂答/上限）一律保守 default，不推進 | W3 W4 |
| 2 | NO / 保守選項先於 YES 比對 | W1 W3 |
| 3 | strict-short 嚴格相等防 substring 誤命中 | W1 |
| 4 | wall-clock budget 從 speak_and_wait 播完起算 | W2 W3 |
| 5 | L4 雙計時器：36=12×3、子狀態暫停補償、客服 YES reset 覆蓋補償 | W4 W5 |
| 6 | C-2 三選一語意；C-2 CANCEL 不過 cancel_confirm（快速通道例外） | W4 |
| 7 | qty_followup 的 reject 不 gate cancel_confirm（已對齊 UX trade-off） | W4 |
| 8 | dialog 模式由 cart 世界狀態每輪推導，非動作歷史 | W4 |
| 9 | cart invariant fail-fast assert（A4-c）進出每層必查 | W5 |
| 10 | sales/ 嚴格不 import 廠商 SDK（選項 C）；action lazy import 在 worker thread 內 | W6 |

## 8. 歷史註解搬遷政策

- **保留並搬家**：仍成立的「為什麼」（NO 先 check 防「不要取消」誤命中、stdin=DEVNULL 防 mpg123 偷輸入、ALSA drain 防尾音截斷…）——行為的一部分。
- **不搬**：純演進史（日期 / commit 編號 / 「原本…後來改成…」敘事）——git history 與舊 spec 已存，新類別不揹舊包袱。

## 9. Out of scope

- `invalid_qty_reask` 主迴圈與 `_dialog_c2_second_stage` **不入** TimedConfirm 家族（reset 鏈 / 重入主迴圈，硬塞會讓基底長滿 if）。
- `InputReader` 不繼承 QueueWorker（producer 形狀不同，只 reuse drain）。
- `cart` / `nlu` / `product_parser` 維持純函式。
- 不改任何對外行為 / 文案 / 計時值 / keyword 內容；不動 `vendor/`；既有測試不改不刪。
