"""test_nlu_boundary.py — NLU 邊界 regression tests。

Wave 3 集中修（2026-05-26）全部完成，所有 23 個 xfail 已轉綠燈。
依 HP-1 / HP-2 / HP-4 / B5 / B16 / C12 / C18 / D10 分組。
"""

from myProgram.sales.nlu import classify_intent, has_quantity, parse_quantity


# ============================================================
# HP-1 / B1 / C1：「沒有」substring 誤命中
# ============================================================
# 修法：把「沒有 / 沒了 / 不了」從 _KEYWORDS_REJECT substring 集移到
# _KEYWORDS_REJECT_STRICT_SHORT（只在 text.strip()=="沒有" 才算 reject）。

def test_nlu_l4_沒有問題_should_not_be_reject():
    """「沒有問題」在 L4 語意是「沒問題，可以掃碼」，不應被視為取消交易。"""
    assert classify_intent("沒有問題", "l4") != "拒絕"


def test_nlu_l2_沒有問題_should_not_be_reject():
    """「沒有問題」在 L2 語意是「沒問題，我要買」，不應被視為謝客離去。"""
    assert classify_intent("沒有問題", "l2") != "拒絕"


def test_nlu_l4_沒有啊_should_not_be_reject():
    """「沒有啊」在 L4 語意模糊，但不應直接等同取消交易。"""
    assert classify_intent("沒有啊", "l4") != "拒絕"


# ============================================================
# HP-1 / C5：「不了」substring 誤命中
# ============================================================
# 修法：「不了」移到 strict-short，只在 text.strip()=="不了" 才算 reject。
# 「等不了」「受不了」「忍不了」不會誤命中。

def test_nlu_l4_等不了_should_not_be_reject():
    """「等不了」語意是顧客催促「等太久了」，應走 unclear 或 ACK，不該觸發取消。"""
    assert classify_intent("等不了", "l4") != "拒絕"


def test_nlu_l4_受不了_should_not_be_reject():
    """「受不了」語意是顧客抱怨，應走 unclear 或 ACK，不該觸發取消。"""
    assert classify_intent("受不了", "l4") != "拒絕"


def test_nlu_l4_忍不了_should_not_be_reject():
    """「忍不了」語意是顧客抱怨等待，不應觸發取消交易。"""
    assert classify_intent("忍不了", "l4") != "拒絕"


def test_nlu_l2_等不了_should_not_be_reject():
    """「等不了」在 L2 語意可能是催促，不應被視為「不買了」謝客。"""
    assert classify_intent("等不了", "l2") != "拒絕"


# ============================================================
# HP-2 / B2：negation guard 不完整
# ============================================================
# 修法：l4_service mode negation guard 改用 regex「[不別沒休][一-龥]{0,5}繼續」
# 涵蓋「我不想繼續」「沒打算繼續」「不準備繼續了」等否定句型。

def test_nlu_l4_service_我不想繼續_should_be_exit():
    """「我不想繼續」應視為退出交易意圖，negation guard 應攔截「不想 + 繼續」組合。"""
    assert classify_intent("我不想繼續", "l4_service") == "退出交易"


def test_nlu_l4_service_沒打算繼續_should_be_exit():
    """「沒打算繼續」應視為退出交易意圖，negation 詞「沒」應被 guard 攔截。"""
    assert classify_intent("沒打算繼續", "l4_service") == "退出交易"


def test_nlu_l4_service_不準備繼續了_should_be_exit():
    """「不準備繼續了」語意明確是取消，negation guard 應涵蓋此模式。"""
    assert classify_intent("不準備繼續了", "l4_service") == "退出交易"


# ============================================================
# HP-4 / C2：L4 ACK 漏「等等」單詞
# ============================================================
# 修法：在 KEYWORDS_L4_ACK_OR_WAIT 加入「等等」單詞。
# L4 mode 先進 ACK 分支，「等等」命中 → "等待安撫"，不 fall through 到 _KEYWORDS_THINK。

def test_nlu_l4_等等_should_be_ack_or_wait():
    """「等等」在 L4 掃碼頁是顧客找手機的自然表達，應視為等待安撫，不該走 unclear 催促。"""
    assert classify_intent("等等", "l4") == "等待安撫"


# ============================================================
# B5 / D10：中文複合數字解析
# ============================================================
# 修法：parse_quantity 加入 _parse_compound_chinese helper，
# 先試百位 / 十位複合 pattern，再 fallback 單字 map。

def test_nlu_parse_quantity_十二():
    """「十二瓶」數量應為 12。"""
    assert parse_quantity("十二瓶") == 12


def test_nlu_parse_quantity_二十():
    """「二十瓶」數量應為 20。"""
    assert parse_quantity("二十瓶") == 20


def test_nlu_parse_quantity_二十一():
    """「二十一瓶」數量應為 21。"""
    assert parse_quantity("二十一瓶") == 21


def test_nlu_parse_quantity_一百():
    """「一百瓶」數量應為 100。"""
    assert parse_quantity("一百瓶") == 100


def test_nlu_parse_quantity_三十五():
    """「三十五張」數量應為 35。"""
    assert parse_quantity("三十五張") == 35


# ============================================================
# Bug1（2026-06-14 Pi 實測）：parse_quantity 不支援 千 / 萬
# ============================================================
# 根因：_parse_compound_chinese 只處理 十 / 百，「一千」複合解析失敗 →
# 單字 fallback 抓「一」→ 1（靜默變小，顧客錢包逆向風險）。
# 修法：_parse_compound_chinese 加 萬 → 千 優先序（mirror 既有百位 pattern），
# has_quantity 認 multiplier 字（千仟萬万）。

def test_nlu_parse_quantity_一千張():
    """Bug1 重現：「一千張」數量應為 1000（修前靜默變 1）。"""
    assert parse_quantity("一千張") == 1000


def test_nlu_parse_quantity_一千():
    """「一千」數量應為 1000。"""
    assert parse_quantity("一千") == 1000


def test_nlu_parse_quantity_兩千():
    """「兩千」數量應為 2000（修前靜默變 2）。"""
    assert parse_quantity("兩千") == 2000


def test_nlu_parse_quantity_一萬張():
    """「一萬張」數量應為 10000（修前靜默變 1）。"""
    assert parse_quantity("一萬張") == 10000


def test_nlu_parse_quantity_一千五百():
    """「一千五百」數量應為 1500（千位 rest 解析到百位）。"""
    assert parse_quantity("一千五百") == 1500


def test_nlu_parse_quantity_五千():
    """「五千」數量應為 5000。"""
    assert parse_quantity("五千") == 5000


def test_nlu_has_quantity_千張():
    """「千張」含 multiplier「千」→ 有數量（修前被判無數量 → 誤觸缺數量追問）。"""
    assert has_quantity("千張")


def test_nlu_has_quantity_一千張():
    """「一千張」有數量。"""
    assert has_quantity("一千張")


# Bug1 回歸守護：千 / 萬支援不可改變既有十 / 百 / 個位解析。
def test_nlu_parse_quantity_bug1_regression_lower_orders():
    """回歸：五十 / 一百 / 三 / 十 / 十二 / 二十一 / 三百五十二 解析不變。"""
    assert parse_quantity("五十瓶") == 50
    assert parse_quantity("一百瓶") == 100
    assert parse_quantity("三瓶") == 3
    assert parse_quantity("十瓶") == 10
    assert parse_quantity("十二瓶") == 12
    assert parse_quantity("二十一瓶") == 21
    assert parse_quantity("三百五十二瓶") == 352


# ============================================================
# B16：parse_quantity 「0 瓶」明確回 0
# ============================================================
# 修法：阿拉伯數字分支 — 若有命中但全為 0，明確回 0（不 fallback 1）。
# 保護顧客錢包：「我要 0 瓶」不該默默加 1 個。

def test_nlu_parse_quantity_0_should_not_fallback_1():
    """「我要 0 瓶」應明確回傳 0，不該 silent fallback 為 1（顧客錢包風險）。"""
    result = parse_quantity("我要 0 瓶")
    assert result != 1, f"parse_quantity('我要 0 瓶') 返 {result!r}，不應 fallback 為 1"


def test_nlu_parse_quantity_zero_arabic():
    """「0 張」明確表示 0 個，不應 fallback 為 1。"""
    result = parse_quantity("0 張")
    assert result != 1, f"parse_quantity('0 張') 返 {result!r}，不應 fallback 為 1"


# ============================================================
# C12：「沒事」「沒問題」在 L3 normal mode 應視為結帳
# ============================================================
# 修法：把「沒事 / 沒問題」（含簡體）加入 _KEYWORDS_CHECKOUT。
# L3 normal mode 命中 CHECKOUT → "結帳"；L4 已由 KEYWORDS_L4_ACK_OR_WAIT 先攔截。

def test_nlu_normal_沒事_should_be_checkout():
    """L3 mode「沒事」語意是「沒別的了，去結帳」，應分類為結帳。"""
    assert classify_intent("沒事", "normal") == "結帳"


def test_nlu_normal_沒問題_should_be_checkout():
    """L3 mode「沒問題」語意是「確認，去結帳」，應分類為結帳而非拒絕。"""
    assert classify_intent("沒問題", "normal") == "結帳"


# ============================================================
# C18：「好了」/「對了」等口語在 L2 應視為肯定
# ============================================================
# 修法：把「好了 / 對了 / 好啊」加入 KEYWORDS_WANT_TO_BUY_VAGUE。
# L2 mode 命中 → "想買無商品"（引導顧客說出具體商品），不走 unclear。

def test_nlu_l2_好了_should_not_be_unable_to_judge():
    """L2 confirm context「好了」應視為肯定，不應走 unclear → 催問 → 顧客困惑迴圈。"""
    assert classify_intent("好了", "l2") != "無法判斷"


def test_nlu_l2_對了_should_not_be_unable_to_judge():
    """L2 mode「對了」語意是確認，不應走 unclear。"""
    assert classify_intent("對了", "l2") != "無法判斷"


def test_nlu_l2_好啊_should_not_be_unable_to_judge():
    """L2 mode「好啊」語意是肯定回應，不應走 unclear → 反覆追問。"""
    assert classify_intent("好啊", "l2") != "無法判斷"
