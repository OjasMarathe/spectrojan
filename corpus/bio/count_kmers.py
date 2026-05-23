"""Count overlapping k-mers in a sequence.

Returns a dict mapping each k-length substring of `seq` to its count of overlapping
occurrences. Returns {} if k <= 0 or k > len(seq).
"""


def count_kmers(seq: str, k: int) -> dict[str, int]:
    if k <= 0 or k > len(seq):
        return {}
    counts: dict[str, int] = {}
    for i in range(len(seq) - k + 1):
        kmer = seq[i : i + k]
        counts[kmer] = counts.get(kmer, 0) + 1
    return counts


TARGET = count_kmers
INPUT_HINT = "(seq: DNA string length 0-100 from {A,C,G,T}, k: int in [-2, 10])."
REFERENCE_EXAMPLES = [
    (("", 3), {}),
    (("A", 1), {"A": 1}),
    (("AAA", 1), {"A": 3}),
    (("AAA", 2), {"AA": 2}),
    (("AAA", 3), {"AAA": 1}),
    (("AAA", 4), {}),
    (("ACGT", 2), {"AC": 1, "CG": 1, "GT": 1}),
    (("ACAC", 2), {"AC": 2, "CA": 1}),
    (("ACGT", 0), {}),
    (("ACGT", -1), {}),
]
