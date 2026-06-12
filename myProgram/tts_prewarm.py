"""TTS 預熱腳本（perf_w5）——把固定文案一次合成進內容定址快取。

用法（Pi 端，需網路）：
    python3.11 -m myProgram.tts_prewarm
產物：myProgram/tts_cache/<hash>.mp3——commit 進 git 後 demo 斷網也能播全部固定語音。

⚠️ 勿與 demo 同時跑——同句的 .tmp 路徑相同，並發合成會互踩寫壞檔；
本腳本是一次性 bootstrap，跑完再啟動 demo。

枚舉範圍：
    1. 自動：l1_text～l5_text、shared 六個文案模組的公開 str 常數（排除含 "{" 的模板；
       少數 print 專用文案被多錄屬無害的幾百 KB，換取枚舉邏輯零維護）
    2. 手列小域變體：HAWK_SLOGANS 全部＋每個商品的 qty prompt / clarify / at-cap 插值
keyword 清單（keywords.py）是比對資料非語音，不掃。
"""

import asyncio
import importlib
import os

from myProgram.sales.constants import (
    HAWK_SLOGANS,
    PRODUCTS,
    MAX_QTY_PER_ITEM,
    QTY_PROMPT_TEMPLATE,
    QTY_CLARIFY_TEMPLATE,
    AT_CAP_NOTICE_TEMPLATE,
)
from myProgram.tts import _CACHE_DIR, _cache_path_for, _store_into_cache, _synthesize

_TEXT_MODULES = (
    "myProgram.sales.constants.l1_text",
    "myProgram.sales.constants.l2_text",
    "myProgram.sales.constants.l3_text",
    "myProgram.sales.constants.l4_text",
    "myProgram.sales.constants.l5_text",
    "myProgram.sales.constants.shared",
)


def _prewarm_texts() -> list:
    """組預熱清單：固定句＋小域模板變體（去重保序）。"""
    texts: list = []
    for mod_name in _TEXT_MODULES:
        mod = importlib.import_module(mod_name)
        for name in sorted(vars(mod)):
            if name.startswith("_"):
                continue
            value = getattr(mod, name)
            if isinstance(value, str) and "{" not in value:
                texts.append(value)
    texts.extend(HAWK_SLOGANS)
    for product, info in PRODUCTS.items():
        unit = info["單位"]
        texts.append(QTY_PROMPT_TEMPLATE.format(product=product, unit=unit))
        texts.append(QTY_CLARIFY_TEMPLATE.format(unit=unit))
        texts.append(AT_CAP_NOTICE_TEMPLATE.format(
            product=product, max_qty=MAX_QTY_PER_ITEM, unit=unit))
    seen: set = set()
    deduped: list = []
    for t in texts:
        if t and t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def main() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    new = skip = fail = 0
    for text in _prewarm_texts():
        cache_path = _cache_path_for(text)
        if os.path.exists(cache_path):
            skip += 1
            continue
        tmp_path = cache_path + ".tmp"
        try:
            # 一次性腳本：asyncio.run 即可，不需常駐 loop
            asyncio.run(_synthesize(text, tmp_path))
            _store_into_cache(tmp_path, cache_path)
            new += 1
            print(f"[預熱] ✓ {text}")
        except Exception as e:
            fail += 1
            print(f"[預熱] ✗ {text!r}：{type(e).__name__}: {e}")
    print(f"[預熱] 完成：{new} 句新合成 / {skip} 句已存在 / {fail} 句失敗")


if __name__ == "__main__":
    main()
