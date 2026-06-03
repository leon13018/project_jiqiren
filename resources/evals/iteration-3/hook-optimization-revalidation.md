# Iteration-3 補充 — SubagentStart hook 優化複驗（dispatch-policy navigator）

> 對 `subagent-inject-rules.ps1` 改為「只對 Explore/Plan 注入、其餘放行」+ dispatch.md Step 1/2 同步更新後，派一個 **general-purpose** fresh navigator 跑 dispatch-policy 場景複驗。**全 pass。**

## 改動
- **hook**：原「編碼類完整 / 研究類精簡」分流 → 改為「只對 Explore/Plan（唯一跳過 CLAUDE.md 者）注入繁中+文檔指標最小導航；其餘 agent 原生載入 CLAUDE.md 故直接放行」。刪掉原「完整版」紅線注入段（對會載 CLAUDE.md 的 agent 純屬重複）。
- **dispatch.md Step 1/2**：「不需塞」理由由「SubagentStart hook 注入」改為「sales-coder/general-purpose 原生載入 CLAUDE.md」；Step 2「靠 hook 注入」改為「紅線靠 CLAUDE.md、karpathy 靠 prompt」。

## hook 行為直測（stdin）
| agent_type | 行為 |
|---|---|
| Explore / Plan | 注入「繁中 + 文檔指標」✓ |
| sales-coder / general-purpose / claude-code-guide | 放行靜默 ✓ |

BOM 保留（ef bb bf）、繁中無亂碼。

## 真實複驗（general-purpose navigator，已無 hook 注入）
**最關鍵發現 — skill_discovery**：navigator 回報它是**從原生載入的 root CLAUDE.md（第 29-31 行「做任何實作性工作前載入 project-01-workflow skill」）**得知要載入 skill 的，**不是靠 hook 注入**。→ 證明拿掉 hook 注入無害：CLAUDE.md 原生載入本就指向 skill，skill discovery 不依賴 hook。

- references_read：CLAUDE.md → SKILL.md → dispatch.md + sdd.md + worktree.md（正確路由、無被迫二跳）
- 7/7 assertion 全中：sales-coder / opus 不必傳 / Wave 6 招 / 派發前 4 步 + ⛔ 越權收尾 + branch --contains 防 Gotcha M / Wave 大小判斷 / CLAUDE.md 事實答對 / dispatch.md 自足
- claude_md_fact 答對：sales-coder 原生載入 CLAUDE.md、紅線本就看得到不必餵、只 Explore/Plan 跳過、要餵的是本對話特有任務 context

## 結論
hook 優化（只補 Explore/Plan）+ dispatch.md 文字更新，經直測 + fresh navigator 複驗**無退化**；且實證「移除對 CLAUDE.md-loading agent 的注入後，skill discovery 仍經 CLAUDE.md 原生指引正常運作」。
