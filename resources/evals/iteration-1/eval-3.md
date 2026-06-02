# Condensed (iteration-1) transcript — eval 3 (threading cluster), model=opus

> cluster 3 精簡後（vendor 59 / threading 116 / incremental 90）。場景同 baseline eval-3。

## Navigator 回覆（摘要）
STT worker = input_reader 語音版，同構踩雷：
1. 生命週期（沿用 S6 4 教訓）：不主動 unblock blocking 讀（close 會 deadlock）；shutdown 只清 queue、daemon 隨 os._exit(0) 殺；daemon 硬殺對 audio device 副作用要評估；read() latest-wins drain。
2. 阻塞 vs polling（S6 教訓 1/2）：default timeout 別亂設 0.1（polling cadence caller-specific）；阻塞→polling 要 audit「假設靜默=沒事」的狀態機。
3. 單 queue 紀律（incremental §單 queue）：STT 結果丟單一 queue、producer 端不分流；關鍵決策＝STT 與鍵盤共用同一 customer-input queue（禁用「語音/鍵盤模式」旗號分流＝已判定的架構錯）。
4. audio pipeline / asyncio（worker thread 用 asyncio.run 非 get_event_loop）/ subprocess 別 fire-and-forget / **STT 麥克風 vs TTS 喇叭自我回授**（TTS 播放時用 tts 的 _pending/wait_idle 讓 STT 丟棄識別，而非旗號分流）。
5. 流程：屬新 worker + main wire-up 中大改 → 必走 SDD + 派 sales-coder；走 incremental S 系列每步只加一層實機測；Linux 絕對路徑；Windows 無法測 audio。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：threading-paths.md → incremental-rebuild.md → myprogram-vendor.md → sales-tts-ux.md → myProgram/.claude/code_map.md。
- reference→reference：路由表 → threading-paths（主入口）；threading → incremental（單 queue/S 系列/sticky 權威）；threading → vendor（shutdown 對比 + 確認 STT 不涉 vendor）；主動跳 sales-tts-ux（audio/asyncio 同構 + _pending/wait_idle 解回授）。
- 缺漏：**STT 與鍵盤是否共用 queue + STT/TTS 自我回授協調 reference 無現成答案**（只給單 queue 原則）；STT 全被當 roadmap 候選、無已落地設計（以上為同構推演）。
