# Visual system — 已移交 report-design-system（本檔僅為指標）

> **architecture-diagram 已改宗淺色蠟筆風。** 原本這裡的深色霓虹 OKLCH 毛玻璃視覺系統（theme / 字體 / 色彩 / 簽名元素 / 視覺 gotchas）**已退場**；現在的視覺風格權威全在 **`report-design-system` skill**。

## 去哪讀（全在 report-design-system skill）

| 要什麼 | 讀 |
|---|---|
| 淺色蠟筆視覺系統（版面慣例 / 蠟筆濾鏡 / Rough.js 填色 / 塗鴉標題 / 強度旋鈕） | `../../report-design-system/reference/diagram-crayon.md` |
| 色票（§2）/ 字型（§3） | `../../report-design-system/reference/report-pdf.md` |
| 視覺 critical gotchas + 渲染 / 截圖 / SVG | `../../report-design-system/reference/render-and-qa.md` |
| 三張定版對照基準（gold standard，做圖前對照） | `../../report-design-system/assets/benchmarks/` |

## 仍屬本 skill 的東西

- **產線 render 機制**（DPR 匯出 / bbox dump / SVG 組裝 / 平行序列化）→ [render-pipeline.md](render-pipeline.md)。
- **製作流程**（讀實際碼鐵則 / SDD / opus 實作 / 3-QA-panel）→ `SKILL.md`。
- frontend-design 落地原則（grounded in subject / structure is information / spend boldness in one place）仍適用，但**只花在 layout + 主角元素，風格別重訂**（風格已釘死於 report-design-system）。

## legacy

舊深色霓虹 theme `resources/architecture/diagrams/theme/{tokens.css,diagram.css}` 與深色圖 ①–⑤ 保留為 legacy（供舊交付 render），本 skill 不再產出深色。
