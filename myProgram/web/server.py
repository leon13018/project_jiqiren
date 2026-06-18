"""uvicorn 背景執行緒生命週期。Pi-only（import uvicorn）。非主執行緒 → 關 signal handler。"""
import threading

import uvicorn

from myProgram.web.app import create_app


def start(bus, on_input, host: str = "0.0.0.0", port: int = 8137):
    server = uvicorn.Server(uvicorn.Config(create_app(bus, on_input), host=host, port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None      # 非主執行緒不可裝 signal handler
    thread = threading.Thread(target=server.run, name="webui-server", daemon=True)
    thread.start()
    return server, thread


def stop(server) -> None:
    server.should_exit = True
