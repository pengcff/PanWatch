"""首页 AI 策展超时回退测试。"""

import asyncio

from src.modules.portfolio.api import dashboard
from src.platform.persistence.database import SessionLocal


def test_curate_timeout_falls_back_to_original_order(monkeypatch):
    class _SlowAI:
        async def chat(self, *_args, **_kwargs):
            await asyncio.sleep(0.2)
            return "1|100|迟到的结果"

    monkeypatch.setattr(dashboard, "CURATE_AI_TIMEOUT_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(
        dashboard,
        "get_configured_failover_client",
        lambda db, model_id=None: _SlowAI(),
    )
    request = dashboard.CurateRequest(
        candidates=[
            dashboard.CurateCandidate(type="holding", symbol="A", name="甲", signal="先看甲"),
            dashboard.CurateCandidate(type="watch", symbol="B", name="乙", signal="再看乙"),
        ]
    )
    db = SessionLocal()
    try:
        result = asyncio.run(
            asyncio.wait_for(dashboard.curate_today(request, db), timeout=0.1)
        )
    finally:
        db.close()

    assert [item["index"] for item in result["items"]] == [0, 1]
