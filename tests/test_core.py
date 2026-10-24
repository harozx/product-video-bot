"""Offline tests: database round trip and Telegram admin check."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def database(tmp_path, monkeypatch):
    import config
    import database as db

    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    if hasattr(db, "DATABASE_PATH"):
        monkeypatch.setattr(db, "DATABASE_PATH", str(tmp_path / "test.db"))
    asyncio.run(db.init_database())
    return db


def test_database_round_trip(database):
    async def scenario():
        pid = await database.execute_insert(
            "INSERT INTO products (name, price) VALUES (?, ?)", ("Áo thun", "199K"))
        vid = await database.execute_insert(
            "INSERT INTO videos (product_id, template, status) VALUES (?, ?, ?)",
            (pid, "slideshow", "ready"))
        rows = await database.execute_query(
            "SELECT p.name, v.status FROM videos v JOIN products p ON p.id = v.product_id "
            "WHERE v.id = ?", (vid,))
        return rows

    assert asyncio.run(scenario()) == [{"name": "Áo thun", "status": "ready"}]


def test_is_admin_denies_everyone_when_not_configured(monkeypatch):
    from bot import handlers

    monkeypatch.setattr(handlers.TelegramConfig, "ADMIN_IDS", [])
    assert handlers.is_admin(123) is False


def test_is_admin_allows_only_listed_ids(monkeypatch):
    from bot import handlers

    monkeypatch.setattr(handlers.TelegramConfig, "ADMIN_IDS", [111, 222])
    assert handlers.is_admin(222) is True
    assert handlers.is_admin(333) is False
