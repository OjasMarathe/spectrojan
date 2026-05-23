"""Filter sequencing reads by mean Phred quality.

Each read is (sequence, quality_string) where quality_string uses Phred+33 encoding:
quality_score(c) = ord(c) - 33. Returns the list of reads (in input order) whose MEAN
quality score is >= threshold. Reads with empty quality strings are excluded regardless
of threshold. Sequence and quality_string must have the same length per read.
"""


def filter_reads_by_quality(
    reads: list[tuple[str, str]], threshold: float
) -> list[tuple[str, str]]:
    out = []
    for seq, qual in reads:
        if not qual:
            continue
        if len(seq) != len(qual):
            continue
        mean_q = sum(ord(c) - 33 for c in qual) / len(qual)
        if mean_q >= threshold:
            out.append((seq, qual))
    return out


TARGET = filter_reads_by_quality
INPUT_HINT = "(reads: list of 0-5 (seq, qual) tuples of equal length 1-20 over {A,C,G,T} and printable ASCII 33-73; threshold: float in [0, 40])."
REFERENCE_EXAMPLES = [
    (([], 20.0), []),
    (([("A", "I")], 20.0), [("A", "I")]),         # I = 73, score = 40
    (([("A", "!")], 20.0), []),                   # ! = 33, score = 0
    (([("AT", "II")], 40.0), [("AT", "II")]),     # mean = 40, threshold = 40
    (([("AT", "II")], 40.1), []),
    (([("AT", "I!")], 20.0), [("AT", "I!")]),     # mean = 20, threshold = 20
    (([("A", "")], 0.0), []),                     # empty quality excluded
]
