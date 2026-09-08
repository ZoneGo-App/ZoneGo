"""The scoring rules, mirrored from the subgraph mappings.

The chain is the authority: points are counted in `subgraph/src/helpers.ts`
and read back from there. These constants exist so the API can explain a score
and snap a timestamp to the same week boundary the mappings use — never to
compute a score of its own. If the two ever disagree, the subgraph is right.
"""

# Five for showing up, five more the first time at that store, and nothing for
# a second visit to the same store on the same day.
POINTS_PER_VISIT = 5
POINTS_NEW_MERCHANT = 5

WEEK = 604_800
# The unix epoch fell on a Thursday, so dividing by a week puts boundaries on
# Thursdays. Monday is three days earlier, and adding S before the division
# moves every boundary S earlier — so three days of shift lands them on
# Monday 00:00 UTC.
MONDAY_SHIFT = 259_200


def week_start_of(timestamp: int) -> int:
    """Monday 00:00 UTC of the week that timestamp falls in."""
    return ((timestamp + MONDAY_SHIFT) // WEEK) * WEEK - MONDAY_SHIFT


def points_for(is_new_merchant: bool, already_scored_today: bool) -> int:
    if already_scored_today:
        return 0
    return POINTS_PER_VISIT + (POINTS_NEW_MERCHANT if is_new_merchant else 0)
