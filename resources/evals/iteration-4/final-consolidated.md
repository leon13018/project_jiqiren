# Iteration-4（Round 3 全 reference 深度去噪）— Consolidated

> Round 3：用 dispatch.md 那套去噪標準（spec §12）過完其餘所有 reference + examples，每 cluster 走 EDD（fresh navigator + grader + comparator）。**全 5 場景零退化、零 load-bearing 誤砍。** baseline = iteration-2/3 狀態；本輪結果存本目錄。

## 去噪力度（user 2026-06-03 校準：只砍真噪音、不為湊數字硬砍）
這些 reference 多半是 round-1/2 已清過的高密度 load-bearing 設計知識（範本/流程/表/Gotcha 解法/領域 know-how），真噪音少。實際只砍：
- **see-also footer**（reference 間非-hub 互指；hub 是 SKILL.md）— 全檔移除
- 與 root CLAUDE.md 重複的 anti-rationalization、重複 pointer
- 日期戳 / commit SHA / episode 敘事 / meta 自述 / 1 段歷史敘事壓縮

**逐字保留**：所有範本、流程圖、行為矩陣、計時數值、Gotcha 解法、canonical 範例、繁簡表、Iron Law、領域 know-how。

## TOC 標準（user 2026-06-03 定案，spec §2.6）
**>30 行的 reference / example 一律開頭加「## 目錄」**。修回 dispatch.md（前一輪去噪誤刪）、補 2 個 examples；其餘 reference 本就有。SKILL.md（router 本身即索引）依 user 決定免目錄。

## 各 cluster 行數變化 + EDD
| cluster | 檔（行數 before→after） | EDD | 結果 |
|---|---|---|---|
| 1 SDD/reviewer | sdd 247→242；examples +TOC | S1 opus+sonnet | pass，零退化 |
| 2 process | worktree 101→97、standard-workflow 80→76、pi-and-structure 102→98 | S2 | pass，零退化 |
| 3 threading | vendor 65→61、threading-paths 117→113、incremental 90→84 | S3 | pass，零退化 |
| 4 sales | sales-dialog-design 152→148、sales-tts-ux 106→102 | S4 | pass，零退化 |
| 5 dormant/conv | bdd-tdd 56（footer slim）；conventions 47 未動 | S5 | pass，零退化 |
| 6 router | SKILL.md 49 未動（無噪音、免 TOC） | （5 場景隱含測 router） | — |
| (dispatch.md) | 前一輪已 −36%；本輪僅修回 TOC | — | — |

reference 本體淨去噪約 −1750 字元（threading −336 / incremental −300 / sales-dialog −251 / sales-tts −238 / bdd −211 / vendor −194 / sdd ~−420 / standard-workflow −131 等）；TOC 還原/補上（dispatch +187、examples +95）屬標準化、非內容增。

## EDD 結論（全場景）
- **S1**（iteration-4/cluster1-s1-result.json）：opus + sonnet 全 pass，sdd 自足、無第 2 跳。
- **S2**（cluster2-s2-result.json）：Gotcha M cherry-pick 鏈 + sync Stop hook 自動 + marker 自我修正全保留，pass。
- **S3/S4/S5**（cluster345-s3s4s5-result.json）：單 queue/sticky/Linux 路徑、C-2 表/L4 雙計時器/cancel-service confirm 秒數/「沒有了」歸結帳、BDD 重啟條件/繁簡表全保留，三場景 pass。
- comparator verdict（合併）：`regression_detected=false`、`all_clusters_self_sufficient=true`、`failed_assertions=[]`、`lost_load_bearing_content=[]`。

grader 標的 weak_assertions 皆為驗證面方法論觀察（assertion 偏 recall / forced_second_hop 自報 / __pycache__ 屬跨列路由非 threading 內容），非內容退化。

## 結論
Round 3 用統一去噪標準過完全部 reference + examples，EDD 全綠、零誤砍；TOC 標準全面落地。
