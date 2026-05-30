"""L3 文字常數（P8 拆分自 constants.py）。

包含 L3（加單 / 結帳確認）對話層的所有字串常數。
注意：DIALOG_VAGUE_BUY_REASK 已於 2026-05-26 Wave 6 移至 constants/shared.py（跨層共用）。
"""

__all__ = [
    "L3_ENTRY_PROMPT",
    "L2_TO_L3_TRANSITION",
    "L3_REJECT_THANKS",
    "L3_B1_CLARIFY",
    "L3_REASK",
    "L3_C1_CHECKOUT_GO",
    "L3_UNCLEAR_FINAL_PROMPT",
    "L3_CHECKOUT_CONFIRM_TEMPLATE",
    "L3_CHECKOUT_REJECT_CLEAR_NOTICE",
    "L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE",
    "L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE",
    "L3_C2_WARNING_TEMPLATE",
    "L3_C2_CONTINUE_ACK",
    "L3_CANCEL_DECLINED_RESUME",
]

# ============================================================
# L3 文字常數
# ============================================================

# L3 進入時詢問語音（詢問額外需求）
L3_ENTRY_PROMPT: str = "請問還有額外需要購買的嗎？"

# L2→L3 加單成功 transition 的合成 voice（短逗號連貫，TTS 中間不斷）。
# 取代原本兩條連續 speak(L2_C_ADDED) + speak(L3_ENTRY_PROMPT) 模式：
# S4 非阻塞 worker 兩條間有「synth + ALSA drain 0.3s」停頓，合成一條 → 一次 synth
# + 自然句內逗號短停頓，使用者實機 demo 反饋更流暢。僅用於 cart 從空→非空 transition；
# 其他 path（cart 一進來就非空的 entry / L3 沉默 reask）仍用獨立的 L3_ENTRY_PROMPT。
L2_TO_L3_TRANSITION: str = "好的，已加入購物車，請問還有額外需要購買的嗎？"

# L3 鏈路 A 拒絕語音（整單作廢）
L3_REJECT_THANKS: str = "好的，取消這次購物，謝謝光臨"

# L3 鏈路 B-1 無法判斷語音（含「還要」措辭）
L3_B1_CLARIFY: str = "不好意思我聽不太懂，請問還要買什麼呢？或者您想聯繫客服？"

# L3 鏈路 B-3 加單後重問語音 / B-4 沉默 timeout 後重問語音
L3_REASK: str = "請問還需要什麼東西嗎？"

# L3 鏈路 C-1 結帳語音
L3_C1_CHECKOUT_GO: str = "好的，為您結帳"

# L3 鏈路 B-1 累積 UNCLEAR_MAX 次後的「最終確認」子狀態提示語音（2026-05-25 加）
# 仿 L4 D 最終確認；給 6s 選 1=取消（清 cart 退）/ 2=繼續加單
# L3 階段已有 cart，達上限進子狀態給機會比直接清 cart 退更好
L3_UNCLEAR_FINAL_PROMPT: str = "系統將取消這次購物，請選擇取消訂單或繼續加單。（請說\"取消\"或者\"繼續\"）"

# L3 鏈路 C-1（顧客明確說結帳）進 L4 前的訂單確認語音模板（2026-05-25 加，B 方案）
# {summary} 範例「6 瓶冰紅茶、1 張刮刮樂」（金額移至 L4 entry 詳細列印，此處不重複）
# 為防多商品點單 + 重複 utterance 累加造成誤增，進結帳前再 confirm 一次給顧客機會修正
L3_CHECKOUT_CONFIRM_TEMPLATE: str = "您即將結帳，總共 {summary}（已享九折優惠），正確嗎？"

# L3 結帳前 confirm 顧客否認後的清 cart 通知（2026-05-26 加，spec 修訂）
# 目前無改/刪商品功能 → 否認 = 清空重點；訊息含 L2_ENTRY_PROMPT 內容，後續主迴圈自動進 DnC
L3_CHECKOUT_REJECT_CLEAR_NOTICE: str = "已幫您清空購物車。如需重新選購，請告訴我您想買什麼？"

# L3 結帳前 confirm 顧客 timeout（沒回應）後的清 cart 通知（2026-05-26 加）
# 區分明確「不對」: 顧客主動意圖；timeout: 沒回應，前綴「由於您沒回應」說明清 cart 原因
L3_CHECKOUT_TIMEOUT_CLEAR_NOTICE: str = "由於您沒回應，已幫您清空購物車。如需重新選購，請告訴我您想買什麼？"

# L3 結帳前 confirm 顧客亂答達上限的取消訊息（2026-05-26 P3.B 加；
# 區分「明確不對」vs「亂答 5 次」兩種 NO 路徑的顧客體感）
L3_CHECKOUT_UNCLEAR_EXHAUSTED_NOTICE: str = (
    "不好意思我聽不太懂您的回應，已取消這次結帳，請重新告訴我您想要購買什麼"
)

# L3 鏈路 C-2 第二段三選一警告語音模板（2026-05-28 重構：從二元 yes/no 改三選一）
# {seconds} = C2_DECISION_TIMEOUT (6s)；wall-clock 倒數內辨識 CONTINUE / CHECKOUT / CANCEL
# 三組 keyword + 各自 strict-short。亂答消耗 budget 不重置；倒數歸零 = 進 confirm 子狀態
#（2026-05-29 反轉：silent timeout 不再直接 L4，與 CHECKOUT keyword path 合流經 confirm）。
#
# 解 Pi demo 2026-05-28 UX bug：舊版「結帳（是）/ 想想（不要）」二元，顧客「不要」歧義
# （「不要結帳」vs「不要整單」）被誤判為「拒絕整單」清 cart。新三選一語意明確、無歧義。
L3_C2_WARNING_TEMPLATE: str = (
    "請問您想要繼續選購商品、結賬還是取消購買？"
    "{seconds}秒後將自動結賬。"
)

# L3 鏈路 C-2 第二段「繼續選購」分支 ack 語音（2026-05-30 加；Pi demo UX 修補）
# 顧客在 C-2 三選一講「繼續」命中 KEYWORDS_C2_CONTINUE → 回 _dialog_main_loop。
# 主迴圈不重播 entry prompt → 若只 speak「好的，請繼續選購」顧客仍失去上下文
# （不知道該講商品名 / 沉默 → 又被 DYC_TIMEOUT 抓回 C-2）。
# 合成 voice 一次 speak 帶 ack + L3 reask 重啟，跟 L2_TO_L3_TRANSITION /
# L3_CANCEL_DECLINED_RESUME 同設計哲學（單一 synth + UX pacing loading-bar 過場）。
L3_C2_CONTINUE_ACK: str = "好的，請繼續選購，請問還要買什麼呢？"

# L3 cancel_confirm NO path 合成 voice（2026-05-30 加；同 4776cb1 同類 root cause 延續）
# 顧客在 L3 拒絕意圖 → cancel_confirm「不要取消 / 繼續」NO → 回 L3 主迴圈 wait。
# 主迴圈不重播 entry prompt → 若只 speak CANCEL_DECLINED_NOTICE 顧客失去上下文。
# 合成 voice 一次 speak 帶 DECLINED + L3 entry 重啟，跟 L2_TO_L3_TRANSITION / L3_C2_CONTINUE_ACK
# 同設計哲學（單一 synth + UX pacing loading-bar 等價過場）。
L3_CANCEL_DECLINED_RESUME: str = "好的，繼續為您服務，請問還有額外需要購買的嗎？"

# 注意：DIALOG_VAGUE_BUY_REASK 已於 2026-05-26 Wave 6 移至 constants/shared.py
# （原因：L2 + L3 通用，跨層性質不應歸單一 L 層 text 檔）
