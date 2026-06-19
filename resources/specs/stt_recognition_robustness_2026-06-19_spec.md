# STT 辨識 robustness（demo-級可靠）— SDD spec

**日期：** 2026-06-19
**類型：** 辨識 robustness（`myProgram/stt.py`）
**裁定：** 使用者 2026-06-19 選「demo-級可靠（安全增量）」；元件 3（結構暖機修 onset clip）**不做**（輕量版救不回被切字頭，demo-級靠講話習慣避開；結構暖機屬高風險「真自然對話」路線）。

## 背景（Pi 2026-06-19 診斷）
持久連線 + 移除 Finalize 後，全流程通、無 zombie timeout。殘留辨識品質：偶發 `speech_final=True` **空白**（文字在 interim、定稿空）→ 我們只認 speech_final 帶文字才注入 → 整輪漏字（如第 3 輪只抓到「五張」）。根因：(a) Deepgram 偶發空定稿；(b) 中途停頓 >300ms 被 endpointing 判定講完 → 拆句。

## 元件 1 — 轉錄 last-non-empty fallback（`_receive_loop`，核心）
追蹤本句「最後一個非空 transcript」；`speech_final` 時 emit「它自己的文字 **或**（空則）最後那個非空 interim」。空定稿不再漏字。

- `__init__` 加欄位（`self._armed_at = 0.0` 附近）：
  ```python
          self._last_nonempty = ""             # 本句最後非空 transcript（空 speech_final 的 fallback）
  ```
- `_receive_loop` 內層 try 的 `data = json.loads(msg)` 之後（現 235-255）改為：
  ```python
                    data = json.loads(msg)
                    _typ = data.get("type")
                    if _typ != "Results":
                        if _typ:
                            _timing(f"Deepgram {_typ}")
                        continue
                    speech_final = data.get("speech_final")
                    alts = data.get("channel", {}).get("alternatives", [])
                    seg = alts[0].get("transcript", "") if alts else ""
                    # 診斷埋點（env-gated）：印每則 Results（含 interim）
                    _timing(f"Deepgram Results final={speech_final} cap={self._capturing} '{seg}'")
                    if not self._capturing:
                        self._last_nonempty = ""   # 跨輪 / 收音窗外：清追蹤，不洩漏到下一輪
                        continue
                    if seg:
                        self._last_nonempty = seg  # 追蹤最後非空（interim 會 refine 到最佳）
                    if speech_final:
                        # 空白 speech_final（Deepgram 偶發定稿空、文字在 interim）→ 退用最後非空
                        best = seg or self._last_nonempty
                        self._last_nonempty = ""   # utterance 邊界 reset
                        text = _normalize_transcript(best)
                        if text:
                            print(f"[語音辨識] {text}")
                            _timing(f"開麥後 {time.monotonic() - self._armed_at:.2f}s 出辨識結果")
                            self._sink(text)
  ```
  （取代原本「先 `if not Results or not speech_final: continue` 再抽 text」的結構；診斷埋點併入、語意不變只是合流。）
- `_receive_loop` docstring 補一句：speech_final 空白時退用最後非空 interim。
- **執行緒安全**：`_last_nonempty` 只被 receiver thread 觸碰（arm/disarm 不碰）→ 無跨執行緒 race。

## 元件 2 — endpointing 預設 300 → 450（減少拆句）
中途小停頓不被誤判「講完」→ 少觸發空定稿 / 拆句。代價：每句講完反應慢 ~150ms（一口氣講幾乎無感）。env 旋鈕保留。

- 現 57 行 `_ENDPOINTING_MS = int(os.environ.get("STT_ENDPOINTING_MS", "300"))` → 預設 `"450"`；註解（55-56）同步更新「未設 = 450」。

## 行為規約 / 不變式
- 一口氣講完（單一帶文字 speech_final）→ 行為同現狀（`best = seg`）。
- 只有「空白 speech_final」才觸發 fallback（退用最後非空 interim）。
- `STT_ENDPOINTING_MS` 仍可 env override（Pi A/B）。
- 既有測試相容：帶文字 speech_final → emit；空 transcript / 純標點 → normalize 後空 → 不 emit；非 Results → 略過。

## 測試
- `tests/stt/test_worker.py`：
  - 新增 `test_empty_speech_final_falls_back_to_last_interim`：feed interim 帶 `'紅茶三瓶刮刮樂五張'`（speech_final=False）+ 空白 speech_final（`_results("", True)`）→ 注入 `'紅茶三瓶刮刮樂五張'`。
  - 既有 `test_speech_final_injected_normalized` / `test_interim_empty_and_nonresults_not_injected` / `test_malformed_message_does_not_kill_connection` / `test_diagnostic_logs_interim_when_timing_set` → 續綠。
- `tests/stt/test_keyterm.py`：`test_base_params_preserved` 的 `assert "endpointing=300" in DEEPGRAM_URL` → 改 **`endpointing=450`**（預設變更）。`_build_deepgram_url(300)`/`(200)` 的 builder 測試不動（測的是參數帶入、非預設）。
- `py -3.14 -m pytest tests/ -q`（baseline 674）。
- Pi：`STT_TTS_TIMING=1` 跑多輪 → 確認空定稿輪不再漏字（退用 interim）、中途小停頓不拆句；endpointing 反應速度可接受（不行就 `STT_ENDPOINTING_MS=350` 降）。

## Out of scope
- 元件 3 結構暖機（onset clip）：不做（理由見裁定）。
- 跨多個 speech_final 累積整句（中途長停頓拆成兩輪）：demo-級靠「一口氣」避開，不做。
- 移除診斷埋點：保留（env-gated，無害）。
- endpointing / 對話文案 / arecord / 連線生命週期其他改動：不動。

## Commit
- 明列 `myProgram/stt.py tests/stt/test_worker.py tests/stt/test_keyterm.py`；末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 可分 2 commit（元件1 / 元件2）或合一。
