# 「這樣就好」加入 CHECKOUT keyword — Mini SDD spec

- **檔**：`myProgram/sales/nlu.py:98`（繁體）、`:100`（簡體）— `_KEYWORDS_CHECKOUT`
- **改前**：清單含「就這樣」「可以了」等，但**無**「這樣就好」
- **改後**：繁體列加 `"這樣就好"`、簡體列加 `"这样就好"`（substring match，一條 cover「這樣就好」「這樣就好了」「不用這樣就好了」三變體）
- **Why**：Pi 實測——L3 加單狀態顧客講「這樣就好 / 這樣就好了」表達「不追加 → 去結帳」，但這詞不在 CHECKOUT keyword → `classify_intent` 落「無法判斷」→ 回「聽不懂」。而「不用這樣就好了」碰巧命中「不用」(REJECT，L3 normal mode 視為不追加→結帳) 而 work——造成使用者觀察到的「有的變體行、有的不行」不一致。加入後三變體一致走結帳。
- **FP 分析**：substring「這樣就好」跟既有「就這樣」同類，難命中非結帳語句；`classify_intent` 優先序上不含 reject/think → 正確落 checkout。L2/L4 mode 行為與既有「就這樣」一致（同為 CHECKOUT substring）。
- **驗證**：`python -m pytest tests/sales/test_nlu.py -q`（新增 case：`classify_intent("這樣就好")=="結帳"`、`("這樣就好了")=="結帳"`、簡體、L3 normal mode）+ 全量 `python -m pytest tests/ -q` 既有不破。
