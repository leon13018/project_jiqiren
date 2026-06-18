"""FastAPI app：/api/state（快照）+ /ws/state（推送）+ 出 webui 靜態檔。Pi-only（import fastapi）。"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from myProgram.sales.constants import PRODUCTS
from myProgram.web.models import Product, DisplayState, Snapshot

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"
_STANDBY = {"phase": "standby", "cart": {}, "total": 0, "paid": 0}


def _catalog() -> list:
    return [Product(name=n, unit=d["單位"], price_now=d["實際"], price_orig=d["原價"])
            for n, d in PRODUCTS.items()]


def create_app(bus) -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    async def _bind_loop() -> None:
        bus.bind_loop(asyncio.get_running_loop())   # 綁 uvicorn loop 供 run_coroutine_threadsafe

    @app.get("/api/state", response_model=Snapshot)
    def get_state() -> Snapshot:
        st = bus.last_state() or _STANDBY
        return Snapshot(catalog=_catalog(), state=DisplayState(**st))

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket) -> None:
        await ws.accept()
        bus.add_client(ws)
        try:
            await ws.send_json(bus.last_state() or _STANDBY)
            while True:
                await ws.receive_text()              # 模式 A：忽略 client 訊息，只維持連線
        except WebSocketDisconnect:
            pass
        finally:
            bus.remove_client(ws)

    # StaticFiles 掛 "/" 必須最後（greedy）；前面的 /api、/ws 路由先註冊先匹配
    app.mount("/", StaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")
    return app
