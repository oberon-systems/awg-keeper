"""Handing out addresses, and not handing them out twice."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, select

from awg_panel import pool
from awg_panel.config import Settings
from awg_panel.db import build_engine
from awg_panel.models import AwgPeer, Interface, ReleasedIp


@pytest.fixture
def session(settings: Settings, node: None) -> Session:
    engine = build_engine(settings)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as opened:
        yield opened


def _interface(session: Session) -> Interface:
    return session.exec(select(Interface)).one()


def test_the_first_address_skips_the_server(session: Session) -> None:
    interface = _interface(session)
    assert pool.allocate(session, interface) == "10.8.0.2/32"


def test_a_taken_address_is_not_offered_again(session: Session) -> None:
    interface = _interface(session)
    session.add(
        AwgPeer(
            profile_id=1,
            interface_id=int(interface.id or 0),
            public_key="a" * 43 + "=",
            assigned_ip="10.8.0.2/32",
        )
    )
    session.flush()
    assert pool.allocate(session, interface) == "10.8.0.3/32"


def test_a_released_address_is_quarantined(session: Session) -> None:
    interface = _interface(session)
    session.add(ReleasedIp(interface_id=int(interface.id or 0), address="10.8.0.2/32"))
    session.flush()
    assert pool.allocate(session, interface) == "10.8.0.3/32"


def test_the_quarantine_expires(session: Session) -> None:
    interface = _interface(session)
    session.add(
        ReleasedIp(
            interface_id=int(interface.id or 0),
            address="10.8.0.2/32",
            released_at=datetime.now(UTC) - pool.QUARANTINE - timedelta(days=1),
        )
    )
    session.flush()
    assert pool.allocate(session, interface) == "10.8.0.2/32"


def test_an_exhausted_pool_is_reported(session: Session) -> None:
    interface = _interface(session)
    interface.pool = "10.9.0.0/30"
    interface.address = "10.9.0.1/30"
    session.add(interface)
    session.flush()
    session.add(
        AwgPeer(
            profile_id=1,
            interface_id=int(interface.id or 0),
            public_key="b" * 43 + "=",
            assigned_ip="10.9.0.2/32",
        )
    )
    session.flush()
    with pytest.raises(pool.PoolExhausted):
        pool.allocate(session, interface)
