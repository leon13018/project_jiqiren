# 報告設計系統 — 權威已移入 skill

> **本檔僅為指標。** 報告設計系統（Anthropic 淺色編輯風 + 系統圖手繪蠟筆風）的**權威內容（單一事實來源）已搬入 `report-design-system` skill**，並做成完全自足、可打包帶走的 skill。

## 去哪讀

載入 `report-design-system` skill，依其 router 讀：

- **報告 PDF 設計系統**（色票 / 字型 / 網格 / 元件庫 / 塗鴉 / PDF 配方 / 檔案規劃）
  → `.claude/skills/report-design-system/reference/report-pdf.md`（原 §0–§8、§10）
- **系統圖手繪蠟筆風**（淺色版面 / 蠟筆濾鏡 / Rough.js 填色 / 塗鴉標題 / 強度旋鈕）
  → `.claude/skills/report-design-system/reference/diagram-crayon.md`（原 §9）
- **渲染 / 截圖 / SVG 匯出 / 視覺自檢**
  → `.claude/skills/report-design-system/reference/render-and-qa.md`
- **三張定版對照基準**（圖①②③ HTML+PNG+SVG，gold standard）
  → `.claude/skills/report-design-system/assets/benchmarks/`

## 產出物仍建在這層

報告**產出物**（`report.html` / `tokens.css` / `assets/{fonts,doodles}/` / `out/`）仍規劃建在 `resources/report/`（見 skill `reference/report-pdf.md` §10）；設計**權威**在 skill、產出物在此層。

> 勿在本檔重述設計內容（避免與 skill 漂移）。改設計 → 改 skill 的 `reference/`。
