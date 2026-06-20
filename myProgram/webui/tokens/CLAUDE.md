# myProgram/webui/tokens/ — 本層導引

> **本層結構索引：`.claude/code_map.md`。**

Glaze Liquid Glass 設計語彙：6 個 CSS `:root` 變數檔（colors / typography / spacing / effects / motion / fonts），是前端視覺的單一事實來源。

- **改視覺先動 token、別在 `app.js`/`app.css` 寫死值**：顏色 / 字級 / 間距 / 玻璃效果 / 動效一律調對應 token 檔的 `--*` 變數。
- **OKLCH 相容性**：`colors.css` 用 OKLCH 品牌色 → Chromium<111 不支援（Pi 4 自瀏覽器跑不動主因之一，見 `../CLAUDE.md`）；加新色用 OKLCH 前先顧 demo 渲染環境。
- **字型雙層**：`fonts.css` 只「載入」（`@import` CDN）、`typography.css` 定義「堆疊」（`--font-*`）；離線在地化改 fonts.css 的 `@import` 為 `@font-face`。
- 完整安全紅線 + 繁中規範見 root `CLAUDE.md`，本檔不重述。
