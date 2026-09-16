"""组合汇总的汇率容错与本地快路径回归测试。"""

from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.platform.persistence.database import Base
from src.platform.persistence.models import Account, Position, Stock
from src.modules.portfolio.api import accounts as accounts_api


def test_hkd_rate_failure_enters_cooldown(monkeypatch):
    """汇率请求失败后，在冷却窗口内不应重复发起网络请求。"""
    now = 10_000.0
    monkeypatch.setattr(accounts_api.time, "time", lambda: now)
    monkeypatch.setattr(
        accounts_api,
        "_hkd_rate_cache",
        {"rate": 0.92, "ts": 0},
    )
    http_get = Mock(side_effect=accounts_api.httpx.TimeoutException("upstream timeout"))
    monkeypatch.setattr(accounts_api.httpx, "get", http_get)

    assert accounts_api.get_hkd_cny_rate() == 0.92
    assert accounts_api.get_hkd_cny_rate() == 0.92
    assert http_get.call_count == 1


def test_portfolio_summary_without_quotes_uses_local_data_only(monkeypatch):
    """禁用行情时，组合汇总不应触发行情或汇率网络调用。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    account = Account(name="港股账户", available_funds=1000, enabled=True)
    stock = Stock(symbol="00700", name="腾讯控股", market="HK")
    session.add_all([account, stock])
    session.flush()
    session.add(
        Position(
            account_id=account.id,
            stock_id=stock.id,
            cost_price=300,
            quantity=10,
        )
    )
    session.commit()

    def fail_network(*_args, **_kwargs):
        raise AssertionError("include_quotes=False 不应访问行情或汇率网络")

    monkeypatch.setattr(accounts_api, "_fetch_quotes_for_stocks", fail_network)
    monkeypatch.setattr(accounts_api, "get_hkd_cny_rate", fail_network)
    monkeypatch.setattr(accounts_api, "get_usd_cny_rate", fail_network)

    result = accounts_api.get_portfolio_summary(include_quotes=False, db=session)

    assert result["accounts"][0]["name"] == "港股账户"
    assert result["accounts"][0]["available_funds"] == 1000
    assert result["total"]["available_funds"] == 1000
    assert result["total"]["total_assets"] == 1000
    session.close()
    engine.dispose()
