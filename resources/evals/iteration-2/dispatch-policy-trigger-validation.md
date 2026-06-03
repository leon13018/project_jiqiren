# 派發政策觸發驗證（移除全部 effort 提及後），model=opus

> **目的**：user 2026-06-03 要求 skill 內**徹底不提 effort**（連「不指定/繼承 session/不強制 xhigh」這類解釋都刪——系統自有策略）。移除後驗證 dispatch 決策仍正確路由 + 給對模型，且不再有 effort 噪音分散注意。

## 場景
「派一個 subagent 做跨 3 檔 refactor（改函式簽名 + 連動更新呼叫端與既有測試，都在 myProgram/sales/）。subagent_type？模型？注意事項？」

## 結果（全正確）
- **subagent_type = `sales-coder`**（dispatch.md 對應表：編 myProgram/sales/*.py 用自訂 sales-coder，frontmatter 預載 > prompt 塞 summary）。
- **模型 = opus，且不必手動傳**（frontmatter 已內建；跨檔 refactor sonnet 踩坑率高、opus 穩）。
- 完整連動：必走 SDD（spec/plan → approval）→ 派發前 4 步 → **Wave 6 招** → 三段 reviewer（spec-reviewer sonnet / code-quality-reviewer opus）→ Iron Law → `git branch --contains` 防 Gotcha M → 收尾手動 sync。
- Wave 大小判斷正確（一個 sales-coder 一次做完、不一檔一 subagent）。

## effort 驗證（本次重點）
Navigator 明確回報：**「兩份 reference（dispatch.md / sdd.md）+ SKILL.md 都沒有任何要求指定 effort / thinking 等級 / xhigh 的內容；模型維度只談 opus/sonnet/haiku 三選一。因此我的回答也沒有提到要設 effort/xhigh——reference 沒要求，我就沒加。」**

→ 移除有效：skill 不提 effort → navigator 不分心、不臆造 effort 設定，只給乾淨模型選擇。派發路由與規則完整無退化。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：SKILL.md → dispatch.md → sdd.md（兩列平行命中「派 subagent」+「改 myProgram .py 走 SDD」）。
- 無被迫非預期二跳。
