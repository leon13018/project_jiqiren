# --hawk 進場 flag + SALES_KEYBOARD 鍵盤 gate + 啟動防呆 — SDD spec（2026-06-21）

## 1. 背景與動機
使用者要求：demo 預設**不用鍵盤控制**，改用 web 網頁（server）或語音（STT）；偶爾要鍵盤再開。
- 觀察（Pi）：`--web` 下雖無語音 echo，但鍵盤 `1`/`t`/`q` 仍能控制。
- 衝突：L1 選單需鍵盤按 `1` 進叫賣，但 web token 無 `1`、語音在 L1 未開麥 → 純關鍵盤會卡在選單。
- 使用者定案（乙＋防呆）：**模式入口改用 CLI flag**（`--hawk` 直接進叫賣，未來其他模式 `--<mode>`）＋ **鍵盤預設關閉**（`SALES_KEYBOARD=1` 才開）＋ 退出用 Ctrl+C ＋ **啟動防呆**：不允許「無 mode flag 且鍵盤關」的組合（會卡死）→ 直接擋下結束。

## 2. 設計核心 + 行為規約
### A. `--hawk` 進場 flag（複用既有 enter_hawk_immediately 機制）
- `main._run_wiring`：`start_hawk = "--hawk" in sys.argv` → 傳給 `logic.run(start_hawk=start_hawk)`。
- `logic.run`：新增 `start_hawk: bool = False` 參數 → `SalesMachine(callbacks, cart, start_hawk=start_hawk)`。
- `SalesMachine.__init__`：新增 `start_hawk: bool = False` → `self.enter_hawk_immediately = start_hawk`（取代 hardcode `False`）。
- 效果：`--hawk` 時**首次** L1 進場即 `enter_hawk_immediately=True` → 跳選單直接 hawk；之後 cycle 不變。**可擴充**：未來新模式加新 flag → 新進場分派（本次只 hawk）。

### B. `SALES_KEYBOARD` 鍵盤 gate（gate stdin reader thread）
- `input_reader.py`：module-level `_KEYBOARD = bool(int(os.environ.get("SALES_KEYBOARD", "0")))`（預設 0=關）。
- `InputReader.__init__(self, source=None, *, keyboard_enabled=True)`：`if keyboard_enabled:` 才啟動 `_loop` stdin daemon thread。
- module singleton `_reader = InputReader(keyboard_enabled=_KEYBOARD)`（production 由 env 帶入，預設關）。
- **`keyboard_enabled` 預設 True**：給既有測試 fixtures（`InputReader(source=...)`）沿用——它們要 thread 跑去消化 FakeByteSource；production 唯一實例是 singleton，明確帶 `_KEYBOARD`。加註解說明此預設理由。
- **不受 gate 影響**：`inject()`（web/觸控 + 語音 STT 共用 sink）、`read()`、`shutdown()` 全照常 → 關鍵盤後 web/語音仍完整驅動。

### C. 退出
- 關鍵盤後 `q` 不可用 → **Ctrl+C**（既有 `main()` 的 `except KeyboardInterrupt`，無需改）。

### D. 啟動防呆（user 追加）
- `main._run_wiring` 解析 flag 後，**call-time** 讀 `keyboard_on = bool(int(os.environ.get("SALES_KEYBOARD", "0")))`。
- **若 `not start_hawk and not keyboard_on`**（無任何 mode flag 且鍵盤關）→ 印明確繁中訊息後 **early `return`**（不啟 web、不跑 logic.run），交回 `main()` 走 cleanup + `os._exit(0)`。防止卡在無法操作的選單。
- 訊息範例：`「[系統] 未指定模式入口 flag（如 --hawk）且鍵盤已停用；無可用控制方式。請加 --hawk 直接進入模式，或設 SALES_KEYBOARD=1 以鍵盤操作選單。」`
- 合法組合：① 有 `--hawk`（鍵盤開關皆可）；② 無 mode flag 但 `SALES_KEYBOARD=1`（選單 + 鍵盤）。
- main 的這個 call-time env 讀與 input_reader 的 import-time `_KEYBOARD` 各自讀同一 env（沿用 SALES_VOICE 多模組各自讀 precedent；production 同一啟動 env 值一致）。

## 3. 改檔範圍（高層；step 移 plan.md）
| 檔 | 改動 |
|---|---|
| `myProgram/main.py` | `_run_wiring` 解析 `--hawk` → `logic.run(start_hawk=...)`；**加 D 啟動防呆 guard**（call-time 讀 SALES_KEYBOARD）；docstring 註明 `--hawk` + 防呆 |
| `myProgram/sales/logic.py` | `run()` 加 `start_hawk: bool = False` → `SalesMachine(start_hawk=...)`；docstring 更新 |
| `myProgram/sales/states/machine.py` | `SalesMachine.__init__` 加 `start_hawk: bool = False` → `self.enter_hawk_immediately = start_hawk`；docstring 註記 |
| `myProgram/input_reader.py` | `_KEYBOARD` env 旗標 + `InputReader.__init__` 加 `keyboard_enabled` gate + singleton 帶 `_KEYBOARD`；docstring/註解 |
| `tests/stt/test_main_wireup.py` | **更新既有 --web/terminal 佈線測試 argv 加 `--hawk`**（否則被防呆擋）；加 `--hawk`→start_hawk=True / 無 → False 測試；加防呆測試（無 flag+鍵盤關→印訊息+early return 不呼 logic.run；無 flag+`SALES_KEYBOARD=1`→正常跑） |
| `tests/sales/test_machine.py` | 加測：`SalesMachine(start_hawk=True)`→首次 L1 `enter_hawk_immediately=True`；預設 False |
| `tests/sales/test_logic.py` | 加測：`logic.run(start_hawk=True)` 穿到 machine（與 machine 測重疊可精簡） |
| `tests/sales/test_input_reader.py` | 加測：`keyboard_enabled=False`→不讀 source 但 inject/read 仍可；`=True`（既有預設）→ 讀 source（行為不變） |

## 4. Out of scope
- **不動 `inject()` / `read()` / `shutdown()` 邏輯**、不動 web token 詞彙（`commands.py`）、不動 STT。
- 不改既有 enter_hawk transition cycle（交易完成→hawk 連續叫賣不變）。
- 不動 SALES_VOICE / SALES_SHOW_COUNTDOWN、不改退出機制（Ctrl+C 既有）。
- doc 更新（reference 註明 --hawk / SALES_KEYBOARD / 防呆）由主 agent 收尾。

## 5. 規範與參考
- 派 sales-coder（opus，預載 karpathy + TDD）。最小外科：複用 enter_hawk_immediately、不重構主迴圈。
- 繁中產出。對照 `myprogram-threading-paths.md`（input_reader 單 queue / daemon thread 慣例）確認 gate 不破壞 thread 模型。

## 6. 測試指令 + 預期結果
- `py -3.14 -m pytest tests/sales/ tests/stt/ -q` → 全綠、無 FAIL/ERROR（既有 input_reader 8 test + --web 佈線測試更新後不變 + 新增數個）。
- 行為：`--hawk` → 首次進 hawk（不印選單）；`SALES_KEYBOARD` 未設 → stdin thread 不啟、`inject` 仍驅動；`=1` → 鍵盤照舊；無 flag+鍵盤關 → 防呆訊息 + 結束。
- Pi：
  - `python3.11 -m myProgram --web --hawk` → 開機直接叫賣、鍵盤無效、web/語音驅動、Ctrl+C 退出。
  - `SALES_KEYBOARD=1 python3.11 -m myProgram --web` → 顯選單、鍵盤可按 1/q。
  - `python3.11 -m myProgram --web`（無 flag、鍵盤關）→ 印防呆訊息後結束（不卡）。

## 7. Commit 規範
- worktree 首 commit：spec + plan doc。
- 實作 commit：prod（main/logic/machine/input_reader）+ tests，`git add` 明列、禁 `-A`（prod/test 可分 commit）。
- message：`feat(input): add --hawk mode-entry flag + SALES_KEYBOARD gate + startup guard` + 繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
啟動防呆：not --hawk and not SALES_KEYBOARD=1 → 印訊息 + 結束（防卡死）
進場：    --hawk → start_hawk=True → SalesMachine.enter_hawk_immediately=True → 首次 L1 跳選單直接 hawk
鍵盤：    SALES_KEYBOARD=0(預設) → 不啟 stdin _loop thread；inject()(web/語音) 照常 → 只 web/語音控制
          SALES_KEYBOARD=1 → 啟 stdin thread → 鍵盤可用（疊加 web/語音）
退出：    Ctrl+C（KeyboardInterrupt，既有處理）
```
