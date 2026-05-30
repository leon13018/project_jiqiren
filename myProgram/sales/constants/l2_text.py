"""L2 文字常數（P8 拆分自 constants.py）。

包含 L2（首次點餐）對話層的所有字串常數。
"""

__all__ = [
    "L2_ENTRY_PROMPT",
    "L2_CANCEL_DECLINED_RESUME",
    "L2_REJECT_THANKS",
    "L2_TIMEOUT_TO_HAWK_VOICE",
    "L2_B1_CLARIFY",
    "L2_B3_REASK",
    "L2_B3_THIRD_REJECT",
    "L2_C_ADDED",
    "L2_UNCLEAR_REJECT_VOICE",
]

# ============================================================
# L2 文字常數
# ============================================================

# L2 進入時詢問語音
L2_ENTRY_PROMPT: str = "您好，請問需要購買什麼東西嗎？"

# L2 cancel_confirm NO path 合成 voice（2026-05-30 加；Pi demo UX 修補延續 4776cb1）
# 顧客在 L2 拒絕意圖 → cancel_confirm「不要取消 / 繼續」NO → 回 L2 主迴圈 wait。
# 主迴圈進入時不重播 entry prompt（_dialog_main_loop docstring 明寫「entry prompt
# 由 caller 負責」）→ 若只 speak CANCEL_DECLINED_NOTICE 顧客失去上下文 → 沉默 →
# 又被 timeout 抓走。合成 voice 一次 speak 帶 DECLINED + L2 entry 重啟，跟
# L2_TO_L3_TRANSITION 同設計哲學（一次 synth 避免 ALSA drain 停頓）。
# 不含「您好」開場 — 顧客已對話過，重啟用問句不該再叫一次好。
L2_CANCEL_DECLINED_RESUME: str = "好的，繼續為您服務，請問需要購買什麼東西嗎？"

# L2 鏈路 A 拒絕語音（顧客**明確**拒絕時用）
# 2026-05-26 Wave 7a 文案速覽：原「謝謝光臨」過短，改更自然口語
L2_REJECT_THANKS: str = "好的，謝謝光臨"

# L2 cart-empty 等待 timeout 時的提示語音（2026-05-26 加；非「拒絕」而是「無回應」）
# 顧客可能走掉 / 沒注意；用比較中性的提示回 L1 繼續叫賣，不講「謝謝光臨」（會誤導旁人）
L2_TIMEOUT_TO_HAWK_VOICE: str = "不打擾您了，歡迎再次光臨"

# L2 鏈路 B-1 無法判斷語音
L2_B1_CLARIFY: str = "不好意思我聽不太懂，請問要買什麼呢？或者您想聯繫客服？"

# L2 鏈路 B-3 沉默後重問語音
L2_B3_REASK: str = "請問需要購買什麼東西嗎？"

# L2 鏈路 B-3 第 3 次想一下的拒絕語音
L2_B3_THIRD_REJECT: str = "看來您還在猶豫，謝謝光臨歡迎下次再來"

# L2 鏈路 C 加入購物車語音
L2_C_ADDED: str = "好的，已加入購物車"

# L2 鏈路 B-1 累積 UNCLEAR_MAX 次後的拒絕語音（2026-05-25 加）
# L2 階段 cart 還沒建立，達上限直接走鏈路 A 拒絕，比進子狀態更乾淨
L2_UNCLEAR_REJECT_VOICE: str = "您似乎不確定要買什麼，謝謝光臨"
