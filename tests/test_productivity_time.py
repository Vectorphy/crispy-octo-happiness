import pytest

from database import DBHandler


@pytest.mark.asyncio
async def test_focus_totals_are_monotonic_isolated_and_survive_restart(tmp_path):
    path = str(tmp_path / "focus.sqlite")
    db = DBHandler(path)
    await db.connect()
    await db.save_productivity_focus_time("one", 1, "group", {5: 60, 6: 30})
    await db.save_productivity_focus_time("one", 1, "group", {5: 60})
    await db.save_productivity_focus_time("one", 1, "group", {5: 20})
    await db.save_productivity_focus_time("two", 2, "other", {5: 120})
    assert await db.get_productivity_focus_seconds(5) == 180
    assert await db.get_productivity_focus_seconds(6) == 30
    assert await db.get_productivity_focus_seconds(7) == 0
    await db.close()
    restarted = DBHandler(path)
    try:
        await restarted.connect()
        assert await restarted.get_productivity_focus_seconds(5) == 180
    finally:
        await restarted.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True])
async def test_focus_totals_reject_invalid_values_without_partial_write(value):
    db = DBHandler(":memory:")
    await db.connect()
    try:
        with pytest.raises(ValueError):
            await db.save_productivity_focus_time("one", 1, "group", {5: 60, 6: value})
        assert await db.get_productivity_focus_seconds(5) == 0
    finally:
        await db.close()
