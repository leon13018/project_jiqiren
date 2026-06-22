# snapshots/ — 架構圖自檢截圖暫存

畫報告系統架構圖時，用 Chromium（Playwright MCP）截圖**自我確認版面**、以及 `System.Drawing` **裁切放大**逐項核對的圖片，一律丟進這個資料夾。

- **非交付物**：正式圖檔（`NN-topic.{png,svg}`）交付進 `../architecture/diagrams/`，不在此。
- **gitignore**：本資料夾內容全部不進版控（規則 `resources/snapshots/*` + `!README.md`），只追蹤這份 README 讓資料夾常駐。
- **製作工作流**：見 skill `architecture-diagram`（`reference/render-pipeline.md` §4–§6 自檢 / 裁切 / 匯出配方）。
