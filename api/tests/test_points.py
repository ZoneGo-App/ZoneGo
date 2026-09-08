from datetime import datetime, timezone

from api.points import (
    POINTS_NEW_MERCHANT,
    POINTS_PER_VISIT,
    points_for,
    week_start_of,
)


def test_a_new_store_is_worth_double():
    assert points_for(is_new_merchant=True, already_scored_today=False) == (
        POINTS_PER_VISIT + POINTS_NEW_MERCHANT
    )


def test_a_known_store_pays_the_base():
    assert points_for(is_new_merchant=False, already_scored_today=False) == 5


def test_the_same_store_twice_in_a_day_scores_nothing():
    """Stops someone farming one counter all afternoon."""
    assert points_for(is_new_merchant=False, already_scored_today=True) == 0
    assert points_for(is_new_merchant=True, already_scored_today=True) == 0


def test_a_week_starts_on_monday_at_midnight_utc():
    # Wednesday 9 September 2026, 15:30 UTC.
    wednesday = int(datetime(2026, 9, 9, 15, 30, tzinfo=timezone.utc).timestamp())
    start = datetime.fromtimestamp(week_start_of(wednesday), tz=timezone.utc)
    assert start.weekday() == 0
    assert (start.hour, start.minute, start.second) == (0, 0, 0)


def test_every_day_of_one_week_snaps_to_the_same_monday():
    monday = int(datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp())
    starts = {week_start_of(monday + day * 86_400) for day in range(7)}
    assert starts == {monday}


def test_the_next_day_rolls_into_the_next_week():
    monday = int(datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp())
    assert week_start_of(monday + 7 * 86_400) == monday + 7 * 86_400
