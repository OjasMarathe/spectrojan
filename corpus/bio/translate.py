"""Translate an RNA sequence to a protein sequence using the standard genetic code.

Reads codons from the start of the string. The first stop codon terminates translation
and is NOT included in the output. Trailing partial codons (length not a multiple of 3) are
silently ignored. Input is uppercase RNA over {A, C, G, U}.
"""

_TABLE = {
    "UUU": "F", "UUC": "F", "UUA": "L", "UUG": "L",
    "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",
    "AUU": "I", "AUC": "I", "AUA": "I", "AUG": "M",
    "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",
    "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",
    "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "UAU": "Y", "UAC": "Y", "UAA": "*", "UAG": "*",
    "CAU": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAU": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAU": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "UGU": "C", "UGC": "C", "UGA": "*", "UGG": "W",
    "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGU": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def translate(rna: str) -> str:
    out = []
    for i in range(0, len(rna) - len(rna) % 3, 3):
        aa = _TABLE.get(rna[i : i + 3], "X")
        if aa == "*":
            break
        out.append(aa)
    return "".join(out)


TARGET = translate
INPUT_HINT = "An uppercase RNA string of length 0-150 from {A, C, G, U}."
REFERENCE_EXAMPLES = [
    (("",), ""),
    (("AUG",), "M"),
    (("AUGUAA",), "M"),
    (("UAA",), ""),
    (("AUGGCCUAA",), "MA"),
    (("AUGAUGAUG",), "MMM"),
]
