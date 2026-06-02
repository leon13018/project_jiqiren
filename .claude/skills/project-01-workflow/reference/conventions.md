# 跨任務通用規範（繁簡對照 / 環境 quirk / 工作原則）

> **🎯 何時讀本檔**：需要繁簡對照、踩到環境 quirk，或要套用跨任務工作原則（fix 一條 bug 掃同類全修 / `/goal` 設計）。

## 目錄
- 輸出語言（繁中）+ 繁簡對照表
- 開發環境 quirk（Windows cp936）
- 工作原則：修 bug 掃同類全修
- 工作原則：`/goal` 條件設計

---

## 輸出語言規範（繁體中文）

**規則：本專案所有產出物的中文一律繁體**（成果在中國台灣展示）。紅線權威在 [CLAUDE.md](../../../../CLAUDE.md) §輸出語言規範；本檔補繁簡對照表 + 派發傳達。
- **適用**：程式碼註解 / 字串字面值 / 所有 `.md`（含 CLAUDE.md / memory / resources/）/ commit message 中文 / 任何寫進檔案的中文。
- **不適用**：對話回覆本身（簡繁混合 OK）。
- **派發 subagent/team 時務必把這條塞進其 context**，否則容易產出簡體。

**常見繁簡對照**（拿不定一律傾向台灣慣用詞）：
| 簡 | 繁 | 簡 | 繁 |
|---|---|---|---|
| 机器人 | 機器人 | 显示/设定/设计 | 顯示/設定/設計 |
| 计算/点餐/关键 | 計算/點餐/關鍵 | 执行/检查 | 執行/檢查 |
| 记忆/档案 | 記憶/檔案 | 实作/实现 | 實作/實現 |
| 队列 | **佇列** | 线程 | **執行緒**（非「線程」）|
| 数据 | **資料**（非「數據」）| 网络 | **網路**（非「網絡」）|
| 字符串 | 字串 | 服务器 | 伺服器 |

---

## 開發環境 quirk（Windows cp936 簡體 locale）

**使用者在台灣，但 Windows 系統設定 = 中國大陸 / 簡體（GBK/cp936，非 Big5/cp950）**（2026-05-25 使用者告知，推翻「台灣 Windows=Big5」誤判）。
- 寫 PowerShell / Windows 編碼相關註解時，別假設「台灣 Windows=Big5」；用「系統 code page（這台是 cp936）」或「系統 code page（非 UTF-8）」。
- 使用者用簡體打字 → 經簡轉繁工具 → 我看到繁中；**對話顯示繁中不代表系統環境是繁中**。
- 亂碼問題優先查 **UTF-8 vs cp936** 衝突（如 `Get-Content` 不指定 `-Encoding utf8` 會以 cp936 解碼 UTF-8 檔）。
- 產出物規範不變（仍全繁體，獨立於系統設定）。

---

## 工作原則：修一條 bug 主動掃同類全修

修一條路徑的 bug 時，主動 grep / 列舉同類路徑（同 return state、同 callback pattern、同子狀態類型），一次修完並在報告明列「順帶掃了哪幾條」，不要等使用者第二輪才講「其他也有」。

**Why**（2026-05-26 連續踩）：L4 客服 timeout 回主選單→隱含 dialog/L5 也要；L4 有 mute 訊息但 dialog 沒有→期待所有 L1 重進路徑統一；DnC 12s 改→DyC 也要對稱。每次「修一條、使用者拉回補三條」，同類掃過比 ping-pong 省 round-trip。

**How**：收到「X 路徑有 bug」→ 動手前先 grep 同 return 值 / 同 callback 簽名 / 同 subroutine 入口 → 一次修完、報告明列順帶掃的 sibling；同類語意實際應不同（少數例外）則明說「為何只修這條」。適用：sales/ 狀態機分支、wire-up callback、NLU keyword 同義詞、constants timeout 對稱組。（與 step-by-step pace 不衝突：同類掃描算當前任務範圍，非預先推測。）

---

## 工作原則：`/goal` 條件設計

`/goal` 的 evaluator（小型快速模型，預設 Haiku）每回合後讀對話判斷條件是否滿足；條件太剛性會誤判沒完成、反覆開新回合。三條：

1. **用「>=」「至少」「無 X」描述，不用精確數字**。❌「pytest 顯示 226 passed」（subagent 加 test 後誤判）→ ✅「無 failed、無 error、無 xfailed；passed >= 226」。（2026-05-26 Wave 4 實際 231 passed，精確數字會讓 evaluator 判未滿足。）
2. **跨 Wave 的 invariant 依存在 prompt 明示**：本 Wave 改動若影響後續 Wave 既有 caller 行為（如 Wave 3 改 `parse_quantity("0 瓶")==0` → Wave 4 `add_item` 要 silent skip qty<=0 而非 raise），在後續 Wave prompt 預先指示處理路徑。
3. **明示「subagent 主動更新既有 fixture」合理**：prompt 加「若發現既有 test 規格/fixture 跟本 Wave 修法語意衝突，可主動更新並在 commit message 說明理由，主 agent 會審查」。

**額外觀察**：`/goal` evaluator 對主 LLM 透明（不收「Goal set」訊息，形式同普通使用者訊息，LLM 只是「持續工作直到沒新使用者訊息」）；Task reminder 對線性自動任務是 noise，忽略即可；turn 上限配合 Wave 數（4 wave≈40 / 5-6 wave≈50 / >7 wave 別連跑，reviewable 邊界）；Gotcha M 偶發、不代表每次 subagent commit 都踩，但 `git branch --contains <SHA>` 驗證仍保留。
