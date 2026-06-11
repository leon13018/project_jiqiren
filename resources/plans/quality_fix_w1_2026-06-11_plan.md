# quality_fix_w1 實作計畫（plan — HOW）

> **執行者**：sales-coder（SDD 階段 2）。對應 spec：`resources/specs/quality_fix_w1_2026-06-11_spec.md`（WHAT，行為規約與等價論證以 spec 為準）。
> 純重構 TDD 規約：**綠 → 改 → 綠 → commit**；每 task 一個 commit；任一步 pytest 不是 460 passed 即停下回報。

**Goal**：消除 #1（C-2 checkout 分流重複）/ #3（tts play 錯誤處理重複）/ #4（at-cap 文案重複），行為零改變。

**改檔**：`myProgram/sales/states/l2_l3_dialog.py`、`myProgram/tts.py`、`myProgram/sales/constants/products.py`、`myProgram/sales/states/_l2_l3_qty_followup.py`。測試零修改。

---

## Task 0：基線驗證

- [ ] **Step 0.1：跑全套測試確認綠基線**

執行：`python -m pytest tests/sales/`
預期：`460 passed`。不是 → 停下回報（基線即壞，不開工）。

---

## Task 1（#1）：`_c2_checkout_via_confirm` 委派 `checkout_flow`

**Files**：Modify `myProgram/sales/states/l2_l3_dialog.py`（`_c2_checkout_via_confirm`，約 647-669 行）

- [ ] **Step 1.1：Read worktree 內 `l2_l3_dialog.py` 目標段**（Edit 前必 Read 該絕對路徑）

- [ ] **Step 1.2：整個 method 替換**

舊（含 docstring 全段）：

```python
    def _c2_checkout_via_confirm(self) -> tuple:
        """C-2 結賬 path（合流：CHECKOUT keyword + silent timeout 都走這裡）。

        經 _dialog_checkout_confirm 確認明細 → "yes" 進 L4；非 yes 清 cart + 重入 dialog 主迴圈。

        對齊既有 L3 C-1 結帳 path（_dispatch_inner / checkout_flow 結帳分支）— 共用 confirm 子狀態。

        2026-05-29 反轉：silent timeout 不再走 _c2_direct_checkout 直接 L4,
        合流到此函數經 confirm（與 CHECKOUT keyword path 完全一致）。新文案
        「{seconds} 秒後自動結賬」字面 promise 寬鬆解讀為「自動啟動結賬流程」
        （含 confirm 子狀態保護顧客錢包）。
        """
        result = _dialog_checkout_confirm(io=self.io, cart=self.cart)
        if result == "yes":
            self.io.speak(L3_C1_CHECKOUT_GO)
            self.io.do_action(ACTION_L3_CHECKOUT_GO)
            return ("L4", 0)
        if result == "cancel_to_l1":
            # 2026-05-30 加：cancel_confirm YES → 直退 L1（不重入 main loop）
            return self.exit_a()
        # 非 yes → 清 cart + speak 通知 + 重入 dialog 主迴圈
        _handle_checkout_confirm_result(result, self.cart, self.io)
        return self.main_loop()
```

新：

```python
    def _c2_checkout_via_confirm(self) -> tuple:
        """C-2 結賬 path（合流：CHECKOUT keyword + silent timeout 都走這裡）。

        分流本體共用 checkout_flow（confirm → "yes" 進 L4 / "cancel_to_l1" 直退 L1 /
        其他清 cart + 通知）；與主迴圈結帳 path 唯一差異 = 非 yes 後重入 main_loop
        （主迴圈語境為 continue 當輪迴圈）。

        2026-05-29 反轉：silent timeout 不再走 _c2_direct_checkout 直接 L4,
        合流到此函數經 confirm（與 CHECKOUT keyword path 完全一致）。新文案
        「{seconds} 秒後自動結賬」字面 promise 寬鬆解讀為「自動啟動結賬流程」
        （含 confirm 子狀態保護顧客錢包）。
        """
        result = self.checkout_flow()
        if result is not None:
            return result
        return self.main_loop()
```

- [ ] **Step 1.3：跑全套測試**

執行：`python -m pytest tests/sales/`
預期：`460 passed`

- [ ] **Step 1.4：commit + branch 自驗**

```bash
git add myProgram/sales/states/l2_l3_dialog.py
git commit -m "refactor(sales): dedupe C-2 checkout confirm flow via checkout_flow"
git branch --contains HEAD
```

commit body：說明三路分流原雙份（checkout_flow / _c2_checkout_via_confirm）收斂為委派、行為零改變，附 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。
`git branch --contains HEAD` 須含 `worktree-quality-fix-w1`；顯示 `main` = Gotcha M，停下回報。

---

## Task 2（#3）：tts `_process` play 階段 try/except/finally + `_print_failure` helper

**Files**：Modify `myProgram/tts.py`

- [ ] **Step 2.1：Read worktree 內 `tts.py`**

- [ ] **Step 2.2：在 `_synthesize` 之後、`class TtsWorker` 之前插入 helper**

```python
def _print_failure(stage: str, detail_lines: list) -> None:
    """TTS 失敗訊息統一印製（synth / play 兩階段共用；字面與舊版逐行一致）。

    detail_lines 每行自帶「key = value」格式，由 caller 依舊版順序排列
    （play FileNotFoundError 的 text 在 hint 前；CalledProcessError 的 cmd 在 text 前）。
    """
    print(f"[語音] ⚠️ TTS 失敗（階段={stage}）")
    for line in detail_lines:
        print(f"[語音]   {line}")
    print(f"[語音] 此字略過,繼續下一字")
```

- [ ] **Step 2.3：`_process` 階段 1（synth）except 區塊換 helper**

舊：

```python
        except Exception as e:
            # edge_tts 可能 raise NoAudioReceived / WebSocketException / asyncio 相關錯
            # 不確定具體類型 → 統一 catch Exception，但訊息要詳細
            print(f"[語音] ⚠️ TTS 失敗（階段=synth）")
            print(f"[語音]   exception = {type(e).__name__}: {e!r}")
            print(f"[語音]   text      = {text!r}")
            print(f"[語音] 此字略過,繼續下一字")
            return
```

新：

```python
        except Exception as e:
            # edge_tts 可能 raise NoAudioReceived / WebSocketException / asyncio 相關錯
            # 不確定具體類型 → 統一 catch Exception，但訊息要詳細
            _print_failure("synth", [
                f"exception = {type(e).__name__}: {e!r}",
                f"text      = {text!r}",
            ])
            return
```

- [ ] **Step 2.4：`_process` 階段 2（play）整段替換**（從「`# 階段 2：播放 mp3`」註解起、到 method 結尾 `time.sleep(ALSA_DRAIN_SEC)` 止）

新版全段（既有註解原樣保留、印出字面不變）：

```python
        # 階段 2：播放 mp3（subprocess.Popen → 保留 reference 給 shutdown 用）
        # 對比 S2 同步版用 subprocess.run：S4 改 Popen + wait 兩段是為了讓
        # shutdown() 可在播放期間呼叫 _proc.terminate()。
        #
        # stdin=DEVNULL（commit f7dab09 加,S2 Pi 實機踩坑）：mpg123 預設讀父
        # 程序 stdin 接收 control characters（q/s/p/+/- 等）。不設 DEVNULL 時：
        #   1. 播放期間 user 在 dialog 打的字會被 mpg123 偷走 → 無法進
        #      Python input() → 顧客以為打了字結果機器人沒反應
        #   2. user 不小心打到 'q' / 's' → mpg123「Stopped.」+ quit 退出碼非 0
        #      → CalledProcessError → 整段 dialog flow 中斷
        # mpg123 從 mp3 路徑參數讀資料、不從 stdin 讀資料 → DEVNULL 不影響播放。
        #
        # finally 統一清 _proc（取代原 3 except + 成功路徑共 4 處重複）：
        # 成功 = try 正常結束 → finally 清 → drain；失敗 = except 印完 → finally 清
        # → return 生效 — 兩種時序皆與舊版「印完才清 / 清完才 drain」一致。
        try:
            with self._lock:
                # 短臨界區：spawn + 存 ref，不包 wait（避免 shutdown 拿不到 lock）
                self._proc = subprocess.Popen(
                    ["mpg123", "-q", TMP_MP3],
                    stdin=subprocess.DEVNULL,
                )
            # 等播完（不持 lock — shutdown 可在此期間 terminate）。terminate
            # 觸發時 wait 返回非 0 returncode（Linux 上 SIGTERM 是 -15）。
            returncode = self._proc.wait()
            if returncode != 0:
                # check=True 等效手寫：模擬 subprocess.CalledProcessError 行為。
                # 走 except 分支印 noisy 訊息（shutdown 觸發的 SIGTERM 也會走這
                # path，returncode 負值代表被 signal 中斷 — 是 expected exit
                # 但仍印訊息，方便 SSH log 看到「程式退出時殺掉了播放中的 X」）。
                raise subprocess.CalledProcessError(
                    returncode=returncode,
                    cmd=["mpg123", "-q", TMP_MP3],
                )
        except FileNotFoundError as e:
            # mpg123 binary 不存在（Pi 未 apt install mpg123）
            _print_failure("play", [
                f"exception = FileNotFoundError: {e!r}",
                f"text      = {text!r}",
                f"hint      = 請在 Pi 上執行 `sudo apt install mpg123`",
            ])
            return
        except subprocess.CalledProcessError as e:
            # mpg123 退出碼非 0（檔案損毀 / 音訊裝置忙 / shutdown SIGTERM 等）
            _print_failure("play", [
                f"exception = subprocess.CalledProcessError: returncode={e.returncode}",
                f"cmd       = {e.cmd}",
                f"text      = {text!r}",
            ])
            return
        except Exception as e:
            # 兜底 — 不明錯誤也要詳細印
            _print_failure("play", [
                f"exception = {type(e).__name__}: {e!r}",
                f"text      = {text!r}",
            ])
            return
        finally:
            with self._lock:
                self._proc = None

        # 播放成功（returncode==0）：drain ALSA
        # 給 ALSA buffer 完成尾巴音訊播放的時間,避免下一個 speak() 立刻啟動
        # 新 mpg123 沖掉舊 buffer（症狀：「付款成功」尾巴被截）。失敗 path
        # 不到這裡因 mpg123 沒真播完 = 無 buffer 殘留 = 不需 drain。
        time.sleep(ALSA_DRAIN_SEC)
```

`_process` docstring 內「各失敗分支用 return 結束」說明仍適用，不動。

- [ ] **Step 2.5：跑全套測試**

執行：`python -m pytest tests/sales/`
預期：`460 passed`（`test_tts_worker.py` 全綠——`_pending` 計數走基底 `_loop` try/finally，本改動不碰）

- [ ] **Step 2.6：commit + branch 自驗**

```bash
git add myProgram/tts.py
git commit -m "refactor(tts): consolidate play-stage failure handling into try/finally + helper"
git branch --contains HEAD
```

commit body：說明錯誤印製 ×4 收斂為 `_print_failure`、`_proc` 清理 ×4 收斂為 finally、印出字面與時序不變，附 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。

---

## Task 3（#4）：at-cap 文案抽 `AT_CAP_NOTICE_TEMPLATE`

**Files**：Modify `myProgram/sales/constants/products.py`、`myProgram/sales/states/_l2_l3_qty_followup.py`

- [ ] **Step 3.1：Read worktree 內兩檔**

- [ ] **Step 3.2：`products.py` 加常數**

`__all__` 補 `"AT_CAP_NOTICE_TEMPLATE"`，檔尾（`QTY_CLARIFY_TEMPLATE` 之後）加：

```python
# L2 / L3 加單時 cart 已達單筆上限的即時通知（2026-06-11 抽常數；
# 原 inline 於 _l2_l3_qty_followup.py 兩處逐字重複）
AT_CAP_NOTICE_TEMPLATE: str = "{product}已經點到單筆上限 {max_qty} {unit}，無法再加"
```

- [ ] **Step 3.3：`_l2_l3_qty_followup.py` import 補 + 兩處替換**

import 區（`from myProgram.sales.constants import (...)` 清單內）補 `AT_CAP_NOTICE_TEMPLATE,`。

兩處（`resolve_and_add_products` Pass 1 的 `remaining <= 0` 分支、`_qty_follow_up_sub_loop` 的 `remaining <= 0` 分支）。**行內容相同、縮排不同**（前者 12 空格、後者 16 空格），各依所在區塊縮排替換；前後註解不動：

舊（去縮排後內容）：

```python
io.speak(f"{product}已經點到單筆上限 {MAX_QTY_PER_ITEM} {unit}，無法再加")
```

新（去縮排後內容）：

```python
io.speak(AT_CAP_NOTICE_TEMPLATE.format(product=product, max_qty=MAX_QTY_PER_ITEM, unit=unit))
```

- [ ] **Step 3.4：跑全套測試**

執行：`python -m pytest tests/sales/`
預期：`460 passed`（`test_states.py:6098/6230` substring assert 字面相同仍綠）

- [ ] **Step 3.5：commit + branch 自驗**

```bash
git add myProgram/sales/constants/products.py myProgram/sales/states/_l2_l3_qty_followup.py
git commit -m "refactor(sales): extract AT_CAP_NOTICE_TEMPLATE to constants"
git branch --contains HEAD
```

commit body：說明 inline 文案 ×2 收斂進 constants（字面不變），附 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。

---

## 完成回報

依 sales-coder 規約回 4-status + 各 commit SHA + TaskList 摘要 + pytest 末行輸出。
