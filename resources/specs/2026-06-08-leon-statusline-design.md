# leon-statusline 設計規格（spec）

> 日期：2026-06-08｜狀態：草案，待使用者審閱
> 類型：Claude Code 自訂狀態列，封裝為**可散佈 plugin**、**跨平台**（macOS / Windows / Linux）。
> 設計來源：本檔由 `/superpowers:brainstorming` 流程定案。技術依據見
> `resources/research/CC_statusline_config_research_2026-06-08.md`（基礎欄位/語法）與
> `resources/research/CC_statusline_crossplatform_impl_research_2026-06-08.md`（跨平台實作）。
> 註：本 plugin 的**程式碼**將放在**獨立 git repo** `C:\Users\LIN HONG\Desktop\leon-statusline\`（與 Project_01 平行、不巢狀）；spec/plan 留在 Project_01 當指揮中心。

---

## 1. 目標

1. **跨平台通用**：同一份 plugin 在 macOS / Windows / Linux 皆可用，可分享給他人安裝。
2. **精緻漂亮**：4 行資訊面板、truecolor 平滑漸層 context bar、乾淨空格分隔。
3. **永不崩潰**：狀態列出錯會害 Claude Code 開不了（要 `claude doctor` 修），故以「絕不崩潰」為第一鐵律。
4. **零執行期依賴**：runtime 只需 Node.js（Claude Code 本身即 Node CLI，保證存在）；不依賴 Nerd Font、不依賴任何 npm 套件。

## 2. 非目標（YAGNI，明確不做）

- ❌ 不做 MCP「實際連線」探測（只給「已設定數」；連線探測太重且抓不全內建橋接）。
- ❌ 不做「純活躍時間」追蹤（牆鐘時間含閒置即可，較簡單）。
- ❌ 不支援 Nerd Font powerline 字元（避免他人終端機顯示豆腐）。
- ❌ 第4行不計入 plugin 帶的 skill/agent/...（只算專案＋user 自訂；plugin 數字大、雜、且不可靠）。
- ❌ 不縮寫 `workflow`。

## 3. 封裝與散佈

- 形式：**Claude Code plugin**，repo 兼作 marketplace。
- repo 結構（確切 manifest schema 於實作階段對照當前官方 plugin 文件確認）：
  ```
  leon-statusline/                 ← 獨立 git repo（別人 add 的 URL）
  ├── .claude-plugin/
  │   └── marketplace.json         ← 宣告 marketplace、列出 plugin
  ├── leon-statusline/             ← plugin 本體
  │   ├── .claude-plugin/
  │   │   └── plugin.json          ← manifest；宣告 statusLine 指向 ${CLAUDE_PLUGIN_ROOT}/statusline.js
  │   ├── statusline.js            ← 主腳本
  │   ├── tests/                   ← Vitest 測試
  │   ├── package.json             ← dev 依賴（vitest）；plugin runtime 不需安裝
  │   └── README.md                ← 安裝/分享教學
  └── README.md
  ```
- 安裝（他人）：`/plugin marketplace add <repo URL>` → `/plugin install leon-statusline`。
- statusLine 命令：`node ${CLAUDE_PLUGIN_ROOT}/statusline.js`（零 `~`、不猜家目錄，最安全跨平台）。

## 4. Runtime 與依賴

- **執行期**：Node.js（`node <path>` 三大 OS 呼叫一致、不需 wrapper）。零 npm 執行期依賴。
- **開發期**：**Vitest**（測試框架，dev-only，不隨 plugin 散佈、不影響零執行期依賴）。

## 5. 版面設計（4 行）

外觀（空格分隔、無 emoji、英文標籤）：
```
~/…/Project_01  Opus effort:high think:on  token:15.5k  ██████████░░░░░░░░░░ 42%  session:my-session
repo:claude-code  worktree:feat-x  git:main +2 ~1 ↑1↓2  +156 -23  PR:#1234 pending
api:<1m  wall:14m  cost:$0.42  5h:24%(reset 1h23m)  7d:41%(reset 5d4h)
CLAUDE.md:7  memory:5  mcp:3  agent:1  skill:2  hook:13  plugin:2  workflow:1
```

### 條件顯示規則（重要）
- **每個 attribute 連同其標題**（如整串 `token:15.5k`）為一個顯示單位：**抓不到/不存在/不適用 → 整個單位隱藏**（含標題）。
- **整行只有在「該行所有 attribute 皆缺」時才整行消失**；否則只是少幾個 attribute、其餘照常。
- 非 Pro/Max 帳號 → `5h` / `7d` 兩個 attribute 隱藏。
- session 未命名 → `session` attribute 隱藏。

## 6. 各 attribute 規格

| 行 | attribute（標題） | 來源欄位 | 格式 | 顯示條件 |
|---|---|---|---|---|
| 1 | 目錄（無標題） | `workspace.current_dir` | 家目錄→`~`；超過 3 段則中段收成 `…`、保留最後 2 段 | 永遠（必有） |
| 1 | 模型（無標題） | `model.display_name` | 原文 | 永遠 |
| 1 | `effort:` | `effort.level` | `low/medium/high/xhigh/max` | 有才顯示 |
| 1 | `think:` | `thinking.enabled` | `on` | 僅為 true 時顯示（off/缺省隱藏） |
| 1 | `token:` | `context_window.total_input_tokens` | `15.5k`（1 位小數 k） | 有才顯示 |
| 1 | context bar（無標題） | `context_window.used_percentage` | 20 格 `█/░` + ` NN%`，truecolor 平滑漸層 | 有才顯示；null 隱藏整條 |
| 1 | `session:` | `session_name` | 原文 | 命名過才顯示 |
| 2 | `repo:` | `workspace.repo.name` | 原文 | 有才顯示 |
| 2 | `worktree:` | `workspace.git_worktree` | 原文 | 在 worktree 才顯示 |
| 2 | `git:` | git CLI（`workspace.current_dir`） | `<branch> +<staged> ~<modified> ↑<ahead>↓<behind>`；無變動顯示 `<branch> clean`；ahead/behind 為 0 時省略 | 在 git repo 才顯示 |
| 2 | 增刪行（無標題） | `cost.total_lines_added/removed` | `+156 -23` | 有才顯示 |
| 2 | `PR:` | `pr.number` / `pr.review_state` | `#1234 pending` | 當前分支有 PR 才顯示 |
| 3 | `api:` | `cost.total_api_duration_ms` | 分鐘精度（d/h/m）；不到 1 分鐘顯示 `<1m` | 有才顯示 |
| 3 | `wall:` | `cost.total_duration_ms`（含閒置） | 連接非零單位至分鐘（d/h/m，如 `14m` / `2h5m` / `1d3h5m`） | 有才顯示 |
| 3 | `cost:` | `cost.total_cost_usd` | `$0.42`（2 位小數） | 有才顯示 |
| 3 | `5h:` | `rate_limits.five_hour.used_percentage` / `resets_at` | `24%(reset 1h23m)` | 僅 Pro/Max、且 API 回應後 |
| 3 | `7d:` | `rate_limits.seven_day.used_percentage` / `resets_at` | `41%(reset 5d4h)` | 僅 Pro/Max |
| 4 | `CLAUDE.md:` | 掃專案樹 | 整數 | 有才顯示（見 §7） |
| 4 | `memory:` | 掃 session memory 目錄 | 整數 | 同上 |
| 4 | `mcp:` | `~/.claude.json` + `.mcp.json` | 整數（已設定數） | 同上 |
| 4 | `agent:` | `.claude/agents/` | 整數 | 同上 |
| 4 | `skill:` | `.claude/skills/` | 整數 | 同上 |
| 4 | `hook:` | 合併 settings 的 `hooks` 條目 | 整數 | 同上 |
| 4 | `plugin:` | settings `enabledPlugins` | 整數 | 同上 |
| 4 | `workflow:` | `.claude/workflows/*.js` | 整數 | 同上 |

### 顏色（truecolor `\x1b[38;2;r;g;b m`；以下為建議值，實作可微調）
- 目錄路徑：藍 `(86,156,214)`
- 模型名：紫/洋紅 `(197,134,192)`
- 次要資訊（effort/think/token/各標籤）：暗灰 `(130,130,130)` 或 dim
- context bar：依 fill 由 綠`(0,200,80)` → 黃`(220,200,0)` → 紅`(220,40,40)` 平滑漸層
- cost：黃
- git：clean 綠、有變動 黃、ahead/behind 青
- PR：approved 綠 / pending 黃 / changes_requested 紅
- 5h/7d：依用量門檻變色（<70 綠、70–89 黃、≥90 紅）

## 7. 第4行計數定義（範圍：只算「專案 ＋ user 自訂」）

- **CLAUDE.md**：遞迴掃**專案樹**（root = `workspace.project_dir` 或 git root）所有 `CLAUDE.md`；**排除** `.git`、`node_modules`、`vendor`、`.venv`、`dist`、`build`。
- **memory**：掃本 session 的 memory 目錄（`~/.claude/projects/<由 cwd 推導>/memory/`）下 `*.md`，**含 `MEMORY.md` 索引**。
- **mcp**：`~/.claude.json`（user+local scope）＋ 專案 `.mcp.json` 的 server 數（**已設定數**，非連線）。
- **agent**：`.claude/agents/` 的檔案數（專案＋ user `~/.claude/agents/`）。
- **skill**：`.claude/skills/**/SKILL.md` 數（專案＋ user）。
- **hook**：合併 user＋專案 `settings.json` 的 `hooks` 區塊**註冊條目數**（非數硬碟檔）。
- **plugin**：settings 的 `enabledPlugins` 數（已啟用）。
- **workflow**：`.claude/workflows/*.js` 數（專案＋ user）。
> 計數結果每 session 快取（§9），不每次重掃。

## 8. 架構

- **單檔主腳本** `statusline.js`，內部模組化為單一職責純函式（可獨立測）：
  - `parseInput(stdinText)` → 解析 JSON、容錯。
  - `renderLine1(d)` / `renderLine2(d)` / `renderLine3(d)` / `renderLine4(d)` → 各回傳該行字串（已套條件顯示與顏色）。
  - `gradientBar(pct, width)` → 漸層 bar 字串。
  - `fmtDuration(ms)` → 連接非零單位至分鐘（如 `14m` / `2h5m` / `1d3h5m`）；不到 1 分鐘回 `<1m`。
  - `resetCountdown(epochSec, nowSec)` → `1h23m`。
  - `shortPath(absPath, homeDir)` → 簡短路徑。
  - `gitInfo(cwd)` → `{branch, staged, modified, ahead, behind}`（快取）。
  - `countInfra(cwd, homeDir)` → 第4行各計數（快取）。
  - `withCache(key, ttlMs, fn)` → 通用快取包裝。
  - `colorize(text, rgb)` / `attr(label, value, rgb)` → 上色與「標題+值」單位組裝（值為空則回空字串＝隱藏）。
- **組裝**：`main()` 讀 stdin → `parseInput` → 算四行（缺項自動隱藏；整行空則略過該行）→ 以 `\n` 串接 → `process.stdout.write` → **`process.exit(0)`**。

## 9. 快取策略

- 快取檔放 plugin 持久資料目錄（`${CLAUDE_PLUGIN_DATA}`，否則退回 `~/.claude/`）；**不放 `os.tmpdir()`**（會被系統清理）。
- 檔名含 **`session_id`**（JSON input 提供；穩定唯一）。**不用 `process.pid`**。
- TTL：第2行 `gitInfo` **2 秒**；第4行 `countInfra` **60 秒**。
- `settings.json`（plugin/使用者）設 `refreshInterval: 10`，讓閒置時倒數會跳。

## 10. 永不崩潰鐵律

1. 整個 `main()` 包 try/catch；任何例外 → 印 fallback（至少模型或目錄一行）→ **`exit 0`**。
2. **永遠至少印一行 stdout**（降級的一行勝過空白）。
3. 每個 JSON 欄位皆當可能 null/缺失，一律 `?? fallback`。
4. **render 絕不阻塞於子程序/網路**：`gitInfo`/`countInfra` 走快取；逾時/失敗即略過該 attribute，不卡整體。
5. 子程序（git）用 `spawnSync` 設短 `timeout`，失敗吞掉。
6. 狀態檔寫入採「先讀後寫、不讓既有值遺失」（避免成本/狀態歸零地雷，雖本設計目前不累計成本，仍守此原則）。

## 11. 跨平台處理

- settings/plugin `command` 用 `${CLAUDE_PLUGIN_ROOT}/statusline.js`（無 `~`、無反斜線問題）。
- 腳本內部路徑一律 `os.homedir()` + `path.join()`；**絕不**信任 `~`、**絕不**字串拼 `/`/`\\`、**絕不**讀 `$HOME`/`%USERPROFILE%`。
- 終端寬度：優先讀 `COLUMNS` 環境變數（CC v2.1.153+），否則 fallback 寫死（如 120）；**不**用 `process.stdout.columns`/`tput`。
- git 用 `--no-optional-locks`。

## 12. 測試（Vitest，完整覆蓋）

- **純函式單元測試**：`fmtDuration`（含 `<1m`、跨 d/h/m 邊界）、`resetCountdown`、`shortPath`（含家目錄替換、超長收斂）、`gradientBar`（0/50/100% 顏色與長度）、`attr`（值空回空＝隱藏）。
- **情境測試（mock JSON）**：完整欄位 / 早期 `null`（`used_percentage`、`current_usage`）/ 非 Pro（無 `rate_limits`）/ 無 git repo / 有 worktree / 有 PR / 大量欄位缺失。
- **永不崩潰測試**：對「空輸入 / 壞 JSON / 各種缺欄位」斷言**一律 exit 0 且輸出至少一行**。
- **條件顯示測試**：驗證「單一 attribute 缺 → 只少該單位」與「整行 attribute 全缺 → 整行消失」。

## 13. 待實作階段確認（不阻擋本 spec）

- plugin `marketplace.json` / `plugin.json` 的**確切欄位 schema**（含 statusLine 如何由 plugin 宣告）→ 實作時對照當前官方 plugin 文件確認。
- `${CLAUDE_PLUGIN_DATA}` 是否在所有環境可用；不可用時退回 `~/.claude/leon-statusline/`。
- 各計數路徑（skills/agents/workflows）在非本機環境是否一致 → 以「目錄存在才數、否則該 attribute 隱藏」容錯。

## 14. 參考

- `resources/research/CC_statusline_config_research_2026-06-08.md`
- `resources/research/CC_statusline_crossplatform_impl_research_2026-06-08.md`
- 設計討論：`resources/userPrompt/statusline.md`（使用者逐版草圖）
