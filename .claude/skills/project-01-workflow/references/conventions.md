# 跨任務通用規範（繁簡對照 / 環境 quirk / 工作原則）

本檔彙整本專案跨任務都適用的通用規範：輸出語言規範、開發環境 quirk、以及兩條跨任務工作原則（修一條 bug 掃同類全修 / `/goal` 條件設計）。各 section 對應一個來源主題。

---

## 輸出語言規範（繁體中文）

**規則：本專案所有產出物的中文一律使用繁體中文。**

**Why：** 使用者最終成果在中國台灣展示，目標觀眾使用繁體中文。使用者本人跟我溝通時混用簡繁，但**輸出產物必須是繁體**。

### 適用範圍（必須繁體）

- 程式碼註解：`# 顯示訂單明細` ✅ ／ `# 显示订单明细` ❌
- 字串字面值：`"歡迎光臨！冰紅茶 30 元"` ✅ ／ `"欢迎光临！冰红茶 30 元"` ❌
- Markdown 文件（含本專案內所有 `.md`、包括 [CLAUDE.md](../../../CLAUDE.md) / memory / `resources/` 內檔案）
- commit message 內的中文（若有）
- 任何寫進檔案的中文

### 不適用

- 對話回覆本身（我跟使用者的對話）— 簡繁混合 OK，使用者不介意。

### 遇到不確定繁簡寫法時的判斷準則

一律優先繁體。常見對照：

- 「机器人」→「機器人」
- 「显示」→「顯示」 / 「设定」→「設定」 / 「设计」→「設計」
- 「计算」→「計算」 / 「点餐」→「點餐」 / 「关键」→「關鍵」
- 「执行」→「執行」 / 「检查」→「檢查」
- 「记忆」→「記憶」 / 「档案」→「檔案」
- 「实作」→「實作」 / 「实现」→「實現」
- 「队列」→「佇列」 / 「线程」→「執行緒」（注意：台灣用「執行緒」非「線程」）
- 「数据」→「資料」（台灣偏好「資料」非「數據」）
- 「网络」→「網路」（台灣用「網路」非「網絡」）
- 「字符串」→「字串」 / 「服务器」→「伺服器」

若拿不定，傾向台灣慣用詞彙。

**派發 subagent / team 時** → 必須把這條規則塞進他們的 context，否則他們很容易產出簡體中文。

---

## 開發環境 quirk（Windows cp936 簡體 locale）

**使用者實體在台灣，但 Windows 系統設定 = 中國大陸 / 簡體中文**。

**Why：** 2026-05-25 使用者主動告知（在修 hook UTF-8 編碼 bug 之後）。原本依「人在台灣」推斷系統 code page 是 Big5/cp950，事實上是 GBK/cp936（PRC 區域）。這個誤判讓 hook 註解寫了不準確的描述。

### How to apply

- **系統 code page = cp936（GBK，PRC 區域）**，不是 cp950/Big5。任何寫 PowerShell / Windows 編碼相關註解時，避免假設「台灣 Windows = Big5」。正確說法用「PS 5.1 預設 OutputEncoding 為系統 code page（這台是 cp936）」或更保守地用「系統 code page（非 UTF-8）」。
- **使用者輸入流程**：使用者用簡體中文打字 → 經過簡轉繁工具 → 傳給我看到的是繁中。所以對話視窗顯示繁中**不代表**系統環境是繁中。
- **產出物規範不變**：上方〈輸出語言規範〉仍要求所有產出物用繁體中文（最終成果在中國台灣展示），這條獨立於 Windows 系統設定。
- **遇到亂碼問題優先檢查**：UTF-8 vs cp936 衝突（不是 vs Big5）。例如 `Get-Content` 不指定 `-Encoding utf8` 會以 cp936 解碼 UTF-8 檔。

---

## 工作原則：修一條 bug 主動掃同類全修

修一條路徑的 bug 時，主動 grep / 列舉同類路徑（同 return state、同 callback pattern、同子狀態類型），一次修完並在報告裡明列「順帶掃了哪幾條」。不要等使用者第二輪才講「其他也有」。

**Why：** 2026-05-26 這天連續踩到 — 使用者多次說「確保其他沒有會發生這種事的」/「麻煩請統一一下做法好不好」：

- L4 客服 timeout 回主選單 → 隱含要求 dialog / L5 退出也要回 hawk（不只是 L4）
- L4 路徑 'c' 按了有 mute 訊息但 dialog 路徑沒有 → 期待 wire-up 在所有 L1 重進路徑統一表現
- DnC 12s 改完 → DyC 也要 12s（對稱要求）

每次都是「修一條，使用者拉回來補三條」。同類路徑掃過比一輪一輪 ping-pong 省很多 round-trip。

### How to apply

- 收到「X 路徑有 bug」→ 動手前先 grep 同 return 值 / 同 callback 簽名 / 同 subroutine 入口
- 列出全部同類路徑 → 一次修完 → commit message + 報告明列「順帶掃了哪些 sibling」
- 若同類路徑語意實際應該不同（少數例外），明說「為何只修這條」
- 適用範圍：sales/ 狀態機分支、wire-up callback 行為、NLU keyword 同義詞、constants timeout 對稱組

相關原則：step-by-step pace（是說「不要預先做後續推測」，但同類路徑掃描算當前任務範圍，不是預先推測，兩條不衝突）。

---

## 工作原則：`/goal` 條件設計

使用 Claude Code `/goal` 工具設計條件時，evaluator（小型快速模型，預設 Haiku）每回合後讀對話文字判斷條件是否滿足。條件寫得太剛性會誤判沒完成，反覆觸發新回合。

**Why：** 2026-05-26 Wave 1-4 自動跑完後，原 goal 條件寫「pytest 顯示『226 passed, 0 xfailed, 0 failed』」但實際 Wave 4 加了 5 個 cart 邊界測試變成 231 passed — 雖然好於預期，但精確數字不符可能讓 evaluator 判斷「條件未滿足」繼續開新回合。

設計 `/goal` 條件時遵守三條：

### 1. 用「>=」「至少」「無 X」描述，不用精確數字

❌ 反例（剛性，subagent 加 test 後會誤判）：

```
pytest 顯示「226 passed, 0 xfailed, 0 failed」
```

✅ 正例（彈性，容忍正當加測試）：

```
python -m pytest tests/sales/ --tb=no -q 顯示「至少 226 passed, 0 xfailed, 0 failed」
（Wave 內可能新增測試，passed 數 >= 226 都算通過）
```

或更明確：「無 failed、無 error、無 xfailed；passed >= N」。

### 2. 跨 Wave 的 invariant 依存要在 prompt 明示

Wave 3 修了 `parse_quantity("0 瓶") == 0`（原本 fallback 1）→ Wave 4 `add_item` 若 assert qty > 0 會炸 caller。Wave 4 prompt 必須明示處理方式（silent skip qty <= 0 而非 raise）。

**規劃 goal 條件時要預先思考**：本 Wave 改動會不會影響後續 Wave 既有 caller 行為？若會，在後續 Wave prompt 內預先指示處理路徑。

### 3. 明示「subagent 主動更新既有 fixture」合理

Subagent 執行任務時常會看到「既有 test 跟新任務語意衝突」（如 Wave 3 的 `test_nlu.py:L0-QTY-008` 規格本身是 B16 要修的 bug；Wave 3 的 `test_states.py:L4-E-002` fixture「等等」改「想想」因 HP-4 後「等等」走 ACK 不走 E 鏈路）— **這是合理判斷不是越界**。

prompt 內加一句：「若你發現既有 test 規格 / fixture 跟本 Wave 修法語意衝突，可主動更新並在 commit message 明確說明理由；主 agent 會審查」。

### 額外觀察

- **`/goal` evaluator 對 LLM 透明**：主對話 LLM 不會收到「Goal set」系統訊息，從訊息形式看跟普通使用者訊息一樣。LLM 只是「持續工作直到沒有新使用者訊息」— evaluator 在 Claude Code 端決定是否續轉。
- **Task reminder 對線性任務是 noise**：reminder 會反覆要求用 TaskCreate，但 4-wave 線性自動執行不需要追蹤 — 忽略即可。
- **Wave 1-4 一次 `/goal` 跑完無 Gotcha M**：Wave 0 那次踩 Gotcha M 是偶發；不代表每次 subagent commit 都會踩。但驗證流程 `git branch --contains <SHA>` 仍要保留。
- **turn 上限要配合 Wave 數**：Wave 1-4 設 40 turns 是 OK；Wave 5-6 範圍更大建議 50；超過 7 個 Wave 別連跑（reviewable 邊界）。
