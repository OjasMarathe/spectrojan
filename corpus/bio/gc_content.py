"""GC content of a DNA sequence.

Returns the fraction of bases in the sequence that are G or C (case-insensitive),
as a float in [0.0, 1.0]. Returns 0.0 for the empty string.
"""


def gc_content(seq: str) -> float:
    if not seq:
        return 0.0
    upper = seq.upper()
    gc = sum(1 for b in upper if b == "G" or b == "C")
    return gc / len(seq)


TARGET = gc_content
INPUT_HINT = "A string of length 0-500 from {A,C,G,T,a,c,g,t,N,n}; may contain ambiguity codes."
REFERENCE_EXAMPLES = [
    (("",), 0.0),
    (("A",), 0.0),
    (("G",), 1.0),
    (("AT",), 0.0),
    (("GC",), 1.0),
    (("ACGT",), 0.5),
    (("acgt",), 0.5),
    (("AAANGC",), 1/3),  # 2 of 6 are G or C
]
