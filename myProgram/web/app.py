"""FastAPI app：/api/state（快照）+ /ws/state（推送 + 上行命令）+ 出 webui 靜態檔。Pi-only（import fastapi）。"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from myProgram.sales.constants import PRODUCTS
from myProgram.web import commands
from myProgram.web.models import Product, DisplayState, Snapshot

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"
_STANDBY = {"phase": "standby", "cart": {}, "total": 0, "paid": 0}


def _catalog() -> list:
    return [Product(name=n, unit=d["單位"], price_now=d["實際"], price_orig=d["原價"])
            for n, d in PRODUCTS.items()]


class _NoCacheStaticFiles(StaticFiles):
    """靜態檔一律 no-cache —— 前端 app.js 更新後瀏覽器一般重整即拿新版（避免 demo 開發快取舊碼）。"""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp


def create_app(bus, on_input) -> FastAPI:
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
                raw = await ws.receive_text()        # Phase 2：上行觸控命令
                try:
                    token = commands.to_token(json.loads(raw))
                except Exception:
                    token = None                     # 壞 JSON / 非 dict → 忽略（不拖垮連線）
                if token is not None:
                    on_input(token)                  # = input_reader.inject（queue.put，thread-safe）
        except WebSocketDisconnect:
            pass
        finally:
            bus.remove_client(ws)

    # StaticFiles 掛 "/" 必須最後（greedy）；前面的 /api、/ws 路由先註冊先匹配
    app.mount("/", _NoCacheStaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")
    return app
