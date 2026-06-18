"""EventBus：橋接同步機器人執行緒 → uvicorn async loop 的 WS 廣播（純 stdlib，無 pydantic）。"""
import asyncio


class EventBus:
    def __init__(self) -> None:
        self._state: dict | None = None
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop) -> None:
        self._loop = loop

    def last_state(self) -> dict | None:
        return self._state

    def add_client(self, ws) -> None:
        self._clients.add(ws)

    def remove_client(self, ws) -> None:
        self._clients.discard(ws)

    def publish(self, state: dict) -> None:
        """機器人執行緒呼叫：存 last-known + 排程廣播到 async loop（loop 未綁時只存）。"""
        self._state = state
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._broadcast(state), self._loop)

    async def _broadcast(self, state: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(state)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
