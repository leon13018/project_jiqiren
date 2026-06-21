"""No-cache 靜態 server，供 architecture-diagram skill 渲染圖用。

為何不用 `python -m http.server`：它不送 cache header，Chromium 會快取
theme/*.css —— 改了 CSS 重渲染卻沒生效（HTML 內聯改有效、CSS 檔改無效，
極易誤判「改了沒用」）。本 server 對每個回應送 `Cache-Control: no-store`。

用法：
    py -3.14 nocache_server.py <要服務的目錄> [port=8191]

例：
    py -3.14 nocache_server.py "C:/.../resources/architecture/diagrams" 8191
背景跑（run_in_background），之後 http://127.0.0.1:8191/NN-*.html。
"""
import http.server
import os
import sys

directory = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8191
os.chdir(directory)


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


http.server.HTTPServer(("127.0.0.1", port), NoCacheHandler).serve_forever()
