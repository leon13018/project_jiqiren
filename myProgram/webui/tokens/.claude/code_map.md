# myProgram/webui/tokens/ — code_map（本層索引）

> 顆粒：細。Glaze Liquid Glass 設計語彙——6 個 CSS 變數檔（`:root` custom properties）。`index.html` 逐檔 link、`app.js`/`app.css` 以 `var(--*)` 引用。Apple iOS 視覺體系移植。

## 檔案
- `colors.css` — Apple iOS 系統色（官方 sRGB）+ OKLCH 衍生品牌色調；深色為主、淺色為輔。
- `typography.css` — Apple iOS 字級體系（光學尺寸：≥20pt 用 Display 切、<20pt 用 Text 切）；定義 `--font-*` 字型堆疊。
- `spacing.css` — 8pt 基準間距 + 圓角（squircle 近似的大 border-radius）。
- `effects.css` — Liquid Glass 材質（backdrop blur+saturation、translucent tint、specular 上緣、ambient shadow、流體漸層；`.glass-*` utility）。
- `motion.css` — spring 緩動、durations、可重用 keyframes（morph / drift / ripple / pop-in）。
- `fonts.css` — **載入**字型（`@import` 從 Google Fonts CDN 取 Inter + Noto Sans TC；自託管 SF Pro 不打包——專利+體積+Pi 用不到）。離線階段改 `@font-face` 指向自託管字型（取代 CDN `@import`）。

## 其他
- `CLAUDE.md` — 本層導引。
- `.claude/code_map.md` — 本檔。
