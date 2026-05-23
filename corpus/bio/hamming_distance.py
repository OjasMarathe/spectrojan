"""Hamming distance between two equal-length sequences.

Returns the number of positions where the two strings differ. The two strings must have
equal length; if they do not, raise ValueError.
"""


def hamming_distance(s1: str, s2: str) -> int:
    if len(s1) != len(s2):
        raise ValueError("inputs must have equal length")
    return sum(1 for a, b in zip(s1, s2) if a != b)


TARGET = hamming_distance
INPUT_HINT = "Two equal-length DNA strings (length 0-100) from {A,C,G,T}. Some test cases may have unequal lengths to exercise the precondition."
REFERENCE_EXAMPLES = [
    (("", ""), 0),
    (("A", "A"), 0),
    (("A", "T"), 1),
    (("AAAA", "AAAA"), 0),
    (("ACGT", "TGCA"), 4),
    (("ACGT", "ACGA"), 1),
]
