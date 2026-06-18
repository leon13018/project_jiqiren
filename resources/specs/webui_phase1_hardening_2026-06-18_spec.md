# WebUI Phase 1 Hardening — Mini SDD spec

**日期：** 2026-06-18
**狀態：** 待實作（worktree + sales-coder）
**前置：** Phase 1（`webui_phase1_2026-06-18_design.md`）已 merge 上 main（`d0de8eb`）+ Pi 實機驗收 1–4 鏡像 ✅。

## 背景與動機
Pi 實機驗收後浮現 1 個 UX bug + 2 條 adopted 反思（皆 Phase 1 防禦性硬化）：
- **UX（使用者報告）**：live 模式 Standby「開始點餐」仍綁 Phase 0 本機 `exitStandby` → 斷線（重新連線中）時點它仍跳轉點餐頁、卻無連線不能點 → 卡死頁。模式 A 下瀏覽器應純被動鏡像、view 全由機器人 WS 驅動。
- **反思 `phase-map-unguarded-keyerror`**：`machine._emit` 用 `_PHASE_BY_STATE[current]`，`current` 非預期值（mock stub / 未來新狀態）→ KeyError crash `SalesMachine.run()`。
- **反思 `web-startup-non-import-error-crash`**：`main._run_wiring` graceful 只包 `ImportError`；`web_server.start()` 等的 `OSError`（port 衝突）等會傳出 → 機器人崩潰，違背「web 掛不開不了機」承諾。

## 改動範圍（3 處，皆 surgical）

### 1. `myProgram/webui/app.js` — `bindEvents` live 模式停用所有改變鏡像狀態的觸控
- **改前**：`if (App._live && (act === "add" || act === "inc" || act === "dec")) return;`
- **改後**：`if (App._live && act !== "adGoto") return;`
- **Why**：模式 A 瀏覽器被動鏡像，view 由機器人 WS 驅動。本機觸控（`exitStandby`/`checkout`/`close`/`place`/`finish`/`add`/`inc`/`dec`）都會與機器人 desync，斷線時更卡死頁。只留 `adGoto`（本機廣告輪播，非鏡像狀態；`toggleReview`/`setView` 在 live 模式已因 `showReview=!_live` 不顯示，`stop`/`noop` 本就 no-op）。
- **驗證**：`?demo=1` 仍完整可用（demo 切換器 + 觸控）；live 模式真驗在 Pi（點「開始點餐」應無反應、留歡迎頁）。

### 2. `myProgram/sales/states/machine.py` — `_emit` phase-map 守衛
- **改前**：
  ```python
  paid = cart_module.calc_total(self.cart) if current == "l5" else 0
  disp(_PHASE_BY_STATE[current], dict(self.cart), paid)
  ```
- **改後**：
  ```python
  phase = _PHASE_BY_STATE.get(current)
  if phase is None:
      return                       # 未知 current → 跳過 emit，不拖垮機器人（web 顯示非關鍵）
  paid = cart_module.calc_total(self.cart) if current == "l5" else 0
  disp(phase, dict(self.cart), paid)
  ```
- **Why**：`current` 非預期值不該 crash 機器人主迴圈；web 鏡像非關鍵 → 未知 phase 靜默跳過（對齊 `make_web_display` 吞例外、「web 掛不拖垮對話」哲學）。今 production `current ∈ {l1,dialog,l4,l5}` 恆有效（unreachable），守衛為防 crash-class（同 `_product_group` 等既有 defense-in-depth 慣例）。
- **測試**（`tests/sales/test_machine.py`）：`disp` spy + 直呼 `machine._emit("unknown_state")` → 斷言不 raise 且 spy 未被呼叫。

### 3. `myProgram/main.py` — `_run_wiring` web 啟動全程 graceful
- **改前**：`try: <3 imports> except ImportError: <fallback>; else: <EventBus/make_web_display/start>`（start 等不受保護）
- **改後**：把 `EventBus()` / `make_web_display(bus)` / `web_server.start(...)` 一併納入 `try`，`except Exception as exc:`（涵蓋 `ImportError` + `OSError` port 衝突 + 其他）→ 印繁中警告（依 exc 區分「依賴缺失」vs「啟動失敗」皆可，訊息含 webui + 退回無 web）→ `web_server=None` + `display_cb = lambda *a, **k: None` 繼續。
- **Why**：文件承諾「web 掛不讓機器人開不了機」，但原實作只防 import；server 啟動失敗（port 佔用等）同樣不該 crash 機器人。
- **測試**（`tests/stt/test_main_wireup.py`）：`--web` + stub `web_server.start` raise（如 `OSError`）→ 斷言 `_run_wiring()` 不 raise、`display` 為 no-op callable、印出含 "webui" 警告。

## Out of scope
- 不改 `myProgram/web/` 既有檔、不動 sales 業務邏輯、不碰 STT（Pi 驗收的 `arecord: Channels count non available` 是音訊裝置設定問題——未帶 `STT_ARECORD_DEVICE`，與本批 / Phase 1 無關）。
- 不做 Phase 2（觸控雙向）。

## 測試指令 + 預期
`python -m pytest tests/` 全綠（現 baseline + 2 新 guard 測試）；既有 sales 行為零改變。

## Commit 規範
3 個 commit（app.js UX / machine guard / main guard），或 machine+main 合一；git add 明列；繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
