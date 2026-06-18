#!/usr/bin/env python3
"""WebUI 零快取靜態伺服器（開發 / 展示用）。

等同 `python -m http.server`，但每個回應都加 no-store header，避免瀏覽器快取住
舊的 app.css / app.js（反覆迭代時別台裝置看到舊畫面的元凶）。服務本檔所在的
webui 目錄，跑法不受工作目錄影響：

    python3.11 myProgram/webui/serve.py [port]   # 預設 8137，監聽 0.0.0.0（同 wifi 可連）
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

_ROOT = os.path.dirname(os.path.abspath(__file__))


class NoCacheHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=_ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    print(f"WebUI no-cache server → http://0.0.0.0:{port}/ （serving {_ROOT}）")
    HTTPServer(("0.0.0.0", port), NoCacheHandler).serve_forever()


if __name__ == "__main__":
    main()
