# iteration-7 — s12 graduation（清理後 grep 驗證紀律）

2026-06-21。單一 graduation run（`wf_6c9b4a38-acf`），驗收新場景 **s12-cleanup-grep-verify-case** 是否可正式入回歸題庫。

## 結論：PASS，s12 畢業

- 3/3 assertion `pass_rate 1.0`、`overall_pass=true`、**無誤殺**（graduation 判準「可判定 + 不誤殺」皆滿足）。
- grader 證據引 `conventions.md` 新增段（L62-68）+ `sdd.md` Iron Law，非複述 navigator。
- 來源：反思 `grep-case-sensitive-false-clear`（落實 commit `6a9962b`）。

## weak_assert 訊號與處置

grader 標 **assert 1（grep 加 -i / 列大小寫變體）半弱**：只查最終 grep 寫法這個產物，死記「-i」而不懂失敗模式的導航也能 pass；真正鑑別力靠 assert 2（OpenCv 漏網機制）+ assert 3（驗證不可信不得宣告完成）兜底。

**處置：保留三元設計、不改 assert。** assert 1/2/3 是刻意的 action / reason / gate 三元（與既有 s1「判斷必先 EnterWorktree」等場景同設計——product 型 assert 由其餘 assert 兜鑑別）。grader 建議把 assert 1 綁因果，等同複製 assert 2、製造冗餘反更糟。weak 訊號入本結果檔供 `scripts/aggregate-edd.ps1` 跨輪追蹤；若日後同類 product-only assert 反覆被標，再整批檢討。
