"""test_nlu_boundary.py — NLU 邊界誤判記錄（Wave 3 待修）。

全部 case 以 @pytest.mark.xfail 標記，代表「已知 bug，Wave 3 修完後拔掉 xfail 改綠燈」。
依 2026-05-26 multi-agent 審查報告（HP-1 / HP-2 / HP-4 / B1 / B2 / B5 / B16 / C1 / C2 / C5 / C12 / C18）分組。

Wave 3 修完後驗收流程：
    1. 拔掉對應 @pytest.mark.xfail
    2. 跑 pytest 確認 PASS
    3. 刪除此檔頂部「Wave 3 待修」說明
"""

import pytest
from myProgram.sales.nlu import classify_intent, parse_quantity


# ============================================================
# HP-1 / B1 / C1：「沒有」substring 誤命中
# ============================================================
# 現狀：_KEYWORDS_REJECT 含「沒有」substring，「沒有問題」在 L4/L2 mode 被
# substring match 吃成「拒絕」，實際語意是「沒問題（同意）」。
# Wave 3 修法：把「沒有」移到 strict-short 集（只在 text.strip()=="沒有" 才算 reject）。

@pytest.mark.xfail(reason="Wave 3 待修 HP-1 / B1 / C1：「沒有問題」在 L4 mode 被 _KEYWORDS_REJECT「沒有」substring 誤判為拒絕")
def test_nlu_l4_沒有問題_should_not_be_reject():
    """「沒有問題」在 L4 語意是「沒問題，可以掃碼」，不應被視為取消交易。"""
    assert classify_intent("沒有問題", "l4") != "拒絕"


@pytest.mark.xfail(reason="Wave 3 待修 HP-1 / C1：「沒有問題」在 L2 mode 同樣被「沒有」substring 誤判為拒絕")
def test_nlu_l2_沒有問題_should_not_be_reject():
    """「沒有問題」在 L2 語意是「沒問題，我要買」，不應被視為謝客離去。"""
    assert classify_intent("沒有問題", "l2") != "拒絕"


@pytest.mark.xfail(reason="Wave 3 待修 HP-1：「沒有啊」在 L4 mode 被「沒有」substring 誤判為拒絕，語意是「我在這裡啊」")
def test_nlu_l4_沒有啊_should_not_be_reject():
    """「沒有啊」在 L4 語意模糊，但不應直接等同取消交易。"""
    assert classify_intent("沒有啊", "l4") != "拒絕"


# ============================================================
# HP-1 / C5：「不了」substring 誤命中
# ============================================================
# 現狀：_KEYWORDS_REJECT 含「不了」，「等不了」「受不了」含「不了」substring
# 在 L4 被誤判為拒絕（取消交易），實際語意是抱怨/催促而非取消。
# Wave 3 修法：「不了」移出 substring 集，或改 strict-short 僅匹配「不了」整詞。

@pytest.mark.xfail(reason="Wave 3 待修 HP-1 / C5：「等不了」含「不了」substring 在 L4 被誤判為取消交易，語意是「等太久了/趕時間」")
def test_nlu_l4_等不了_should_not_be_reject():
    """「等不了」語意是顧客催促「等太久了」，應走 unclear 或 ACK，不該觸發取消。"""
    assert classify_intent("等不了", "l4") != "拒絕"


@pytest.mark.xfail(reason="Wave 3 待修 HP-1 / C5：「受不了」含「不了」substring 在 L4 被誤判為取消交易，語意是抱怨等待時間")
def test_nlu_l4_受不了_should_not_be_reject():
    """「受不了」語意是顧客抱怨，應走 unclear 或 ACK，不該觸發取消。"""
    assert classify_intent("受不了", "l4") != "拒絕"


@pytest.mark.xfail(reason="Wave 3 待修 HP-1 / C5：「忍不了」含「不了」substring 在 L4 被誤判，語意是抱怨")
def test_nlu_l4_忍不了_should_not_be_reject():
    """「忍不了」語意是顧客抱怨等待，不應觸發取消交易。"""
    assert classify_intent("忍不了", "l4") != "拒絕"


@pytest.mark.xfail(reason="Wave 3 待修 C5：「等不了」在 L2 mode 同樣被「不了」誤判為拒絕")
def test_nlu_l2_等不了_should_not_be_reject():
    """「等不了」在 L2 語意可能是催促，不應被視為「不買了」謝客。"""
    assert classify_intent("等不了", "l2") != "拒絕"


# ============================================================
# HP-2 / B2：negation guard 不完整
# ============================================================
# 現狀：l4_service mode negation guard 只覆蓋「不繼續/不要繼續/別繼續/停止」；
# 「我不想繼續」「沒打算繼續」會 fallthrough 到 _KEYWORDS_CONTINUE substring 命中「繼續」
# → 返「繼續交易」，違反 confirm-default-must-be-conservative。
# Wave 3 修法：擴充 negation guard 使用 regex「不|別|沒|休 + 繼續」覆蓋更多否定詞。

@pytest.mark.xfail(reason="Wave 3 待修 HP-2 / B2：「我不想繼續」negation guard 漏接，被「繼續」substring 誤判為繼續交易")
def test_nlu_l4_service_我不想繼續_should_be_exit():
    """「我不想繼續」應視為退出交易意圖，negation guard 應攔截「不想 + 繼續」組合。"""
    assert classify_intent("我不想繼續", "l4_service") == "退出交易"


@pytest.mark.xfail(reason="Wave 3 待修 HP-2 / B2：「沒打算繼續」negation guard 漏接，被「繼續」substring 誤判為繼續交易")
def test_nlu_l4_service_沒打算繼續_should_be_exit():
    """「沒打算繼續」應視為退出交易意圖，negation 詞「沒」應被 guard 攔截。"""
    assert classify_intent("沒打算繼續", "l4_service") == "退出交易"


@pytest.mark.xfail(reason="Wave 3 待修 HP-2 / B2：「不準備繼續了」negation guard 漏接，語意明確是取消")
def test_nlu_l4_service_不準備繼續了_should_be_exit():
    """「不準備繼續了」語意明確是取消，negation guard 應涵蓋此模式。"""
    assert classify_intent("不準備繼續了", "l4_service") == "退出交易"


# ============================================================
# HP-4 / C2：L4 ACK 漏「等等」單詞
# ============================================================
# 現狀：KEYWORDS_L4_ACK_OR_WAIT 含「等等我」「等我」「稍等」「等一下」但漏「等等」獨立詞。
# 「等等」在 _KEYWORDS_THINK 內，L4 mode 下走「想一下」→ L4 dispatch 沒對應 → unclear →
# 連 3 次後自動進客服模式。
# Wave 3 修法：在 KEYWORDS_L4_ACK_OR_WAIT 加入「等等」，或 L4 mode 把「想一下」也視為 ACK。

@pytest.mark.xfail(reason="Wave 3 待修 HP-4 / C2：「等等」單獨在 L4 被分類為「想一下」而非「等待安撫」，顧客找手機掃碼時系統催促")
def test_nlu_l4_等等_should_be_ack_or_wait():
    """「等等」在 L4 掃碼頁是顧客找手機的自然表達，應視為等待安撫，不該走 unclear 催促。"""
    assert classify_intent("等等", "l4") == "等待安撫"


# ============================================================
# B5 / D10：中文複合數字解析
# ============================================================
# 現狀：_CHINESE_DIGIT_MAP 是逐字查找，「十二」命中「二」返 2（「十」排 map 後方被「二」覆蓋）；
# 「二十」命中「二」返 2；複合數字規則不支援「十位 × 10 + 個位」運算。
# Wave 3 修法：實作中文數字解析（十 × n + m 邏輯）或導入 cnnum2int 函式庫。

@pytest.mark.xfail(reason="Wave 3 待修 B5 / D10：「十二」應解析為 12，但目前逐字查找只命中「二」返 2")
def test_nlu_parse_quantity_十二():
    """「十二瓶」數量應為 12，複合中文數字目前未實作。"""
    assert parse_quantity("十二瓶") == 12


@pytest.mark.xfail(reason="Wave 3 待修 B5：「二十」應解析為 20，但目前逐字查找只命中「二」返 2")
def test_nlu_parse_quantity_二十():
    """「二十瓶」數量應為 20，複合中文數字目前未實作。"""
    assert parse_quantity("二十瓶") == 20


@pytest.mark.xfail(reason="Wave 3 待修 B5：「二十一」應解析為 21，但目前逐字查找命中「二」返 2")
def test_nlu_parse_quantity_二十一():
    """「二十一瓶」數量應為 21，複合中文數字目前未實作。"""
    assert parse_quantity("二十一瓶") == 21


@pytest.mark.xfail(reason="Wave 3 待修 D10：「一百」應解析為 100，但 _CHINESE_DIGIT_MAP 無「百」位支援")
def test_nlu_parse_quantity_一百():
    """「一百瓶」數量應為 100，百位中文數字目前未實作。"""
    assert parse_quantity("一百瓶") == 100


@pytest.mark.xfail(reason="Wave 3 待修 B5：「三十五」應解析為 35，複合十位中文數字目前未實作")
def test_nlu_parse_quantity_三十五():
    """「三十五張」數量應為 35，複合中文數字目前未實作。"""
    assert parse_quantity("三十五張") == 35


# ============================================================
# B16：parse_quantity 「0 瓶」silent fallback
# ============================================================
# 現狀：parse_quantity 阿拉伯數字分支跳過 n==0（只取 n>0），無任何 0 命中後
# fallthrough 到「預設 1」，「我要 0 瓶」變成點了 1 個。
# Wave 3 修法：應明確回傳 0 或 raise ValueError，不該 silent fallback 為 1。

@pytest.mark.xfail(reason="Wave 3 待修 B16：「我要 0 瓶」阿拉伯數字 0 被跳過後 fallback 為 1，顧客明確說 0 卻被默默加 1 個")
def test_nlu_parse_quantity_0_should_not_fallback_1():
    """「我要 0 瓶」應明確回傳 0（或 raise），不該 silent fallback 為 1（顧客錢包風險）。"""
    result = parse_quantity("我要 0 瓶")
    assert result != 1, f"parse_quantity('我要 0 瓶') 返 {result!r}，不應 fallback 為 1"


@pytest.mark.xfail(reason="Wave 3 待修 B16：「0 張」阿拉伯數字 0 被跳過後 fallback 為 1")
def test_nlu_parse_quantity_zero_arabic():
    """「0 張」明確表示 0 個，不應 fallback 為 1。"""
    result = parse_quantity("0 張")
    assert result != 1, f"parse_quantity('0 張') 返 {result!r}，不應 fallback 為 1"


# ============================================================
# C12：「沒事」「沒問題」在 L3 normal mode 應視為結帳
# ============================================================
# 現狀：「沒事」「沒問題」不在 _KEYWORDS_CHECKOUT 或 _KEYWORDS_REJECT_L3_STRICT 內，
# 也不在 _KEYWORDS_REJECT（strict-short「沒」會被 _equals_strict_short 擋住，但
# 「沒事」「沒問題」 _contains_any REJECT → 命中「沒有」substring 返「拒絕」）。
# 實際上 L3 mode「沒事了」「沒問題」應視為「不追加，去結帳」。
# Wave 3 修法：把常見口語「沒事/沒問題/沒了」也加入 _KEYWORDS_CHECKOUT 或 L3 結帳白名單。

@pytest.mark.xfail(reason="Wave 3 待修 C12：L3 mode「沒事」應視為「不追加，結帳」，目前被「沒」誤命中走 _KEYWORDS_REJECT 返結帳可能不穩定或走 unclear")
def test_nlu_normal_沒事_should_be_checkout():
    """L3 mode「沒事」語意是「沒別的了，去結帳」，應分類為結帳。"""
    assert classify_intent("沒事", "normal") == "結帳"


@pytest.mark.xfail(reason="Wave 3 待修 C12：L3 mode「沒問題」應視為「沒問題，去結帳」，目前「沒有」substring 誤命中返拒絕")
def test_nlu_normal_沒問題_should_be_checkout():
    """L3 mode「沒問題」語意是「確認，去結帳」，應分類為結帳而非拒絕。"""
    assert classify_intent("沒問題", "normal") == "結帳"


# ============================================================
# C18：「好了」/「對了」等口語在 L2 應視為肯定
# ============================================================
# 現狀：「好了」在 _KEYWORDS_CHECKOUT 被移除（見 nlu.py 註解「no/nope/好了移除」），
# L2 mode 下不在任何 keyword 集 → 返「無法判斷」。
# 實際 L2 語境：顧客回答「好了」通常表示確認商品選擇（接近肯定/結帳意圖）。
# Wave 3 修法：在 L2 mode 把「好了」視為肯定確認（可加到 L2 專屬 confirm yes keyword）。

@pytest.mark.xfail(reason="Wave 3 待修 C18：「好了」在 L2 mode 返「無法判斷」，語意應是顧客確認商品（肯定/結帳），應至少不走 unclear")
def test_nlu_l2_好了_should_not_be_unable_to_judge():
    """L2 confirm context「好了」應視為肯定，不應走 unclear → 催問 → 顧客困惑迴圈。"""
    assert classify_intent("好了", "l2") != "無法判斷"


@pytest.mark.xfail(reason="Wave 3 待修 C18：「對了」在 L2 mode 不在任何 keyword 集，返「無法判斷」，語意是確認")
def test_nlu_l2_對了_should_not_be_unable_to_judge():
    """L2 mode「對了」語意是確認，不應走 unclear。"""
    assert classify_intent("對了", "l2") != "無法判斷"


@pytest.mark.xfail(reason="Wave 3 待修 C18：「好啊」在 L2 mode 不在 KEYWORDS_L4_ACK_SHORT（L4 限定），返「無法判斷」")
def test_nlu_l2_好啊_should_not_be_unable_to_judge():
    """L2 mode「好啊」語意是肯定回應，不應走 unclear → 反覆追問。"""
    assert classify_intent("好啊", "l2") != "無法判斷"
