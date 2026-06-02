# 在 Monorepo / 大型程式庫中設定 Claude Code<br>（Set up Claude Code in a monorepo or large codebase）

> **本文件性質**：Claude Code 官方文檔頁面的**完整轉述式結構化筆記**。逐節對應原頁，保留所有設定名稱、glob 模式、
> 環境變數、config JSON 範例與全部對照表（這些是功能性事實，照實複製才有用）；散文段落以繁中重組轉述，不逐字全文複製。
> **版權聲明**：原文版權屬 Anthropic；本檔僅在關鍵術語 / 設定鍵 / 極短標誌性語句處做短引用，無逐字全文複製。出處見文末。

---

## 頂部 metadata

| 項目 | 內容 |
|---|---|
| 原文標題 | *Set up Claude Code in a monorepo or large codebase* |
| 來源 | Claude Code 官方文檔 |
| 原文 URL | https://code.claude.com/docs/en/large-codebases |
| 純文字版 URL | https://code.claude.com/docs/en/large-codebases.md |
| 抓取日期 | 2026-06-02 |
| 使用者關注錨點 | `#choose-between-per-directory-claude-md-and-path-scoped-rules` |

**一句話 TL;DR**：大型程式庫裡，為小專案調校的預設值會把不相關的指令與檔案讀取塞滿 context、浪費 token 並拖垮表現；
本指南教個人與團隊用一組**會疊加、不互相取代**的設定，把 Claude **scope 到任務實際碰到的那塊程式碼**。每項設定都註明
是「本機個人」還是「commit 進 repo 給團隊共享」。

---

## 1. 本指南涵蓋什麼（What this guide covers）

- 大型程式庫 = 一個數百萬行的 repo，或含許多 package 的 monorepo。
- 各項設定**彼此獨立、會層疊（layer）而非取代**，挑適用的用即可。
- **先讀「從哪啟動 Claude」**（決定設定檔放哪），最後看「組合起來」。

### 1.1 本頁所有設定一覽（Settings on this page，完整 8 列）

| 我想要… | 用 |
|---|---|
| 只載入我碰到的程式碼的慣例，而非一個 root 檔涵蓋所有子系統 | 每目錄 **CLAUDE.md**（按目錄分層） |
| 排除我從不碰的 package 的 CLAUDE.md | **`claudeMdExcludes`** |
| 擋 Claude 打開 build 產物、生成碼、vendored 依賴 | `permissions.deny` 裡的 **`Read` deny 規則** |
| 透過 language server 找 symbol 定義 / 呼叫者，而非掃檔 | **code intelligence plugin**（LSP） |
| Claude 建 worktree 時只 checkout 任務需要的目錄 | **`worktree.sparsePaths`** |
| 同一 session 內讀寫 sibling package 或另一個 repo | **`--add-dir`** 或 **`additionalDirectories`** |
| 給 Claude 某區專屬、只在相關時才載入的程序知識 | 每目錄 **skills** |
| 用一組大家都安裝的慣例取代大量 per-directory CLAUDE.md | 內部 marketplace 的 **plugin** |

> **Tip（原文補充）**：保持 context 精簡的 workflow 技巧（如把探索丟給 subagent 跑、讓檔案讀取留在主對話之外）見
> *Best practices for Claude Code*；要把基準配置推給全組織開發者見 *Set up Claude Code for your organization*。

### 1.2 全頁範例 monorepo（所有 code 範例都以此為準）

大型單一樹（single-tree）程式庫套用同樣模式：範例中的 `packages/api/` 換成你自己的子系統目錄（如 `src/backend/` / `lib/core/`）。

```text
monorepo/
  CLAUDE.md                     # root instructions
  packages/
    api/
      CLAUDE.md                 # API-specific instructions
      .claude/skills/
      src/
    web/
      CLAUDE.md                 # frontend-specific instructions
      .claude/skills/
      src/
    shared/
      CLAUDE.md                 # shared library instructions
      src/
```

---

## 2. 從哪啟動 Claude（Choose where to start Claude）

**啟動 `claude` 的位置**決定三件事：Claude 不必額外授權就能讀寫哪些檔、啟動時哪些 CLAUDE.md 載入 context、哪些 project 設定生效。

| 從哪啟動 | 檔案存取 | 啟動時載入的 CLAUDE.md | 何時用 |
|---|---|---|---|
| **Repository root** | 每個檔 | 只有 root；子目錄檔在 Claude 讀到那裡時按需載入 | 任務橫跨多個 package / 子系統 |
| **某子目錄** | 只有那個子樹，直到你授權更多 | 該目錄的 + **每個祖先目錄的** | 工作 scope 在單一 package / 子系統 |

> **關鍵 gotcha**：`.claude/settings.json` 的 project 設定**只從你的啟動目錄載入，不像 CLAUDE.md 那樣從父目錄繼承**。
> 放在 repo root 的 `.claude/settings.json` 只在你**從 root 啟動**時生效。
> → 因此後面每節都會註明它的設定檔該放 repo root 還是放你啟動的子目錄、以及該 commit 還是留本機。

---

## 3. 按目錄分層 CLAUDE.md（Layer CLAUDE.md files by directory）

**問題**：大型程式庫單一 root CLAUDE.md 要嘛膨脹到涵蓋每個子系統慣例（浪費 context 在與當前任務無關的指令）、要嘛太籠統而無用。
**做法**：把指令拆成 per-directory 檔 → Claude 載入「全 repo 規則」+「只有你正在動的那塊程式碼的慣例」。

**載入機制**：Claude 啟動時載入工作目錄 + 每個父目錄的 CLAUDE.md；之後讀到某子目錄的檔時，按需載入該子目錄的檔。
root 檔設定全 repo 規則，每個子目錄各加自己的。

**常見的兩層拆法**：
- **Root `CLAUDE.md`**：到處適用的指令——coding standards、commit 慣例、repo 佈局。
- **每子目錄 `CLAUDE.md`**：該區 stack 專屬慣例。monorepo 中每個 package 一個；大型單一樹中每個子系統一個（如 `src/db/`、`src/api/`）。

把這些檔 commit 進 repo，隊友才會繼承。各目錄的 owner 通常維護自己那份。

**root CLAUDE.md 範例**（讓 Claude 對 repo 結構定位）：

```markdown
This is a monorepo with three packages under packages/:

- packages/api: Node.js REST API with Express, TypeScript, and PostgreSQL
- packages/web: React frontend with Vite, TypeScript, and TailwindCSS
- packages/shared: shared TypeScript utilities used by both api and web

Run commands from the package directory, not the monorepo root.
Each package has its own tsconfig.json, package.json, and test suite.
```

**子目錄 `packages/api/CLAUDE.md` 範例**（加該區 stack 專屬 context）：

```markdown
This package is the REST API server.

- Run tests: `npm test` (uses Vitest)
- Run dev server: `npm run dev` (port 3001)
- Database migrations: `npm run migrate`
- Environment variables: copy `.env.example` to `.env`

API routes are in src/routes/. Each route file exports an Express router.
Database queries use Knex in src/db/. Never write raw SQL strings in route handlers.
```

> 從 `packages/api/` 啟動 Claude → 同時載入 `packages/api/CLAUDE.md` 與 root `CLAUDE.md`，**`packages/web/` 的指令不進 context**。

**讓檔案隨程式庫與模型演進保持更新的三法**：
1. **在 PR 中審查**：把 CLAUDE.md 編輯當一般文件變更 review，讓慣例跟著 code 走。
2. **重大模型發佈後重審**：為繞過舊模型限制而寫的指令，等新模型能自己處理後可能變成 overhead。例：強制單檔 refactor 的規則，限制消失後就該刪。
3. **加 Stop hook 提議更新**：[`Stop` hook](https://code.claude.com/docs/en/hooks#stop) 在 Claude 回應結束時收到 session transcript 路徑，腳本可趁缺口還新鮮時審查 session、提議 CLAUDE.md 更新。

### 3.1 ⭐ 在「每目錄 CLAUDE.md」與「path-scoped rules」之間怎麼選

> （Choose between per-directory CLAUDE.md and path-scoped rules — 使用者關注的那節）

每目錄 `CLAUDE.md` 與 `.claude/rules/` 下的 [path-scoped rules](https://code.claude.com/docs/en/memory#path-specific-rules) **都能把指令鎖定到樹的某部分**。
差別在**檔案放哪**與**何時載入**：

| 做法 | 檔案位置 | 何時載入 | 何時用 |
|---|---|---|---|
| **每目錄 `CLAUDE.md`** | 在該目錄內、與其 code 並列 | 從該目錄啟動時於啟動載入，或 Claude 讀到該目錄某檔時按需載入 | 各目錄 owner 維護自己的慣例；指令跟 code 一起版控 |
| **`.claude/rules/` 的 path-scoped rule** | 集中在 repo root 的 `.claude/` | 當 Claude 處理符合該 rule 的 `paths:` glob 的檔案時 | 你想把所有慣例放一處，或同一條 rule 套用到許多散落的路徑 |

> 想看連 skills 也一起比較的版本：原文指向 *Compare similar features*（`/en/features-overview#compare-similar-features`）。

### 3.2 排除不相關的 CLAUDE.md（Exclude irrelevant CLAUDE.md files / `claudeMdExcludes`）

從 repo root 啟動時，每個子目錄的 CLAUDE.md 會在 Claude 一讀到該目錄的檔就載入。**`claudeMdExcludes`** 設定用路徑 / glob
**跳過特定檔，讓它們永不載入**。

- 用於你從不碰的目錄：別隊的 package、legacy code、vendored 子樹。
- **排除清單是靜態的、不是 per-task 開關**。要今天專注 A package、明天 B package → 改用「從該 package 目錄啟動」，別改排除清單。
- 只想對自己生效 → 放 `.claude/settings.local.json`（gitignored、不 commit）。
- 模式用 glob 比對**絕對路徑**，所以相對風格的模式要以 `**/` 開頭才能在樹中任意位置匹配。

```json
// .claude/settings.local.json
{
  "claudeMdExcludes": [
    "**/packages/admin-dashboard/**",
    "**/packages/legacy-*/**"
  ]
}
```

→ 跳過那些 package 下的每個 CLAUDE.md 與 rules 檔；root CLAUDE.md 與你有在動的 package 仍正常載入。

**其他常見模式**：
- `"**/packages/*/CLAUDE.md"` — 排除每個 package 的 CLAUDE.md，但保留 root。
- `"**/packages/web/**"` — 排除 web package 下的所有東西（含 rules）。
- `"/home/user/monorepo/legacy/CLAUDE.md"` — 用絕對路徑排除單一特定檔。

**重點**：
- **Managed policy 的 CLAUDE.md 無法被排除**，組織級指令永遠生效。
- `claudeMdExcludes` 可設在任一 [settings scope](https://code.claude.com/docs/en/settings#configuration-scopes)：user / project / local / managed。
- **陣列跨 scope 會合併**：團隊設 project 級預設，個人可加 local override。

---

## 4. 減少 Claude 讀的東西（Reduce what Claude reads）

指令只是 context 的一部分；**檔案讀取**是另一個隨程式庫增長的成本。以下設定擋掉不相關路徑的讀取，並用 language-server 查詢取代地毯式掃檔。

### 4.1 擋 build 產物 / vendored code 的讀取（`Read` deny 規則）

- Claude 的內容搜尋**預設遵守 `.gitignore`**，所以 `node_modules/`、`dist/`、`build/` 等已列在那裡的路徑，不必額外設定就不會出現在搜尋結果。
- **對於 checked-in 的路徑**（vendored SDK、committed 生成碼）→ 在 `permissions.deny` 加 `Read` deny 規則，即使搜尋列出也擋住 Claude 打開。

放哪：
- 對全 repo 生效 → commit 進 `.claude/settings.json`。
- 個人 → `.claude/settings.local.json`。
- 這些檔**只從啟動目錄載入**：從 root 啟動就放 root；從子目錄啟動就放各 package 的 `.claude/`。
- 要在**任何**啟動目錄都強制 → 設在 [managed settings](https://code.claude.com/docs/en/settings#settings-files)（user / project 設定無法 override）。

```json
// .claude/settings.json
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**)",
      "Read(./**/build/**)",
      "Read(./**/*.generated.*)",
      "Read(./vendor/**)"
    ]
  }
}
```

**Deny 規則的涵蓋範圍與限制**：
- 涵蓋 Claude 內建檔案工具，以及被辨識的 Bash 檔案命令（`cat` / `head` / `grep` / `find` 等）當被 deny 的路徑被當參數傳入時。
- **不會**把被 deny 的路徑從遞迴搜尋的輸出中過濾掉；**不涵蓋**自行打開檔案的任意 subprocess。
- 完整 pattern 語法見 *Read and Edit permission rules*。

### 4.2 用 code intelligence 減少檔案讀取（LSP）

大型程式庫裡找 symbol 定義 / 使用處可能耗掉大量檔案讀取與 grep。[Code intelligence plugins](https://code.claude.com/docs/en/discover-plugins#code-intelligence)
把 Claude 接上 language server，讓它直接跳定義、找 reference、浮現型別錯誤，而非掃整棵樹。

- 官方 marketplace 有 TypeScript / Python / Go / Rust 等常見語言的 plugin。
- 安裝 TypeScript plugin 範例：

```shell
/plugin install typescript-lsp@claude-plugins-official
```

- 要對全 repo 啟用（而非自己裝）→ 加進 [`enabledPlugins` project 設定](https://code.claude.com/docs/en/settings#plugin-settings)。
- **需求**：每台開發者機器要有該語言的 language server binary；從官方 marketplace 安裝需連 GitHub。受限網路 → 改從內部 Git host / 本地路徑加 marketplace。
- 與上面的 `claudeMdExcludes` + `Read` deny 規則互補：那些把不相關內容擋在 context 外，code intelligence 則省去為定位定義而讀遍剩下的內容。

---

## 5. Scope worktree 與檔案存取（Scope worktrees and file access）

控制 worktree 內磁碟上有什麼、以及 Claude 能在啟動點之外讀寫哪些目錄。

### 5.1 只 checkout 需要的目錄（`worktree.sparsePaths`）

`--worktree` 旗標在新 git worktree 開 session，讓變更與主 checkout 隔離。預設 checkout **整個 repo**。
**`worktree.sparsePaths`** 用 git sparse-checkout **只寫出列出的目錄 + root 層級檔案**到磁碟 → worktree 啟動更快、佔空間更少。

- 大家都需要相同路徑 → commit 進 `.claude/settings.json`；個人加路徑 → `.claude/settings.local.json`（清單跨 scope 合併：local 可加不能減）。

```json
// .claude/settings.json
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ]
  }
}
```

- `sparsePaths` 的路徑**相對 repo root**，不論你從哪個子目錄啟動。任何目錄路徑都行，不限 package root。
- 對 [subagent worktree 隔離](https://code.claude.com/docs/en/worktrees#isolate-subagents-with-worktrees)特別有用：每個跑在 worktree 的 subagent 拿到輕量 checkout。**同一 session 所有 worktree 共用同一份 `sparsePaths`**——若一個 subagent 要 `packages/api/`、另一個要 `packages/web/`，兩個都列。
- **列目錄、不列個別檔**。root 層級檔（`package.json`、`tsconfig.base.json`、lock 檔）永遠會跟著被 checkout；**root 層級目錄不會**，所以要 `.claude/settings.json` / `.claude/rules/` / `.claude/skills/` 在 worktree 內可用，就把 `.claude` 列進去。

**搭配 `symlinkDirectories` 避免在多個 worktree 重複大目錄**（如 `node_modules`）：

```json
// .claude/settings.json
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ],
    "symlinkDirectories": [
      "node_modules"
    ]
  }
}
```

→ 每個 worktree 的 `node_modules/` symlink 回主 repo 那份，而非在磁碟複製。

> **Note（原文）**：`sparsePaths` 與 `symlinkDirectories` 在 worktree 建立**之前**從啟動目錄讀取。建立後，session 工作目錄
> 是 worktree root（不是你啟動的子目錄）。因此 worktree 內的 project 設定從 worktree root 的 `.claude/settings.json`
> （即 repo root 那份的 checked-out 副本）載入。**其他要在 worktree 內生效的設定（permission rules / hooks）放 repo root 的 `.claude/settings.json`。**

### 5.2 跨 package / repo 授權存取（`additionalDirectories` / `--add-dir`）

> 本節適用於「從子目錄啟動」或「任務橫跨多個 checkout」。若你從單一大樹的 repo root 啟動，Claude 已能存取每個檔，可跳過。

從 `packages/api/` 啟動時 Claude 只能讀寫該目錄。若任務要跨 package 改動（如更新 `api` 與 `web` 都 import 的 shared type），
需授權 sibling 目錄。同一機制也能授權另一個獨立 checkout 的 repo。

**`additionalDirectories`**（在 `.claude/settings.json`）給 Claude 工作目錄外的目錄存取權：

```json
// .claude/settings.json
{
  "permissions": {
    "additionalDirectories": [
      "../shared",
      "../web"
    ]
  }
}
```

- 相對路徑相對「你啟動 Claude 的目錄」解析。此設定下 Claude 從 `packages/api/` 工作時可讀寫 `packages/shared/` 與 `packages/web/`。

**或在啟動時用旗標臨時授權**（不改設定）：

```bash
claude --add-dir ../shared
```

**不論用哪種方式加目錄，Claude 都能讀寫其中的檔。但該目錄的 CLAUDE.md / `.claude/rules/` / skills 是否也載入，取決於加法**：

| 用什麼加 | 載入 CLAUDE.md 與 rules | 載入 skills |
|---|---|---|
| `additionalDirectories` 設定 | 永不 | 永不 |
| `--add-dir` 旗標 / `/add-dir` 命令 | 只有設下方環境變數時 | 會 |

要讓 `--add-dir` / `/add-dir` 加的目錄載入 CLAUDE.md 與 rules → 設環境變數：

```bash
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude --add-dir ../shared
```

- 此環境變數對 `additionalDirectories` 設定列出的目錄**無效**。
- 大家都需要的 sibling → commit `additionalDirectories`；個人選擇 / 一次性 → `.claude/settings.local.json` 或啟動時 `--add-dir`。

---

## 6. 每目錄 skills（Add per-directory skills）

任何子目錄可定義 scope 到自己 stack 的 [skills](https://code.claude.com/docs/en/skills)。skill **在 Claude 判斷相關時才按需載入**，所以 API 專屬工具不會在前端工作時佔 context。

- skills 放該目錄內的 `.claude/skills/`，跟該區 code 一起 commit。monorepo 每 package 一組；大型單一樹每子系統一組（如 `src/db/.claude/skills/`）。

建立：
```bash
mkdir -p packages/api/.claude/skills/api-testing
```

`packages/api/.claude/skills/api-testing/SKILL.md` 範例（教 Claude 該 package 的測試模式）：

```markdown
---
name: api-testing
description: Testing patterns for the API package. Use when writing or modifying tests in packages/api/.
---

## Test structure

Tests are in `src/__tests__/` mirroring the `src/` directory structure.
Each route file has a corresponding `.test.ts` file.

## Running tests

- All tests: `npm test`
- Single file: `npm test -- src/__tests__/routes/users.test.ts`
- Watch mode: `npm test -- --watch`

## Test utilities

- `src/__tests__/helpers/db.ts`: provides `setupTestDb()` and `teardownTestDb()` for database tests
- `src/__tests__/helpers/auth.ts`: provides `createTestUser()` and `getAuthToken()` for authenticated endpoints

## Patterns

- Use `supertest` for HTTP assertions, not raw fetch
- Always wrap database tests in a transaction that rolls back
- Mock external services in `src/__tests__/mocks/`
```

- 不同子目錄各放各的：`packages/web/.claude/skills/component-patterns/` 描述前端元件慣例。Claude 在 `packages/api/` 工作載 api-testing、在 `packages/web/` 工作載 component-patterns，兩邊互不載入對方。
- **也可用 file pattern 而非放置位置來 scope**：[`paths` frontmatter 欄位](https://code.claude.com/docs/en/skills#frontmatter-reference)吃 glob，Claude 只在處理匹配檔時自動載入。適合「放 repo root 的 `.claude/skills/`、但只套用到某類檔案」的 skill，例如 scope 到 `**/migrations/**` 的 DB migration skill。

### 6.1 讓 skills 保持可被發現（Keep skills discoverable）

skills 散在多目錄時，Claude 選擇的清單會變大。**Claude 靠讀每個被發現的 skill 的 name + description 來挑，只有被選中的那個的完整內容載入 context。**

**哪些 skills 在 scope 內取決於從哪啟動**：
- **從子目錄（如 `packages/api/`）**：該目錄、每個父目錄直到 repo root、加 user 與 enterprise 級的 skills。
- **從 repo root**：session 中 Claude 碰到的每個子目錄的 skills——可累積到**數百個**。
- **用 `--add-dir` 加 sibling 後**：該 sibling 的 skills 也載入。（`additionalDirectories` 只給檔案存取、**不**載 skills。）

**重點**：name 永遠載入，但 [description 在數量多時會被截短](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short)，可能剝掉 Claude 用來判斷是否適用的關鍵字。
→ **description 寫短，並以「請求中會出現的字」開頭**，例如「writing or modifying tests in `packages/api/`」。

- 多目錄共用的 skill（PR 慣例、deploy checklist）→ 放 repo root 的 `.claude/skills/`，任何啟動目錄都載入。
- 共用 skill 需要自己的版本歷史 / 跨 repo → 打包成 [plugin](https://code.claude.com/docs/en/plugins)。plugin skill 用 `plugin-name:skill-name` 命名空間，不會跟 per-directory skill 撞名；平台團隊集中版控更新。
- 找出沒用到的 skill：開 OpenTelemetry logs exporter、設 `OTEL_LOG_TOOL_DETAILS=1`（skill 名照實記錄不被遮）。`skill_activated` 事件的 `skill.name` 記每次呼叫，`invocation_trigger` 記是命令 / Claude / 巢狀 skill 觸發 → 告訴你該合併或退役哪些。

---

## 7. 分層擋不住時，集中化慣例（Centralize conventions when layering stops scaling）

per-directory CLAUDE.md 隨程式庫增長會難以治理：慣例飄移、檔案過時、沒人擁有 root。這通常由維護 repo Claude Code 設定的團隊解決，而非各開發者。

**把慣例與參考內容從「永遠載入的 CLAUDE.md」移到按需載入的機制**：
- [Skills](https://code.claude.com/docs/en/skills)：只在與任務相關時才載入的參考材料。
- [Plugins](https://code.claude.com/docs/en/plugins)：由平台團隊集中擁有的、版控的 skills / hooks / commands bundle。
- [MCP servers](https://code.claude.com/docs/en/mcp)：若組織已對 repo 跑 code search / RAG index，暴露成 MCP 工具讓 Claude 查詢，而非直接讀檔。

> 平台團隊如何集中強制這些，見 *server-managed or endpoint-managed settings*。

### 7.1 在 session 啟動時推薦對的 plugin（SessionStart hook）

慣例搬進 plugin 後，在不熟區域啟動 Claude 的隊友不知道該區 owner 維護哪個 plugin。
[`SessionStart` hook](https://code.claude.com/docs/en/hooks#sessionstart) 可補這缺口——**hook 印到 stdout 的內容會在第一個 prompt 之前加進 Claude context**。

- 例：寫腳本從 [hook input](https://code.claude.com/docs/en/hooks#common-input-fields) 讀啟動目錄 → 在 commit 進 repo 的「路徑→plugin」對照表查 → 印出推薦讓 Claude 在首次回覆轉達。寫法見 *Automate actions with hooks*。

---

## 8. 組合起來（Put it together）

組合配置用 monorepo 佈局；同樣的檔適用大型單一樹的任何子目錄。**project 設定只從你啟動的目錄載入，所以每個子目錄的 `.claude/settings.json` 必須自足，不能疊在 root 檔上。**

範例把 `worktree`、`additionalDirectories`、`Read` deny 規則 commit 進 `.claude/settings.json`，讓每個在 `packages/api/` 的開發者得到相同的 sibling 存取、sparse 路徑、排除。`packages/api/` 的 committed 設定：

```json
// packages/api/.claude/settings.json
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ],
    "symlinkDirectories": [
      "node_modules"
    ]
  },
  "permissions": {
    "additionalDirectories": [
      "../shared"
    ],
    "deny": [
      "Read(./**/dist/**)",
      "Read(./**/build/**)"
    ]
  }
}
```

- 因為 session 從 `packages/api/` 啟動，sibling package 的 CLAUDE.md 已不在 scope，所以這裡**不需** `claudeMdExcludes`（若你也會從 root 啟動，把它加到 repo root 的 `.claude/settings.local.json`）。
- `additionalDirectories` 在你**直接從 `packages/api/` 啟動**時生效。但在從此 session 建的 worktree 內，工作目錄是 worktree root，此設定檔不載入；sibling package 在 worktree 內本就可達，但 **deny 規則需要在 repo root 的 `.claude/settings.json` 再放一份**，worktree session 才會撿到：

```json
// .claude/settings.json（repo root，給 worktree session）
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**)",
      "Read(./**/build/**)"
    ]
  }
}
```

**設定後的 repo 佈局**：

```text
monorepo/
  CLAUDE.md
  .claude/settings.json                           # deny rules for worktree sessions
  packages/
    api/
      CLAUDE.md
      .claude/settings.json                       # worktree, additionalDirectories, deny rules
      .claude/skills/api-testing/SKILL.md
    web/
      CLAUDE.md
      .claude/skills/component-patterns/SKILL.md
    shared/
      CLAUDE.md
```

**從 `packages/api/` 啟動的效果**：
- 載入 root CLAUDE.md 與 `packages/api/CLAUDE.md`，跳過 `packages/web/CLAUDE.md`。
- 可讀寫 `packages/api/` 與 `packages/shared/` 的檔。
- 跳過 `packages/api/` 內 `dist/` / `build/` 的讀取。
- api-testing skill 按需可用。
- 建的 worktree 含 `.claude/`、`packages/api/`、`packages/shared/` 與 root 層級檔，deny 規則由 root 設定檔套用到整個 worktree。

---

## 9. Scope 並規劃跨 package 的變更（Scope and plan changes that span packages）

上面的配置控制 Claude **看到**什麼；當單一變更碰到多個 package（如改 shared type 連同每個呼叫處），**怎麼 scope 與排序任務**也影響結果。

**兩個讓跨 package 變更保持一致的技巧**：
- **在一個 session 給 Claude 整個變更**：把 shared 編輯與其呼叫處一起交付，讓每個編輯背後的決策保持一致，而非每個 package 重新推導。
- **編輯前把計畫存檔**：先 plan，請 Claude 把計畫寫成 repo 內的 markdown 檔。長的跨 package session 途中會 [compact context](https://code.claude.com/docs/en/context-window#what-survives-compaction)，存檔的計畫在對話歷史可能消失之處存活。

---

## 10. 下一步（Next steps）

- 用 [hooks](https://code.claude.com/docs/en/hooks-guide) 在 Claude 編檔後跑 per-directory linter / type-checker。
- 讀 *Manage costs effectively* 了解程式庫大小如何影響 token 用量、以及在更大規模 rollout 前設花費上限。
- 讀部落格文 *How Claude Code works in large codebases*（組織 rollout 模式與 ownership——位於本頁 per-repository 配置之上的組織層）。
  → 本專案已存有該文的結構化筆記：`resources/research/CC_large_codebases_best_practices_2026-06-01.md`。

---

## 附：與本專案（Project_01）的對照（筆者補充，非原文）

本頁是**空間分層**（monorepo 多 package，靠「從哪啟動 / 每目錄檔 / sparse worktree / 跨目錄授權」把 Claude 鎖到一塊）。
Project_01 是**單一 repo、單一啟動點**，所以多數設定（`sparsePaths` / `additionalDirectories` / `claudeMdExcludes` / per-package CLAUDE.md）
當前**用不到**。對本專案真正有參考價值的是：

- **§3.1 每目錄 CLAUDE.md vs path-scoped rules**：本專案已選擇「skill + progressive disclosure」做**主題分層**而非空間分層；若未來要把某些規則綁到特定路徑（如 `myProgram/sales/**`），`.claude/rules/` 的 `paths:` glob 是官方機制。
- **§3 維護三法**（PR 審查 / 模型升級後重審 / Stop hook 提議更新）：與本專案既有 Stop hook、CLAUDE.md 維護原則相通。
- **§4.1 `Read` deny 規則**：可考慮 deny `myProgram/vendor/**` 的讀取以省 context（目前是靠 hook 擋寫、不擋讀）。
- **§6.1 skill description 寫法**：以「請求會出現的字」開頭、描述寫短——本專案 `project-01-workflow` skill 的 description 撰寫可參照。

> 以上為對照觀察，**非建議立即實作**；要不要採用由後續指令決定。

---

## 出處

- **來源**：Claude Code 官方文檔
- **原文標題**：Set up Claude Code in a monorepo or large codebase
- **URL**：https://code.claude.com/docs/en/large-codebases
- **抓取日期**：2026-06-02（WebFetch 全頁，內容完整無截斷）
- **版權聲明**：本檔為轉述式結構化筆記；設定鍵 / glob / 環境變數 / config JSON 範例為功能性事實照實複製，散文以繁中重組，無逐字全文複製。原文版權屬 Anthropic。
