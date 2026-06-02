# Claude 如何記住您的專案（Memory — 官方文檔完整統整）

> **本文件性質**：Claude Code 官方文檔 `zh-TW/memory` 頁面的**完整轉述式結構化筆記**。逐節對應原頁，保留所有
> 位置 / 路徑字串、設定鍵、glob 模式、環境變數、config 範例與全部對照表（功能性事實照實複製）；散文以繁中重組。
> **版權聲明**：原文版權屬 Anthropic；本檔僅在關鍵術語 / 路徑 / 極短標誌性語句處短引用，無逐字全文複製。出處見文末。

---

## 頂部 metadata

| 項目 | 內容 |
|---|---|
| 原文標題 | 「Claude 如何記住您的專案」（Memory） |
| 來源 | Claude Code 官方文檔（繁中版） |
| 原文 URL | https://code.claude.com/docs/zh-TW/memory |
| 抓取日期 | 2026-06-02（WebFetch 全頁，內容完整無截斷） |

**一句話 TL;DR**：每個 session 以全新 context window 開始；兩個互補機制跨 session 傳遞知識——**CLAUDE.md**（你寫的持久指令）
與**自動記憶**（Claude 依你的更正自己寫的筆記）。兩者每次對話開始都載入，且被視為**上下文（不是強制配置）**；要硬性阻止某動作得用
[PreToolUse hook](https://code.claude.com/docs/zh-TW/hooks-guide)。

---

## 0. CLAUDE.md vs 自動記憶（兩系統對照）

| | CLAUDE.md 檔案 | 自動記憶 |
|---|---|---|
| **誰編寫** | 您 | Claude |
| **包含內容** | 指令和規則 | 學習和模式 |
| **範圍** | 專案、使用者或組織 | 每個 worktree，跨 worktrees 共享 |
| **載入到** | 每個工作階段 | 每個工作階段（前 200 行或 25KB） |
| **用於** | 編碼標準、工作流程、專案架構 | 建置命令、除錯見解、Claude 發現的偏好 |

- 想**引導** Claude 行為 → 用 CLAUDE.md。想讓 Claude **從更正中自動學習** → 自動記憶。
- Subagents 也可維護自己的自動記憶（見 sub-agents 頁）。

---

## 1. CLAUDE.md 檔案

純文字 markdown，為專案 / 個人 / 組織提供持久指令；Claude 每個 session 開始時讀取。

### 1.1 何時新增到 CLAUDE.md

把 CLAUDE.md 當「寫下你本來會重新解釋的內容」的地方。以下情況新增：
- Claude **第二次**犯同樣的錯。
- code review 發現 Claude 該知道的程式庫知識。
- 你這個 session 又輸入了跟上個 session 一樣的更正 / 澄清。
- 新團隊成員需要相同 context 才能上手。

**保持為「每個 session 都該保留的事實」**：建置命令、慣例、專案佈局、「始終執行 X」規則。
若條目是「多步驟程序」或「只對程式庫一部分重要」→ 移到 [skill](https://code.claude.com/docs/zh-TW/skills) 或 [路徑範圍規則](#18-用-clauderules-組織規則)。

### 1.2 選擇 CLAUDE.md 檔案的位置（完整層級表）

> 下表按**載入順序**列出，從最廣泛範圍到最具體範圍——因此**專案指令在使用者指令之後**出現在 context 中。

| 範圍 | 位置 | 目的 | 共享對象 |
|---|---|---|---|
| **受管理的原則** | macOS：`/Library/Application Support/ClaudeCode/CLAUDE.md`<br>Linux/WSL：`/etc/claude-code/CLAUDE.md`<br>Windows：`C:\Program Files\ClaudeCode\CLAUDE.md` | IT/DevOps 管理的組織範圍指令 | 組織所有使用者 |
| **使用者指令** | `~/.claude/CLAUDE.md` | 所有專案的個人偏好 | 僅您（所有專案） |
| **專案指令** | **`./CLAUDE.md` 或 `./.claude/CLAUDE.md`** | 專案的團隊共享指令 | 透過原始碼控制的團隊成員 |
| **本地指令** | `./CLAUDE.local.md` | 個人專案特定偏好；加進 `.gitignore` | 僅您（目前專案） |

- 工作目錄**上方**目錄層級的 `CLAUDE.md` / `CLAUDE.local.md` 在**啟動時完整載入**；**子目錄**中的檔在 Claude 讀到那些目錄的檔時**按需載入**。
- 大型專案可用 [專案規則](#18-用-clauderules-組織規則) 把指令拆成主題檔，並限定到特定檔案類型 / 子目錄。

### 1.3 設定專案 CLAUDE.md

> **專案 CLAUDE.md 可以儲存在 `./CLAUDE.md` 或 `./.claude/CLAUDE.md` 中。**（原文逐字）

建立此檔，放適用於專案上**任何人**的指令：建置與測試命令、編碼標準、架構決策、命名慣例、常見工作流程。
透過版本控制與團隊共享，所以**專注於專案級標準，而非個人偏好**。

> **Tip（原文）**：執行 `/init` 自動產生起始 CLAUDE.md（Claude 分析程式庫、抓建置 / 測試指令與慣例；已存在則建議改進而非覆蓋）。
> 設 `CLAUDE_CODE_NEW_INIT=1` 啟用互動式多階段流程（詢問要設哪些成品：CLAUDE.md / skills / hooks，用 subagent 探索後呈現可審查提案）。

### 1.4 編寫有效的指令

CLAUDE.md 每個 session 開始載入 context，與對話一起消耗 token。因為是**上下文不是強制配置**，寫法影響可靠度。

- **大小**：每個 CLAUDE.md **目標 < 200 行**。更長消耗更多上下文、降低遵守度。指令變大 → 用[路徑範圍規則](#18-用-clauderules-組織規則)讓指令只在處理匹配檔時載入。也可拆成 [import](#15-匯入其他檔案) 組織（但匯入檔啟動時仍載入、仍進 context）。
- **結構**：用 markdown 標題 + 項目符號分組。組織良好比密集段落更易遵循。
- **具體性**：寫**具體到能驗證**的指令：
  - 「使用 2 空格縮排」而非「正確格式化程式碼」
  - 「提交前執行 `npm test`」而非「測試您的變更」
  - 「API 處理程式位於 `src/api/handlers/`」而非「保持檔案組織」
- **一致性**：兩規則矛盾時 Claude 可能任意選一。定期檢查 CLAUDE.md、子目錄巢狀 CLAUDE.md 與 `.claude/rules/`，移除過時 / 衝突指令。monorepo 中用 `claudeMdExcludes` 跳過別隊無關的 CLAUDE.md。

### 1.5 匯入其他檔案

- CLAUDE.md 用 **`@path/to/import`** 語法匯入其他檔；匯入檔在**啟動時展開並一起載入** context。
- 允許**相對與絕對路徑**；**相對路徑相對「包含匯入的那個檔」解析，不是工作目錄**。可遞迴匯入，**最大深度 4 跳**。

```text
有關專案概述，請參閱 @README，有關此專案的可用 npm 命令，請參閱 @package.json。

# 其他指令
- git 工作流程 @docs/git-instructions.md
```

- **`CLAUDE.local.md`**：不想簽入版控的個人偏好放專案根目錄；與 CLAUDE.md 一起載入、同樣處理；加進 `.gitignore`（`/init` 選個人選項會自動加）。
- **多 worktree 共享個人指令**：gitignored 的 `CLAUDE.local.md` 只存在你建它的那個 worktree。要跨 worktree 共享 → 改從主目錄匯入：
  ```text
  # 個人偏好
  - @~/.claude/my-project-instructions.md
  ```

> **Warning（原文）**：Claude Code **第一次**在專案遇到外部匯入時顯示核准對話列出檔案；拒絕則匯入保持禁用、對話不再出現。

### 1.6 AGENTS.md

- **Claude Code 讀 `CLAUDE.md`，不讀 `AGENTS.md`**。若 repo 已為其他 agent 用 `AGENTS.md` → 建一個 `CLAUDE.md` 匯入它，兩工具讀同一指令不重複，並可在匯入下方加 Claude 專屬指令：
  ```markdown
  @AGENTS.md

  ## Claude Code
  對 `src/billing/` 下的變更使用 plan mode。
  ```
- 不需 Claude 專屬內容時，symlink 也行：`ln -s AGENTS.md CLAUDE.md`（**Windows 建 symlink 需管理員 / 開發者模式，改用 `@AGENTS.md` 匯入**）。
- 在已有 `AGENTS.md` 的 repo 跑 `/init` 會讀它並合併相關部分到產生的 `CLAUDE.md`；也讀 `.cursorrules`、`.windsurfrules`。

### 1.7 ⭐ CLAUDE.md 檔案如何載入（核心機制）

- **沿目錄樹向上走**：Claude 從**目前工作目錄**向上走，檢查沿途每個目錄的 **`CLAUDE.md` 和 `CLAUDE.local.md`**。
  例：在 `foo/bar/` 執行 → 載入 `foo/bar/CLAUDE.md`、`foo/CLAUDE.md` 與沿途任何 `CLAUDE.local.md`。
- **串接（concatenate）不覆蓋**：所有發現的檔被連接進 context，不互相覆蓋。
- **載入順序 = 檔案系統根 → 工作目錄**：`foo/CLAUDE.md` 在 `foo/bar/CLAUDE.md` **之前**出現 → 越接近啟動點的指令**越後**讀。每個目錄內，`CLAUDE.local.md` 接在 `CLAUDE.md` **之後**（個人筆記是該層最後讀的）。
- **子目錄按需載入**：Claude 也會在工作目錄**下方**子目錄發現 `CLAUDE.md` / `CLAUDE.local.md`；它們**不在啟動時載入**，而是 Claude 讀到那些子目錄的檔時才包含。
- monorepo 撿到別隊 CLAUDE.md → 用 `claudeMdExcludes` 跳過。完整佈局見 [Monorepos 和大型儲存庫](https://code.claude.com/docs/zh-TW/large-codebases)。
- **HTML 註解移除**：CLAUDE.md 中**區塊級 HTML 註解**（`<!-- maintainer notes -->`）在注入 context 前被移除（給人類維護者留筆記不耗 token）；**程式碼區塊內的註解保留**；用 Read 工具直接開檔時註解可見。

> **⚠️ 關鍵觀察（與「子目錄 .claude/CLAUDE.md」問題直接相關）**：本節描述的「向上走 / 向下按需」機制，**只檢查每個目錄的
> `CLAUDE.md` 與 `CLAUDE.local.md`**，**沒有**提到會檢查子目錄的 `.claude/CLAUDE.md`。`./.claude/CLAUDE.md` 這個等價位置
> 是在 §1.2 / §1.3 對「**專案指令**（`.` = 工作目錄 / 專案根）」描述的。詳見文末「附錄：子目錄 .claude/CLAUDE.md 的精確結論」。

#### 1.7.1 從其他目錄載入（`--add-dir`）

- `--add-dir` 讓 Claude 存取主工作目錄外的目錄；**預設不載入那些目錄的 CLAUDE.md**。
- 要也載入 → 設環境變數：
  ```bash
  CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude --add-dir ../shared-config
  ```
- 這會從其他目錄載入 **`CLAUDE.md`、`.claude/CLAUDE.md`、`.claude/rules/*.md` 和 `CLAUDE.local.md`**。
  （若用 `--setting-sources` 排除 `local`，則跳過 `CLAUDE.local.md`。）
  > 註：此句是文檔中**唯一**明確把 `.claude/CLAUDE.md` 當「某目錄的目錄級 CLAUDE.md」列出之處，但脈絡是 `--add-dir` 加入的目錄，不是「向下按需載入子目錄」。

### 1.8 用 `.claude/rules/` 組織規則

大型專案可用 `.claude/rules/` 把指令拆成多檔，保持模組化、團隊好維護。規則也可**限定到特定檔案路徑**，只在 Claude 處理匹配檔時載入（減雜訊、省 context）。

> **Note（原文）**：規則在每個 session 或開啟匹配檔時載入。不需常駐 context 的「任務特定指令」改用 [skills](https://code.claude.com/docs/zh-TW/skills)（只在你呼叫或 Claude 判斷相關時載入）。

#### 1.8.1 設定規則
- 在 `.claude/rules/` 放 markdown 檔，每檔一主題、用描述性檔名（`testing.md` / `api-design.md`）。**所有 `.md` 遞迴發現**，可組織進子目錄（`frontend/` / `backend/`）：
  ```text
  your-project/
  ├── .claude/
  │   ├── CLAUDE.md           # 主要專案指令
  │   └── rules/
  │       ├── code-style.md   # 程式碼樣式指南
  │       ├── testing.md      # 測試慣例
  │       └── security.md     # 安全要求
  ```
- **沒有 `paths` frontmatter 的規則在啟動時載入，優先級與 `.claude/CLAUDE.md` 相同。**

#### 1.8.2 路徑特定規則（path-specific rules）
- 用帶 `paths` 欄位的 YAML frontmatter 限定；只在 Claude 處理匹配檔時適用：
  ```markdown
  ---
  paths:
    - "src/api/**/*.ts"
  ---
  # API 開發規則
  - 所有 API 端點必須包括輸入驗證
  - 使用標準錯誤回應格式
  - 包括 OpenAPI 文件註解
  ```
- 沒 `paths` 的規則**無條件**載入、適用所有檔。路徑範圍規則在 Claude **讀到匹配檔時觸發**，不是每次工具使用都觸發。

| 模式 | 匹配 |
|---|---|
| `**/*.ts` | 任何目錄的所有 TypeScript 檔 |
| `src/**/*` | `src/` 下所有檔 |
| `*.md` | 專案根目錄的 Markdown 檔 |
| `src/components/*.tsx` | 特定目錄的 React 元件 |

- 可指定多模式 + 大括號展開匹配多副檔名：
  ```markdown
  ---
  paths:
    - "src/**/*.{ts,tsx}"
    - "lib/**/*.ts"
    - "tests/**/*.test.ts"
  ---
  ```

#### 1.8.3 用符號連結跨專案共享規則
- `.claude/rules/` 支援 symlink（解析後正常載入、循環 symlink 會被偵測處理）：
  ```bash
  ln -s ~/shared-claude-rules .claude/rules/shared
  ln -s ~/company-standards/security.md .claude/rules/security.md
  ```

#### 1.8.4 使用者級別規則
- `~/.claude/rules/` 的個人規則適用你機器上**每個專案**：
  ```text
  ~/.claude/rules/
  ├── preferences.md    # 個人編碼偏好
  └── workflows.md      # 偏好工作流程
  ```
- **使用者級規則在專案規則之前載入 → 專案規則優先級較高。**

### 1.9 為大型團隊管理 CLAUDE.md

#### 1.9.1 部署組織範圍的 CLAUDE.md
- 部署一個集中管理、適用機器上所有使用者的 CLAUDE.md，**無法被個人設定排除**。
- 步驟：(1) 在受管理原則位置建檔（macOS `/Library/Application Support/ClaudeCode/CLAUDE.md`、Linux/WSL `/etc/claude-code/CLAUDE.md`、Windows `C:\Program Files\ClaudeCode\CLAUDE.md`）；(2) 用 MDM / 群組原則 / Ansible 分發。
- **`claudeMd` 金鑰**：可把受管理 CLAUDE.md 內容直接放進 `managed-settings.json`，不必部署單獨檔：
  ```json
  {
    "claudeMd": "Always run `make lint` before committing.\nNever push directly to main."
  }
  ```
  - **範圍**：機器上每個 session、每個 repo。repo 特定指導改用專案 CLAUDE.md。
  - **優先級**：與受管理 CLAUDE.md 相同；在使用者與專案 CLAUDE.md 之前載入。
  - **在何處被遵守**：僅受管理與原則設定；在使用者 / 專案 / 本地設定設 `claudeMd` 無效。

**受管理 CLAUDE.md vs 受管理設定的分工**（設定做技術強制、CLAUDE.md 做行為指導）：

| 關注 | 配置在 |
|---|---|
| 阻止特定工具 / 命令 / 檔案路徑 | 受管理設定：`permissions.deny` |
| 強制沙箱隔離 | 受管理設定：`sandbox.enabled` |
| 環境變數與 API 提供者路由 | 受管理設定：`env` |
| 驗證方法與組織鎖定 | 受管理設定：`forceLoginMethod` / `forceLoginOrgUUID` |
| 程式碼樣式與品質指南 | 受管理 CLAUDE.md |
| 資料處理與合規提醒 | 受管理 CLAUDE.md |
| Claude 的行為指令 | 受管理 CLAUDE.md |

> 設定規則由用戶端強制執行（不論 Claude 怎麼決定）；CLAUDE.md 塑造行為但**不是硬強制層**。

#### 1.9.2 排除特定的 CLAUDE.md 檔案（`claudeMdExcludes`）
- monorepo 中祖先 CLAUDE.md 可能含無關指令。`claudeMdExcludes` 按路徑 / glob 跳過特定檔：
  ```json
  {
    "claudeMdExcludes": [
      "**/monorepo/CLAUDE.md",
      "/home/user/monorepo/other-team/.claude/rules/**"
    ]
  }
  ```
- 模式用 glob 比對**絕對路徑**。可設在任一設定層（使用者 / 專案 / 本地 / 受管理原則），**陣列跨層合併**。
- **受管理原則 CLAUDE.md 無法被排除**（組織指令永遠適用）。

---

## 2. 自動記憶（Auto Memory）

讓 Claude 不必你寫就跨 session 累積知識：工作時自存筆記（建置命令、除錯見解、架構筆記、程式碼樣式偏好、工作流程習慣）。**不是每個 session 都存**——依「未來對話是否有用」決定。

> **Note（原文）**：自動記憶需 Claude Code **v2.1.59+**（`claude --version` 檢查）。

### 2.1 啟用或停用
- 預設**開啟**。切換：session 中開 `/memory` 用切換鈕，或在專案設定設：
  ```json
  { "autoMemoryEnabled": false }
  ```
- 環境變數停用：`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。

### 2.2 儲存位置
- 每個專案有自己的記憶目錄：**`~/.claude/projects/<project>/memory/`**。`<project>` 路徑**源自 git 儲存庫**，所以**同一 repo 內所有 worktrees 與子目錄共享同一個自動記憶目錄**。git repo 外則用專案根目錄。
- 改位置：設 `autoMemoryDirectory`（任一設定範圍：使用者 / 專案 / 本地 / 原則 / `--settings`）：
  ```json
  { "autoMemoryDirectory": "~/my-custom-memory-dir" }
  ```
  - 值必須是絕對路徑或以 `~/` 開頭。在專案 `.claude/settings.json` / `settings.local.json` 設時，需先接受該資料夾的**工作區信任對話**才生效（與管理 hooks 同閘道）。
- 目錄結構：
  ```text
  ~/.claude/projects/<project>/memory/
  ├── MEMORY.md          # 簡潔索引，載入到每個工作階段
  ├── debugging.md       # 除錯模式詳細筆記
  ├── api-conventions.md # API 設計決策
  └── ...                # Claude 建立的任何其他主題檔案
  ```
- **自動記憶是機器本地的**，不跨機器 / 雲端共享。

### 2.3 它如何運作
- **`MEMORY.md` 前 200 行或前 25KB（先到為準）** 每次對話開始載入；超過閾值的內容啟動時不載入。Claude 靠把詳細筆記移到主題檔保持 `MEMORY.md` 簡潔。
- 此限制**僅適用 `MEMORY.md`**；CLAUDE.md 不論長度都完整載入（但短檔遵守度更好）。
- 主題檔（`debugging.md` / `patterns.md`）**啟動時不載入**，Claude 用標準檔案工具**按需讀取**。
- 介面顯示「寫入記憶 / 回憶記憶」時 = Claude 正在更新 / 讀取 `~/.claude/projects/<project>/memory/`。

### 2.4 審計和編輯
- 自動記憶檔是純 markdown，可隨時編輯 / 刪除。`/memory` 可瀏覽並開啟。

---

## 3. 用 `/memory` 檢視和編輯
- `/memory` 列出目前 session 載入的所有 CLAUDE.md / CLAUDE.local.md / 規則檔，可切換自動記憶開關，並提供開啟自動記憶資料夾的連結；選任一檔在編輯器開啟。
- 要 Claude「記住」某事（如「始終用 pnpm 不用 npm」）→ 存進自動記憶。要改成寫進 CLAUDE.md → 直接說「將此新增到 CLAUDE.md」或用 `/memory` 自己編輯。

---

## 4. 疑難排解記憶問題

### 4.1 Claude 不遵循我的 CLAUDE.md
- CLAUDE.md 內容是**系統提示之後的使用者訊息**，不是系統提示本身 → Claude 讀並嘗試遵循，但**無嚴格遵守保證**（尤其模糊 / 衝突指令）。
- 除錯：
  - `/memory` 驗證 CLAUDE.md / CLAUDE.local.md 有被載入（沒列出 = Claude 看不到）。
  - 檢查相關 CLAUDE.md 是否在「為本 session 載入的位置」。
  - 指令更具體（「2 空格縮排」優於「正確格式化」）。
  - 找跨檔衝突指令。
- 必須在**特定時間點**執行的（每次提交前 / 每次編檔後）→ 改寫 [hook](https://code.claude.com/docs/zh-TW/hooks-guide)（固定生命週期事件、無論 Claude 怎麼決定都適用）。
- 想要**系統提示層級**的指令 → `--append-system-prompt`（每次呼叫都要傳，較適合腳本 / 自動化）。

> **Tip（原文）**：用 [`InstructionsLoaded` hook](https://code.claude.com/docs/zh-TW/hooks#instructionsloaded) 記錄**確切載入了哪些指令檔、何時、為何**——對**除錯路徑特定規則或子目錄中的延遲載入檔案**很有用。

### 4.2 我不知道自動記憶保存了什麼
- `/memory` → 選自動記憶資料夾瀏覽，純 markdown 可讀 / 編 / 刪。

### 4.3 我的 CLAUDE.md 太大了
- 超過 200 行消耗更多上下文、可能降遵守度。用路徑範圍規則只在處理匹配檔時載入，或修剪非每 session 需要的內容。拆成 `@path` 匯入有助組織但**不減上下文**（匯入檔啟動時載入）。

### 4.4 指令在 `/compact` 後似乎丟失了
- **專案根目錄 CLAUDE.md 在壓縮中倖存**：`/compact` 後從磁碟重讀並重新注入。
- **子目錄巢狀 CLAUDE.md 不會自動重新注入**；Claude 下次讀該子目錄的檔時才重新載入。
- 壓縮後消失的指令，要嘛只在對話中給過、要嘛在尚未重載的巢狀 CLAUDE.md。對話專用指令 → 加進 CLAUDE.md 使其持久。

---

## 附錄：⭐「子目錄能不能把 CLAUDE.md 放進子目錄的 `.claude/`？」精確結論

> 這是本次查詢的核心問題。使用者推論：「專案 CLAUDE.md 可存 `./CLAUDE.md` 或 `./.claude/CLAUDE.md` → 子目錄也可放 `<子目錄>/.claude/CLAUDE.md`」。
> 依本頁原文，**這個推論文檔未明確支持**，須分情況：

**證據盤點**：
1. `./CLAUDE.md` 或 `./.claude/CLAUDE.md` 的等價，原文是在「**專案指令**」層級講的（§1.2 表格、§1.3）；這裡的 `.` 指**工作目錄 / 專案根**。
2. §1.7「CLAUDE.md 如何載入」描述向上走 / 向下按需時，**逐字只說檢查每個目錄的 `CLAUDE.md` 與 `CLAUDE.local.md`**，**未提**會去看子目錄的 `.claude/CLAUDE.md`。
3. 全文唯一把 `.claude/CLAUDE.md` 當「某目錄的目錄級檔」明確列出的，是 §1.7.1 `--add-dir` 載入清單（`CLAUDE.md`、`.claude/CLAUDE.md`、`.claude/rules/*.md`、`CLAUDE.local.md`）——但脈絡是 `--add-dir` 加入的目錄，非「向下按需載入子目錄」。

**結論（分情況）**：
- ✅ **若你直接「從子目錄啟動 Claude」**：該子目錄成為工作目錄，`./.claude/CLAUDE.md`（相對它）就是「專案指令」→ 會被當專案 CLAUDE.md 載入。此情況下 `<子目錄>/.claude/CLAUDE.md` 可行。
- ❓ **若你從專案根啟動、靠「向下按需」載入子目錄**：文檔只保證 `<子目錄>/CLAUDE.md`（直接放）會被發現載入；**`<子目錄>/.claude/CLAUDE.md` 是否會被按需發現，文檔未明確記載**。
- ✅ **官方 large-codebases 頁的所有子目錄範例**：per-directory CLAUDE.md **一律直接放 `<子目錄>/CLAUDE.md`**，從未用 `.claude/` 變體。

**實務建議**：
- 子目錄 CLAUDE.md **用官方明示、保證載入的 `<子目錄>/CLAUDE.md`（直接放）**，不要塞進 `<子目錄>/.claude/`（後者按需載入未獲文檔背書）。
- 若仍想驗證 `<子目錄>/.claude/CLAUDE.md` 在你的啟動方式下會不會載入 → 用 §4.1 提到的 **`InstructionsLoaded` hook** 實測（它正是為「除錯子目錄延遲載入檔」設計）。

---

## 出處
- **來源**：Claude Code 官方文檔（繁中版）
- **原文標題**：Claude 如何記住您的專案（Memory）
- **URL**：https://code.claude.com/docs/zh-TW/memory
- **抓取日期**：2026-06-02（WebFetch 全頁，完整無截斷）
- **版權聲明**：本檔為轉述式結構化筆記；位置 / 路徑字串、設定鍵、glob、環境變數、config 範例為功能性事實照實複製，散文以繁中重組，無逐字全文複製。原文版權屬 Anthropic。
