"""Transcribe DNA to RNA.

Replaces T with U (preserving case). Other characters are passed through unchanged.
"""


def transcribe(dna: str) -> str:
    return dna.replace("T", "U").replace("t", "u")


TARGET = transcribe
INPUT_HINT = "A string of length 0-200 from {A,C,G,T,a,c,g,t}."
REFERENCE_EXAMPLES = [
    (("",), ""),
    (("A",), "A"),
    (("T",), "U"),
    (("t",), "u"),
    (("ACGT",), "ACGU"),
    (("ATAT",), "AUAU"),
]
