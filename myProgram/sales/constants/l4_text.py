"""L4 文字常數（P8 拆分自 constants.py；2026-05-30 重構簡化版）。

包含 L4（付款）對話層的所有字串常數。
"""

__all__ = [
    "L4_ENTRY_PROMPT_TEMPLATE",
    "L4_QR_MOCK_HINT",
    "L4_A_PAY_SUCCESS",
    "L4_B_CANCEL_THANKS",
    "L4_C_CONFIRM_PROMPT_TEMPLATE",
    "L4_D_FORCED_EXIT",
    "L4_ACK_GENTLE",
    "L4_REMIND_PROMPT",
    "L4_UNCLEAR_NOTICE",
]

# ============================================================
# L4 文字常數
# ============================================================

# L4 進入時語音模板（{total} 為總金額；2026-05-25 加九折提示）
L4_ENTRY_PROMPT_TEMPLATE: str = "您的總金額是 {total} 元（已享全品項九折優惠），請您掃碼付款"

# L4 entry 終端列印的 QR mock 提示（2026-05-26 Wave 7a C21：抽常數）
# 未來 S2+ 接真 QR code 時改為「請掃碼付款」即可，只動一處
L4_QR_MOCK_HINT: str = "請掃碼付款（終端輸入 s + Enter 模擬掃碼成功）"

# L4 鏈路 A 掃碼成功語音
L4_A_PAY_SUCCESS: str = "付款成功"

# L4 鏈路 B 取消語音
# 2026-05-26 Wave 7a 文案速覽：更柔和口語版本
L4_B_CANCEL_THANKS: str = "好的，這次先不交易，謝謝光臨"

# L4 鏈路 C 客服模式「請問是否繼續交易？」確認 prompt 模板（2026-05-30 二次重構）
# 取代既有 L4_C_OPTIONS_PROMPT「請選擇退出交易或繼續交易（請說"退出"或者"繼續"）」
# user 反饋舊版需要顧客學「退出 / 繼續」術語且 12s × N 次 retry 過於冗餘。
# 新設計：一次性 {seconds} 秒決策；silent / NO 自動取消，跟 cancel_confirm pattern 對齊
# （但語意 inverse — cancel_confirm「您是否取消」silent=取消；此處「是否繼續」silent=取消）。
# 文案對齊 L3_C2_WARNING_TEMPLATE 風格（全形「？」+ 句末「。」+ {seconds} 模板）。
L4_C_CONFIRM_PROMPT_TEMPLATE: str = "請問是否繼續交易？{seconds}秒後將自動取消交易。"

# L4 鏈路 D 強制退語音
L4_D_FORCED_EXIT: str = "已取消這次交易"

# L4 顧客禮貌肯定 / 等待安撫的溫和回應（2026-05-26 加；使用者實機 UX 修補）
# 不催促、不重印明細、不累計 unclear；告訴顧客系統有聽到，但保持掃碼意圖
L4_ACK_GENTLE: str = "好的，請您方便時掃碼付款即可"

# L4 「12s 沒回應」重複提示語音（2026-05-30 加；重構簡化版）
# 取代原本 4 階段語氣（L4_D_VOICE_NEUTRAL/GENTLE/MODERATE/WARNING）— user 反饋
# budget 30s + 間隔 12s 最多 2 次循環，4 階段沒空間；改用單一中性提示。
# 文案：短促 + 中性 + 無催促感（避免顧客被機器逼迫）
L4_REMIND_PROMPT: str = "請您掃碼付款"

# L4 亂輸入「系統無法判斷」提示（2026-05-30 加；重構簡化版）
# 取代原本 L4_E_CLARIFY「不好意思我聽不太懂您的意思，請說『繼續』或『退出』」+
# unclear_count 機制 — user 反饋複雜；改成只印通用提示不 count，不重置 budget。
# 對齊 L2/L3 B-1 既有風格「不好意思我聽不太懂」。
L4_UNCLEAR_NOTICE: str = "不好意思我聽不太懂"
