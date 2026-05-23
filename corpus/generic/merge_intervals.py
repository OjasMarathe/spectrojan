"""Merge a list of possibly-overlapping closed intervals.

Each interval is a (start, end) tuple with start <= end. Intervals may be given in any order.
Returns the minimal list of non-overlapping closed intervals (sorted by start) whose union
equals the union of the inputs. Two intervals touch-but-do-not-overlap (e.g., (1,2) and (3,4))
are NOT merged. Touch-at-endpoint (e.g., (1,2) and (2,3)) IS merged into (1,3).
"""


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    sorted_ivs = sorted(intervals)
    merged: list[tuple[int, int]] = [sorted_ivs[0]]
    for start, end in sorted_ivs[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


TARGET = merge_intervals
INPUT_HINT = "A list of 0-10 (start, end) integer tuples with -30 <= start <= end <= 30, in arbitrary order; may overlap or touch."
REFERENCE_EXAMPLES = [
    (([],), []),
    (([(1, 3)],), [(1, 3)]),
    (([(1, 3), (2, 4)],), [(1, 4)]),
    (([(1, 2), (3, 4)],), [(1, 2), (3, 4)]),       # do not merge gap
    (([(1, 2), (2, 3)],), [(1, 3)]),               # merge touch
    (([(3, 5), (1, 2)],), [(1, 2), (3, 5)]),       # unsorted input
    (([(1, 10), (2, 3), (4, 5)],), [(1, 10)]),     # nested
]
