"""Return the k-th largest element in a list.

`arr` is a non-empty list of integers and `k` is an integer in [1, len(arr)].
The k-th largest is the element that would appear at index (len(arr) - k) if `arr` were
sorted in non-decreasing order. Duplicates count: if arr = [3, 3, 3] and k = 2, return 3.
If preconditions are violated, raise ValueError.
"""


def kth_largest(arr: list[int], k: int) -> int:
    if not arr or k < 1 or k > len(arr):
        raise ValueError("k out of range")
    return sorted(arr)[len(arr) - k]


TARGET = kth_largest
INPUT_HINT = "(arr: list of 0-20 ints in [-50, 50]; k: int in [0, len(arr)+1] — boundary values must be tested)."
REFERENCE_EXAMPLES = [
    (([5], 1), 5),
    (([1, 2, 3], 1), 3),
    (([1, 2, 3], 2), 2),
    (([1, 2, 3], 3), 1),
    (([3, 3, 3], 2), 3),
    (([1, 2, 2, 3], 2), 2),
]
