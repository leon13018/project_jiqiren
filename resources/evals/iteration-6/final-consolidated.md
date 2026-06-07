# iteration-6 — 2026-06-07 候選 4-7 落實驗證（pass@k + baseline 對照首跑）

> 背景：逆向採納候選 4-7 落實（spec `reverse_adoption_4to7_2026-06-07_spec.md`，commit `01684bf`）+ s2 斷言 3 改寫（weak_asserts 首發訊號處置，`46da47a`）。

## 兩輪驗證

1. **k3-s2-revalidation**（wf_05285289）：k=3 × 改寫後 s2——三 trial 全 3/3、聚合結構（pass_rate / majority_pass）正確、改寫斷言重畢業。pass@k 機制驗證通過。
2. **baseline-s9**（wf_62e4f48c）：s9 + bare 對照——**with-skill 3/3 vs bare 0/3，skill 增益 +3 條實證**（bare 只能靠常識摸方向，命不中 memory-health.ps1 路徑 / 主 checkout 約束 / ledger 疫苗協議）。baseline 機制驗證通過，s9 是 skill 不可省的鐵證。

## weak_asserts 累積訊號（待人定奪，未處置）

- **s2**：改寫後斷言 3 仍偏弱（題幹已限定單檔，path-prefix 才有鑑別力）；斷言 2「不需走 SDD」對純文件恆真（建議改問「SDD 觸發精確檔案集合為何」）；建議新增「research 筆記 + code_map 同改」複合場景考夾帶判斷
- **s9**：斷言 1 查存在不查六步順序；斷言 3 通用批准與專案 ledger 綁一條（建議拆兩條）+ 未考「升層後不留雙權威」硬邊界

## 結論

候選 4-7 全部落實並驗證：pass@k（k 預設 1 零成本）、baseline 對照（場景級 opt-in）、claudemd-health.ps1（真實 repo 8 份全綠）、aggregate-edd.ps1（iteration-5 實資料 4 收 4 跳、場景 3 的 1/2 跨輪率正確呈現）。
