# Skill scripts/ vs Dynamic Workflows——流程該固化到哪裡（判準研究）

> **本檔性質**：deep-research workflow（6 角度 fan-out、22 來源、94 claims 抽取、25 條三票對抗驗證 → 23 確認 2 否決）的綜整筆記。聚焦**淨增量主題**：「一段流程/可執行邏輯該寫成 skill 附帶的 `scripts/` 還是 `.claude/workflows/` 的 dynamic workflow 腳本」。
> **與既有筆記的關係**：workflows 編排細節（meta/pipeline/args 踩坑）→ `workflows_orchestration_research_2026-06-04.md`；skills 撰寫實踐 → `skills_best_practices_research_2026-06-03.md`、`CC-skills.md`；本檔不重述。
> **版權**：轉述式結構化筆記，原文版權屬 Anthropic 及各來源；標誌性語句短引用。抓取日期 2026-06-07。

---

## 0. 一句話答案

**判準＝「誰持有 plan」+「誰做工」**（官方 workflows docs 原語：「The difference is who holds the plan」）：

| 你要固化的東西 | 寫成 | 為什麼 |
|---|---|---|
| **確定性邏輯本身**（排序/解析/驗證/健檢——不該靠 token 生成的工作） | **skill `scripts/`** | shell 行程直接做工，code 不進 context、只有輸出耗 token；Claude 保留編排權 |
| **多 agent 編排的 plan**（迴圈/分支/扇出/對抗驗證——單一對話協調不了的規模） | **`.claude/workflows/` 腳本** | runtime 在隔離環境持有 plan 與中間結果，Claude context 只收最終答案 |

兩者不互斥：本專案現行「memory-health.ps1（script 做確定性檢查）+ skill-edd-regression.js（workflow 編排 grader 群）」正是各歸其位。

---

## 1. Skill `scripts/`——官方定位（驗證 3-0 ×3 組）

- **設計意圖**：「certain operations are better suited for traditional code execution... require the **deterministic reliability that only code can provide**」（engineering blog）；「**instructions for flexible guidance, code for reliability**」（platform docs）。固化判準＝該操作需要**效率或確定性可靠性**。
- **執行模型**：**真實 OS shell 行程**——Claude 在 code execution 環境經 bash 跑它（`${CLAUDE_SKILL_DIR}` 引用），有完整檔案系統/shell 存取。
- **context 行為**：「runs them via bash and receives **only the output**（the script code itself never enters context）」——官方目錄樹直接標註 `helper.py (utility script - executed, not loaded)` vs `reference.md (loaded when needed)`。比讓 Claude 即時生成等價 code 省 token 得多。
- **分工定位**：「The bundled script **does the work** while Claude **handles orchestration**」——Claude 把回合花在「組合與決策」，boilerplate 交給 script。

## 2. Dynamic Workflows——官方定位（驗證 3-0 ×4 組）

- **本質**：Claude 動態撰寫的 JS 腳本，由**專屬 runtime 在隔離環境背景執行**——不是 shell 行程、不是通用直譯器，是帶 `agent()` 等協調原語的編排 harness。
- **設計意圖**：確定性多 agent 編排——扇出數十到數百個各自獨立 context 的 subagent（上限 1,000/run），內建對抗驗證，正面對抗三個失效模式：**agentic laziness、自我偏好偏誤、goal drift**。
- **關鍵能力**：腳本可決定每個 subagent 的 model 與是否 worktree 隔離（worktree 細節僅 harness blog 載明，docs 只復述 model-routing）。
- **檔案存取**：「**No direct filesystem or shell access from the workflow itself** — Agents read, write, and run commands. The script coordinates the agents」。

## 3. 執行模型對比（核心差異表）

| 維度 | skill `scripts/` | `.claude/workflows/` 腳本 |
|---|---|---|
| 執行者 | OS shell（bash/pwsh 行程） | CC 內建 workflow runtime（隔離 JS 環境） |
| 檔案/shell 存取 | **有**（直接） | **無**（只能透過派出的 agent） |
| 誰做工 | script 本身 | 被 spawn 的 subagent 群 |
| 誰持有 plan | Claude（逐回合編排，結果進 context） | 腳本（迴圈/分支/中間結果在 script 變數） |
| context 成本 | 只有輸出進 context | 只有最終答案進 context |
| 觸發 | agent 用 Bash 跑 | Workflow tool（具名 registry 掃 `.claude/workflows/` / scriptPath） |
| 適用 | 重複的確定性邏輯 | 「needs more agents than one conversation can coordinate」 |

## 4. 打包/散佈（含對先前口頭結論的修正）

- **plugin 支援範圍**（plugins-reference manifest schema 全列舉）：skills / commands / agents / hooks / mcpServers / outputStyles / lspServers / experimental.{themes, monitors} / userConfig / channels / dependencies——**無 workflows 欄位**，全頁 grep 'workflow' 零命中。未識別欄位被「忽略而非報錯」→ 嚴格說是「不被識別為可載入 component」。
- **skill + scripts/ 是正式可打包資產**：plugins-reference 的 skill 結構樹明列 `scripts/ (optional)`。
- **⭐ 官方組合模式（修正本專案 2026-06-07 對話中的口頭結論）**：harness blog 明文——「To share them via a skill, **put your JavaScript workflow files in the skill folder and reference them in the SKILL.md**」。即 workflow 檔**可以**放 skill 資料夾隨 skill/plugin 散佈；但官方補充建議「think of the workflows in the skill as a **template** instead of a script」（當範本參考，非保證具名觸發）。先前口頭說「只能請使用者手動複製進 .claude/workflows/」過於保守——官方有背書的 skill 夾帶散佈法，惟 registry 觸發行為未明（見 §6 開放問題 1）。

## 5. 對 Project_01 的對照結論

- **現行架構已符合官方判準**：`memory-health.ps1`（確定性檢查 → skill scripts/）、`clean-pi-pycache.ps1`（同）、`skill-edd-regression.js`（多 agent 編排 → .claude/workflows/）各歸其位，無需搬移。
- **EDD harness 留在 `.claude/workflows/` 仍是對的**：本地具名觸發是 registry 硬功能；skill 夾帶法的官方語境是「跨專案散佈」且僅當 template——若日後要把 harness 包成 plugin，路徑＝「.js 副本放 skill 內 + SKILL.md 註明 template 性質」，本地版仍以 `.claude/workflows/` 為運行權威。
- **判準一句話可進 `workflow-authoring.md`**（候選，待定奪）：「確定性邏輯歸 scripts/（shell 做工），多 agent plan 歸 workflows/（runtime 持 plan）」。

## 6. 誠實標註（caveats + 開放問題 + 否決紀錄）

**Caveats**（綜整者原註，照錄要點）：
1. dynamic workflows 為 research preview（v2.1.154+），介面/散佈方式可能變動。
2. 「plugin 不含 workflows」是 negative claim——已對 manifest schema + 檔案位置 reference + 全頁 grep 三重驗證，但未識別欄位是被忽略而非禁止。
3. worktree-per-subagent 僅單一 primary 來源（harness blog）。
4. 「skill 路由」「heavy/deterministic logic」等措辭屬綜整詮釋，官方原語是「efficiency / deterministic reliability」「capabilities beyond a single prompt」。

**開放問題**（官方未明確回答）：
1. plugin 安裝路徑下的 skill 內 .js workflow，會被 runtime registry 識別可具名觸發，還是僅當 template 由 Claude 重新生成？
2. workflow 的隔離 JS 環境能否間接呼叫 skill bundled script（「workflow 編排 + script 確定性工具」同 run 串接）？——目前已知解法：由被派的 agent 用 Bash 跑 script（本專案 EDD 即此模式）。
3. 「少量分支但不需數十 agent」灰色地帶有無量化門檻？
4. API 版 skill（無網路/runtime 限制）與 CC 版 script 執行能力差異對可攜性的影響。

**否決紀錄（疫苗）**：
- ✗（1-2）「script 應提供可執行解法而非復述預設行為」——方向合理但無足夠 primary 支撐為官方判準，勿引為官方說法。
- ✗（0-3）「plugin 恰好打包五種 component」——實為 11+ 欄位（含 outputStyles/lspServers/themes/monitors 等），舊五分類說法已過時。

---

## 7. 來源表（抓取日期 2026-06-07；P=primary）

| 來源 | 品質 |
|---|---|
| anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | P |
| claude.com/blog/lessons-from-building-claude-code-how-we-use-skills | P |
| platform.claude.com/docs/en/agents-and-tools/agent-skills/overview | P |
| claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code | P |
| claude.com/blog/introducing-dynamic-workflows-in-claude-code | P |
| code.claude.com/docs/en/skills ｜ /workflows ｜ /plugins ｜ /plugins-reference | P ×4 |
| github.com/anthropics/claude-code plugins/README ｜ anthropics/skills（skill-creator、web-artifacts-builder/scripts） | P ×3 |
| infoq.com（dynamic workflows 報導） | 二手 |
| alexop.dev / mindstudio.ai ×2 / kenhuangus.substack / leehanchung.github.io / claudefa.st ×2 / firecrawl.dev / composio.dev | 社群 blog（僅交叉印證，主張皆以 P 來源為準） |

> 統計：6 角度、22 來源、94 claims 抽取、25 條驗證（23 確認 / 2 否決）、綜整成 11 條發現；105 agent、~294 萬 subagent tokens。
