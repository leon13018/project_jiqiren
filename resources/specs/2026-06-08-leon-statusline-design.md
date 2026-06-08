# leon-statusline 設計規格（spec）

> 日期：2026-06-08（v2，依官方 plugin 指南 + 交叉驗證修正分發架構）｜狀態：草案
> 類型：Claude Code 自訂狀態列，封裝為**可散佈 plugin**、**跨平台**（macOS / Windows / Linux）。
> 技術依據：`resources/research/CC_statusline_config_research_2026-06-08.md`（欄位/語法）、
> `resources/research/CC_statusline_crossplatform_impl_research_2026-06-08.md`（跨平台實作）、
> `resources/research/CC_create_plugins_official_guide.md`（官方建立 plugin 指南）。
> 註：plugin **程式碼**放獨立 git repo `C:\Users\LIN HONG\Desktop\leon-statusline\`（與 Project_01 平行、不巢狀）；spec/plan 留 Project_01 當指揮中心。

---

## 1. 目標

1. **跨平台通用**：同一份 plugin 在 macOS / Windows / Linux 皆可用、可分享給他人。
2. **精緻漂亮**：4 行資訊面板、truecolor 平滑漸層 context bar、乾淨空格分隔。
3. **永不崩潰**：狀態列出錯會害 Claude Code 開不了，故以「絕不崩潰」為第一鐵律。
4. **零執行期依賴**：runtime 只需 Node.js（CC 本身即 Node CLI，保證存在）；不依賴 Nerd Font、不依賴任何 npm 套件。

## 2. 非目標（YAGNI）

- ❌ 不做 MCP「實際連線」探測（只給「已設定數」）。
- ❌ 不做「純活躍時間」追蹤（牆鐘時間含閒置）。
- ❌ 不支援 Nerd Font powerline 字元。
- ❌ 第4行不計入 plugin 帶的 skill/agent/...（只算專案＋user 自訂）。
- ❌ 不縮寫 `workflow`。
- ❌ repo 不顯示 public/private（需 gh/API，破壞零依賴）。

## 3. 封裝與散佈（依官方指南修正）

> **關鍵限制**（官方指南「使用您的 plugin 提供預設設定」段 + 交叉驗證 2 agent 確認）：**plugin 的 `settings.json` 只支援 `agent` / `subagentStatusLine`，不支援主 `statusLine`**。所以「裝 plugin 就自動出現狀態列」**不成立**。採業界實證模式（claude-powerline 等）：**plugin 帶腳本 + 一個 setup 指令，由 setup 把 `statusLine` 寫進使用者 settings.json**。

- 形式：**Claude Code plugin**，repo 兼作 marketplace。
- repo 結構：
  ```
  leon-statusline/                    repo root（marketplace）
    .claude-plugin/marketplace.json   宣告 marketplace、列出 plugin
    README.md
    leon-statusline/                  plugin 本體（${CLAUDE_PLUGIN_ROOT}）
      .claude-plugin/plugin.json      manifest（name/version/...；無 statusLine 欄位）
      statusline.mjs                  主腳本：讀 stdin → 4 行 → exit 0
      setup.mjs                       安全 merge：把 statusLine 寫進指定 settings.json
      skills/setup-statusline/SKILL.md  指令 /leon-statusline:setup-statusline
      src/                            邏輯模組
      tests/                          Vitest 測試
      package.json                    dev: vitest
      README.md
  ```
- **安裝/啟用（他人，3 步）**：
  1. `/plugin marketplace add <repo URL>`
  2. `/plugin install leon-statusline`
  3. `/leon-statusline:setup-statusline [user|project|local]` ← setup 把 statusLine 寫進選定 settings.json
- **statusLine 命令寫入內容**：setup 在 skill 內容中解析 `${CLAUDE_PLUGIN_ROOT}`（此情境**會**展開）成**絕對路徑**寫入：`node "<plugin絕對路徑>/statusline.mjs"`。**不**在 statusLine 命令本身留 `${CLAUDE_PLUGIN_ROOT}`（該情境是否展開未證實，issue #9354）。
- 你自己這台：也可直接把上面那行手動寫進 `~/.claude/settings.json`，或用 setup 指令。

## 3.5 setup 指令行為（/leon-statusline:setup-statusline）

- **範圍參數**：`user`（預設→`~/.claude/settings.json`）/ `project`（`.claude/settings.json`）/ `local`（`.claude/settings.local.json`）。
- **安全 merge**（`setup.mjs`）：讀目標檔 → JSON parse → **只設 `statusLine` 一個 key、其餘原封不動** → 寫回；寫入前**備份整檔**（`settings.json.bak-<時間戳>`）。
- **既有 statusLine → 停下來問**（你的要求）：若目標檔已有 `statusLine`，**不直接覆蓋**；setup 回報 `existing:true`，由指令**提示使用者「偵測到已有 statusLine，覆蓋（舊設定會備份）還是取消？」，經同意才以 `--force` 寫入**。
- 目標檔不存在 → 建最小 `{ "statusLine": {...} }`。
- 寫入的 statusLine 物件含 `refreshInterval: 10`（讓倒數會跳）。

## 4. Runtime 與依賴

- **執行期**：Node.js（`node <path>` 三大 OS 一致、不需 wrapper）。零 npm 執行期依賴。
- **開發期**：**Vitest**（dev-only，不隨 plugin 散佈）。

## 5. 版面設計（4 行）

外觀（空格分隔、無 emoji、英文標籤）：
```
~/…/Project_01  Opus effort:high think:on  token:15.5k  ██████████░░░░░░░░░░ 42%  session:my-session
repo:claude-code  worktree:feat-x  git:main +2 ~1 ↑1↓2  +156 -23  PR:#1234 pending
api:<1m  wall:14m  cost:$0.42  5h:24%(reset 1h23m)  7d:41%(reset 5d4h)
CLAUDE.md:7  memory:5  mcp:3  agent:1  skill:2  hook:13  plugin:2  workflow:1
```

### 條件顯示規則
- **每個 attribute 連同其標題**（如整串 `token:15.5k`）為一顯示單位：抓不到/不存在/不適用 → **整個單位隱藏**。
- **整行只有在「該行所有 attribute 皆缺」時才整行消失**。
- 非 Pro/Max → `5h`/`7d` 隱藏；session 未命名 → `session` 隱藏。

## 6. 各 attribute 規格

| 行 | attribute | 來源 | 格式 | 條件 |
|---|---|---|---|---|
| 1 | 目錄 | `workspace.current_dir` | 家目錄→`~`；超 3 段收 `…` 留最後 2 段 | 永遠 |
| 1 | 模型 | `model.display_name` | 原文 | 永遠 |
| 1 | `effort:` | `effort.level` | low/medium/high/xhigh/max | 有才顯示 |
| 1 | `think:` | `thinking.enabled` | `on` | 僅 true 時 |
| 1 | `token:` | `context_window.total_input_tokens` | `15.5k`（1 位小數 k） | 有才顯示 |
| 1 | context bar | `context_window.used_percentage` | 20 格 `█/░`+` NN%`，平滑漸層 | 有才顯示 |
| 1 | `session:` | `session_name` | 原文 | 命名過才顯示 |
| 2 | `repo:` | `workspace.repo.name` | 原文 | 有才顯示 |
| 2 | `worktree:` | `workspace.git_worktree` | 原文 | 在 worktree 才顯示 |
| 2 | `git:` | git CLI | `<branch> +<staged> ~<modified> ↑<ahead>↓<behind>`；無變動 `clean`；ahead/behind 0 時省略 | 在 git repo |
| 2 | 增刪行 | `cost.total_lines_added/removed` | `+156 -23` | 有才顯示 |
| 2 | `PR:` | `pr.number`/`pr.review_state` | `#1234 pending` | 有 PR 才顯示 |
| 3 | `api:` | `cost.total_api_duration_ms` | 連接非零單位至分鐘；<1 分 `<1m` | 有才顯示 |
| 3 | `wall:` | `cost.total_duration_ms`（含閒置） | `14m`/`2h5m`/`1d3h5m` | 有才顯示 |
| 3 | `cost:` | `cost.total_cost_usd` | `$0.42` | 有才顯示 |
| 3 | `5h:` | `rate_limits.five_hour.*` | `24%(reset 1h23m)` | 僅 Pro/Max |
| 3 | `7d:` | `rate_limits.seven_day.*` | `41%(reset 5d4h)` | 僅 Pro/Max |
| 4 | `CLAUDE.md:` `memory:` `mcp:` `agent:` `skill:` `hook:` `plugin:` `workflow:` | 見 §7 | 整數 | 見 §7 |

### 顏色（truecolor `\x1b[38;2;r;g;b m`；建議值，可微調）
路徑藍 `(86,156,214)`／模型紫 `(197,134,192)`／次要暗灰 `(130,130,130)`／bar 綠`(0,200,80)`→黃`(220,200,0)`→紅`(220,40,40)` 平滑漸層／cost 黃／git clean 綠、有變動 黃、ahead/behind 青／PR approved 綠/pending 黃/changes 紅／5h·7d 依門檻 <70 綠 70–89 黃 ≥90 紅。

## 7. 第4行計數定義（範圍：只算專案＋user 自訂）

- **CLAUDE.md**：遞迴掃專案樹（root=`workspace.project_dir` 或 git root）所有 `CLAUDE.md`；排除 `.git`/`node_modules`/`vendor`/`.venv`/`dist`/`build`。
- **memory**：掃本 session memory 目錄（`~/.claude/projects/<cwd 非英數字元換 '-'>/memory/`）下 `*.md`，**含 `MEMORY.md`**。
- **mcp**：`~/.claude.json` + 專案 `.mcp.json` 的 server 數（已設定數）。
- **agent**：`.claude/agents/` 檔數（專案 + user `~/.claude/agents/`）。
- **skill**：`.claude/skills/**/SKILL.md`（含 SKILL.md 的子目錄）數（專案 + user）。
- **hook**：合併 user + 專案 settings 的 `hooks` 區塊**註冊條目數**。
- **plugin**：settings `enabledPlugins` 數。
- **workflow**：`.claude/workflows/*.js` 數（專案 + user）。
> 計數每 session 快取（§9）。

## 8. 架構

- **進入點 `statusline.mjs`** + **邏輯模組 `src/*.mjs`**（純函式、可獨立測）：
  `parseInput` / `renderLine1..4` / `buildOutput` / `gradientBar` / `colorize` /
  `fmtDuration` / `resetCountdown` / `shortPath` / `attr` / `joinLine` / `gitInfo` / `countInfra` / `withCache`。
- **setup 機制**：`setup.mjs`（`targetPath`/`mergeStatusLine`/`applySetup`）+ `skills/setup-statusline/SKILL.md`（驅動「停下來問」互動）。
- **組裝**：`main()` 讀 stdin → parse → 算四行（缺項隱藏；整行空略過）→ `\n` 串接 → stdout → **`process.exit(0)`**。

## 9. 快取策略

- 快取檔放 `${CLAUDE_PLUGIN_DATA}`（否則退回 `~/.claude/leon-statusline/`）；**不放 tmp**。
- 檔名含 **`session_id`**；不用 `process.pid`。
- TTL：git **2 秒**、計數 **60 秒**。
- statusLine 物件含 `refreshInterval:10`。

## 10. 永不崩潰鐵律

1. `main()` 全包 try/catch；任何例外 → 印 fallback → **`exit 0`**。
2. **永遠至少印一行**。
3. 每欄位當可能 null/缺失，一律 fallback。
4. render 絕不阻塞於子程序/網路（走快取；逾時/失敗略過該 attribute）。
5. git `spawnSync` 設短 `timeout`，失敗吞掉。
6. 狀態/設定檔寫入「先讀後寫、不破壞既有」（setup 亦遵守，且覆蓋 statusLine 前備份 + 問使用者）。

## 11. 跨平台處理

- statusLine 的 `command` 由 setup 寫成**絕對路徑** `node "<plugin root>/statusline.mjs"`；**不**在 command 內留未展開的 `${CLAUDE_PLUGIN_ROOT}`（該情境是否展開未證實，故 setup 預先解析）。
- 腳本內部路徑一律 `os.homedir()` + `path.join()`；絕不信任 `~`、絕不字串拼 `/`/`\\`、絕不讀 `$HOME`/`%USERPROFILE%`。
- 終端寬度：優先 `COLUMNS` 環境變數（CC v2.1.153+），否則 fallback 寫死；不用 `process.stdout.columns`/`tput`。
- git 用 `--no-optional-locks`。

## 12. 測試（Vitest，完整覆蓋）

- **純函式單元**：`fmtDuration`（<1m、d/h/m 邊界）、`resetCountdown`、`shortPath`、`gradientBar`、`attr`、`joinLine`。
- **setup 單元**：`targetPath`、`mergeStatusLine`、`applySetup`（既有 statusLine 不覆蓋、--force 覆蓋+備份、檔案不存在則建立、其餘 key 保留）。
- **情境（mock JSON）**：完整 / 早期 null / 非 Pro / 無 git / 有 worktree / 有 PR / 大量缺欄位。
- **永不崩潰**：空輸入 / 壞 JSON / 缺欄位 → 一律 exit 0 且至少一行。
- **條件顯示**：單 attribute 缺只少該單位、整行全缺才整行消失。

## 13. 待實作階段確認（容錯設計，不阻擋）

- `${CLAUDE_PLUGIN_DATA}` 可用性；不可用退回 `~/.claude/leon-statusline/`。
- memory 目錄編碼規則跨版本；目錄不存在則該 attribute 隱藏。
- marketplace.json `$schema` URL（官方僅確認 plugin-manifest 的 SchemaStore URL）→ 可省略 `$schema`。

## 14. 參考

- `resources/research/CC_statusline_config_research_2026-06-08.md`
- `resources/research/CC_statusline_crossplatform_impl_research_2026-06-08.md`
- `resources/research/CC_create_plugins_official_guide.md`（官方建立 plugin 指南）
- 設計討論：`resources/userPrompt/statusline.md`（使用者逐版草圖）
