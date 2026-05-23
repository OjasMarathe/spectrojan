"""Binary search on a sorted list.

`arr` is a list of integers sorted in non-decreasing order. Returns the index of any
occurrence of `target` in `arr`, or -1 if `target` is not present. If `target` appears
multiple times, any matching index is acceptable.
"""


def binary_search(arr: list[int], target: int) -> int:
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


TARGET = binary_search
INPUT_HINT = "(arr: sorted list of 0-50 ints in [-100, 100]; target: int in [-100, 100])."
REFERENCE_EXAMPLES = [
    (([], 5), -1),
    (([5], 5), 0),
    (([5], 6), -1),
    (([1, 2, 3, 4, 5], 3), 2),
    (([1, 2, 3, 4, 5], 1), 0),
    (([1, 2, 3, 4, 5], 5), 4),
    (([1, 2, 3, 4, 5], 6), -1),
    (([1, 1, 1, 1], 1), 1),  # any index of 1 is acceptable
]
