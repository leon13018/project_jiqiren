# Changelog — 2026-06-23 期末報告 PDF 製作 + 系統圖 6K 升級弧

> 不改產品碼；全在 `resources/report/` + `resources/architecture/diagrams/`。延續上一期「畫圖收官 → 下一階段做報告 PDF」。產出物＝交付用的高保真 PDF（gitignored `out/`，已另存桌面交件夾）。

## 一、報告 PDF 內容定版（`report.html` + `tokens.css`）

承接 compact 前的 35 頁草稿，本弧逐頁精修到定版（使用者逐項像素級驗收）：

- **第 2 頁目錄**：標題「目錄」→「**內容**」；移除章名前的 1–9 編號；**加 PDF 內部跳轉超連結**（9 章分隔頁 `id=ch1..ch9` + 參考資料 `id=refs`，目錄列補 `href`；已解壓 PDF 驗證 10 個 `/Subtype/Link` + `/Names`/`/Dests` 命名目標樹）；新增「介紹 → 3」連結列；字級 13→12pt、行距收緊、頁碼欄 `.toc max-width:5in`。
- **第 3 頁介紹**：「摘要」→「**介紹**」；內容**擴充為四段**（應用情境引言 + 系統技術總覽 + **跨機型適應力**[因邏輯與硬體回呼注入解耦，小至桌上型 TonyPi、大至等身服務型人形機器人皆適用] + 報告導讀）。
- **第 28 頁 webui 畫面流大改版**：2×3 截圖牆 → **蛇形 1→6 流程**（第 2 列左右反轉使箭頭一筆連貫）+ **粗蠟筆塗鴉箭頭**（block-arrow `<symbol>` + `#crayonArrow` 手抖+柔顆粒，歪歪粉粉但清楚，每箭頭帶流程說明）+ **圖說高透明手繪蠟筆框**（`::before`+`#crayonFrame`，編號徽章經數輪後**移除**）+ **奶油米色方格背景**（原樣複製基準 `03-web-phase` 的 `#faf9f5` 底 + `#ece6da` 30px 格）+ 截圖**無外框**直接置於方格紙 + 移除 Chapter 標誌、頁面垂直置中。中途試過彩色框/雲朵框/Rough hachure 填充，皆 reset，最終定為「無框截圖 + 圖說小框」。
- **第 33 頁未來展望改寫**：神經網路 AEC / 商品影像辨識 / 大型語言模型 / **harness sales agent**（harness 統一編排 LLM 與工具呼叫、防幻覺亂答、為 tool·MCP·CLI 存取外部資料庫設權限稽核邊界）；版位調整結論左欄、未來展望右欄（`break-before:column`）。
- **第 9 頁第 3 章塗鴉**：堆疊三方塊**變細 + 拉開上下間距**（原黏成一團「像大便」），stroke 10→8、gap 10→28；試過三色 OKLCH 後還原單色 `--ivory`。
- **全章 Chapter pill**：字級 8.5→10.5pt（外框尺寸不變、縮 padding + `line-height:1.15` 補償、文字不碰邊）。
- **全報告頁碼（folio）**：位置數輪微調定於距右 .725in / 距底 ≈.41in。

## 二、系統圖 6K 升級（9 張 `.svg` 就地覆寫）

- **動機**：使用者要 4K→更高保真。先釐清 **Chromium print-to-PDF 本來就是向量輸出**（文字/蠟筆線/箭頭/塗鴉皆向量、無限解析度；只有 feTurbulence 濾鏡層被點陣化）。
- **關鍵發現**：`--force-device-scale-factor` 對 **print-to-PDF 完全無效**（1× 與 3× 輸出**位元組數一模一樣**）——它只作用於 screenshot。故提高圖保真的槓桿＝**把圖的原始 HTML 用更高 dsf 重拍 PNG、再換回 SVG 的 base64**。
- **執行**：9 張圖以**舊 `--headless` + `--force-device-scale-factor=3`** 重渲染（①②③⑤⑥⑦⑧⑨ 1960→5880px、④ 2040→6120px ≈ 6K），base64 包回**相同 viewBox** 的 SVG（邏輯尺寸不變、內嵌 PNG 升 3×）。源：01–03 在 `report-design-system/assets/benchmarks/`、04–09 在 `diagrams/`（rough.js+jason8.ttf 同層）。
- **效果**：報告 PDF 內嵌解析度 **240–371ppi → 420–557ppi**；圖檔總量 ~54MB→~92MB（**使用者裁示永久存進 git**）。

## 三、全屏圖頁尺寸統一（純 `report.html` 頁面重構，圖不重算）

數輪逼近最終解：① 統一 14×8.5 contain（留白）→ ② per-aspect 14in 寬填滿 → ③ **定版：所有圖頁＝標準報告頁寬 11in**。
- **8 張非時序圖**：頁面＝**標準 11×8.5**（與封面/內文完全相同）；圖 `object-fit:contain` + 置中、以 11in 寬填滿、上下因比例留白（米底襯邊、不裁切）。
- **時序圖 ④**：**同寬 11in、頁加長 11×13.38**（容直式內容）。
- 結果：**整份報告每頁皆 11in 寬**，除時序圖外連高度都統一 8.5in。

## 四、交付

- 6K PDF（**72MB / 35 頁 / 字型全內嵌向量 Type3 / 含 Unicode 可搜尋**，pdfinfo·pdffonts·pdfimages 驗證）`SendUserFile` 傳出，並複製到 `Desktop\人形機器人期末作業\humanoid-sales-robot-final-report-6K.pdf`。
- `myProgram/` 另複製一份到同交件夾，**排除全部 CLAUDE.md（9）與 .claude/（9）**（只動副本、原專案未碰；副本 50 個 .py 完整）。
- `out/` 清掉舊 `report.pdf` 與 4K 檔（gitignored、非版控）。

## Commits（皆已 push 到 `main`、Pi 同步）

`b334166` 目錄改版 · `d4fd150` 第28頁畫面流+頁碼 · `b45559d` 介紹擴充/未來展望/pill/第9頁塗鴉 · `00c5d44` 9圖重算6K+全屏頁統一 · `3e2b86c` 全屏頁統一14in（後修） · `e1e3bbf` 改為11in同封面寬 · `ff07d4b` 8張非時序圖頁高回標準8.5。

## 待辦（未完）

- **P1 攤位全景 / P4 demo 互動**兩張實體照片（第 31 頁 `.photo-ph` 佔位待填）。
- `diagrams/` 獨立 `.png` 交付檔仍是 2×（報告只用 `.svg`，未同步升 6K；要的話可補，會再 +~70MB）。
- 交件副本 `myProgram/` 內仍含 `__pycache__/`、`tts_cache/`（使用者只要求排除 CLAUDE.md/.claude）。
