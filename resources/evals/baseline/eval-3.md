# Baseline transcript — eval 3 (threading cluster), model=opus

> T0 baseline，現行 verbose skill。場景：新增 STT worker thread 有哪些坑。

## Navigator 回覆

要點（STT 與既有 input_reader 同形狀，5 輪修補教訓可一比一搬）：
- A 架構：STT 取代 input_reader byte source（非並行新 queue）；**單 queue + 順序消費**（禁可變旗號分流，incremental-rebuild §單 queue）；blocking 全推背景 daemon，GUI（cv2/tkinter）留主線程。
- B 複用 input_reader 4 教訓：daemon 卡 blocking syscall → interpreter shutdown hang，靠 `os._exit(0)` 兜底；不要主動 unblock（stdin.close 曾 deadlock）；shutdown 對稱但依資源（tts=terminate subprocess / action=守 sticky 旗號 stopAction / input_reader=只清 queue）；read() latest-wins drain（STT 只推 final result，partial 留 worker 內）。
- C lazy import / Windows pytest 兼容：STT 依賴 Pi-only，禁 Windows 裝；callback 用函式內 lazy import 避免 import 觸發 worker；支援注入式 source 供測試。
- D TTS↔STT 並行特定坑：self-listening（播音被麥克風收回）→ 講話時 mute STT（複用 wait_idle/_pending）；既有 read_customer_input 先 wait_idle 再倒數天然避 echo，保留勿破壞。
- E 紀律：改 myProgram/*.py 必走 SDD、派 sales-coder、三段 reviewer；incremental-rebuild 精神一輪只加一變數（先 FIFO+final-only+mute，barge-in 等後續）；實機驗證唯一真相。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：threading-paths.md → .claude/code_map.md → myProgram/.claude/code_map.md → incremental-rebuild.md → main.py → tts.py → input_reader.py。
- reference→reference：threading-paths → incremental-rebuild（Part C 指向 S1-S7 模板；STT＝再加一 worker/queue 正落單 queue 教訓，兩份須合看）。兩份都指 myprogram-vendor（sticky），但 STT 不碰 vendor，未跳讀。
- 缺漏：**無 STT 專屬 reference**（引擎選型/麥克風/echo/barge-in 全無記載，D 節是推導）；建議實作時補 reference/myprogram-stt.md 或在 spec 定下。
