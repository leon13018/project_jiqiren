import asyncio

from myProgram.web.bus import EventBus


def test_publish_sets_last_state_without_loop():
    bus = EventBus()
    bus.publish({"phase": "ordering", "cart": {"冰紅茶": 2}, "total": 54, "paid": 0})
    assert bus.last_state()["cart"] == {"冰紅茶": 2}      # loop 未綁 → 只存 last-known，不爆


def test_broadcast_sends_to_clients_and_drops_dead():
    bus = EventBus()
    sent, dead = [], object()

    class OkWS:
        async def send_json(self, s):
            sent.append(s)

    class DeadWS:
        async def send_json(self, s):
            raise RuntimeError("closed")

    ok, bad = OkWS(), DeadWS()
    bus.add_client(ok)
    bus.add_client(bad)
    asyncio.run(bus._broadcast({"phase": "standby"}))
    assert sent == [{"phase": "standby"}]
    assert bad not in bus._clients and ok in bus._clients     # 斷線者剔除
