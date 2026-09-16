"""发现实时源失败或超时时的快照回退测试。"""

import asyncio

import pytest

from src.modules.market.api import discovery


class _SlowCollector:
    async def fetch_hot_stocks(self, **_kwargs):
        await asyncio.sleep(0.2)
        return []


def test_hot_stocks_timeout_returns_latest_snapshot(monkeypatch):
    """实时源卡住时应在短超时后返回本地快照。"""
    monkeypatch.setattr(discovery, "DISCOVERY_LIVE_TIMEOUT_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(
        discovery,
        "_latest_snapshot_stocks",
        lambda db, market, limit: [
            {
                "symbol": "600519",
                "market": market,
                "name": "贵州茅台",
                "price": 1700.0,
                "change_pct": 1.2,
                "turnover": 100000.0,
                "volume": 1000.0,
            }
        ],
    )

    async def run():
        return await asyncio.wait_for(
            discovery._hot_stocks_live_or_snapshot(
                collector=_SlowCollector(),
                db=None,
                market="CN",
                mode="turnover",
                limit=20,
            ),
            timeout=0.1,
        )

    result = asyncio.run(run())
    assert result[0]["symbol"] == "600519"


def test_hot_stocks_keeps_empty_result_empty(monkeypatch):
    """实时源和快照都为空时，不伪造成功数据。"""
    class _EmptyCollector:
        async def fetch_hot_stocks(self, **_kwargs):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(discovery, "_latest_snapshot_stocks", lambda db, market, limit: [])
    result = asyncio.run(
        discovery._hot_stocks_live_or_snapshot(
            collector=_EmptyCollector(),
            db=None,
            market="CN",
            mode="turnover",
            limit=20,
        )
    )
    assert result == []
