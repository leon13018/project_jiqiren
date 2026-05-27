"""L4 文字常數（P8 拆分自 constants.py）。

包含 L4（付款）對話層的所有字串常數。
"""

__all__ = [
    "L4_ENTRY_PROMPT_TEMPLATE",
    "L4_QR_MOCK_HINT",
    "L4_A_PAY_SUCCESS",
    "L4_B_CANCEL_THANKS",
    "L4_C_OPTIONS_PROMPT",
    "L4_D_FORCED_EXIT",
    "L4_D_FINAL_PROMPT",
    "L4_E_CLARIFY",
    "L4_E_AUTO_SERVICE",
    "L4_ACK_GENTLE",
    "L4_D_VOICE_NEUTRAL",
    "L4_D_VOICE_GENTLE",
    "L4_D_VOICE_MODERATE",
    "L4_D_VOICE_WARNING",
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

# L4 鏈路 C 客服模式選項提示語音（終端 + 語音皆印）
L4_C_OPTIONS_PROMPT: str = "請選擇退出交易或繼續交易。（請說\"退出\"或者\"繼續\"）"

# L4 鏈路 D 強制退語音
L4_D_FORCED_EXIT: str = "已取消這次交易"

# L4 鏈路 D 達上限後的「最終確認」子狀態提示語音（2026-05-25 加）
# 6s 給顧客選『取消訂單』或『繼續當前付款』；同 L4_C_OPTIONS_PROMPT 風格
L4_D_FINAL_PROMPT: str = "因為都沒有付款，系統即將取消這次交易，請選擇取消訂單或繼續當前付款。（請說\"取消\"或者\"繼續\"）"

# L4 鏈路 E 無法判斷語音（unclear_count < 3）
L4_E_CLARIFY: str = "不好意思我聽不太懂，請掃碼付款，或者您想聯繫客服？"

# L4 鏈路 E 第 3 次自動進客服語音（unclear_count == 3）
L4_E_AUTO_SERVICE: str = "我可能無法協助您，正在為您聯繫客服"

# L4 顧客禮貌肯定 / 等待安撫的溫和回應（2026-05-26 加；使用者實機 UX 修補）
# 不催促、不重印明細、不累計 unclear；告訴顧客系統有聽到，但保持掃碼意圖
L4_ACK_GENTLE: str = "好的，請您方便時掃碼付款即可"

# L4 鏈路 D 四階段催促語音模板（{total} 為總金額）
L4_D_VOICE_NEUTRAL: str = "您的總金額是 {total} 元，請掃碼，或聯繫客服"
L4_D_VOICE_GENTLE: str = "提醒您，您的總金額是 {total} 元，需要協助請說『聯繫客服』"
L4_D_VOICE_MODERATE: str = "您的總金額是 {total} 元，請儘快完成掃碼"
L4_D_VOICE_WARNING: str = "您的總金額是 {total} 元，請儘快完成掃碼，否則將取消這次交易"
