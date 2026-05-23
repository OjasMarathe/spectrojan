"""DNA reverse complement.

Returns the reverse complement of a DNA sequence. Case is preserved on the complemented base.
Domain: characters from {A, C, G, T, a, c, g, t}. Behavior on any other character is undefined.
"""


def reverse_complement(seq: str) -> str:
    table = str.maketrans("ACGTacgt", "TGCAtgca")
    return seq.translate(table)[::-1]


TARGET = reverse_complement
INPUT_HINT = "A string of length 0-200 consisting only of characters from {A, C, G, T, a, c, g, t}."
REFERENCE_EXAMPLES = [
    (("",), ""),
    (("A",), "T"),
    (("ACGT",), "ACGT"),
    (("ATGC",), "GCAT"),
    (("acgt",), "acgt"),
    (("AAAA",), "TTTT"),
]
