"""Find open reading frames in an RNA sequence (forward strand only, frame 0 only).

An ORF is a substring starting at an AUG codon and ending at the first in-frame stop codon
(UAA, UAG, or UGA). Returned ORFs are the codons FROM AUG up to but NOT including the stop.
Only ORFs starting in reading frame 0 of the input are reported (i.e. positions 0, 3, 6, ...).
Returns a list of (start_index, protein_string) tuples in order of start_index.

If an AUG is found with no in-frame stop before end-of-sequence, that ORF is NOT reported
(only completed ORFs count).
"""

_STOPS = {"UAA", "UAG", "UGA"}
_TABLE = {
    "UUU": "F", "UUC": "F", "UUA": "L", "UUG": "L",
    "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",
    "AUU": "I", "AUC": "I", "AUA": "I", "AUG": "M",
    "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",
    "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",
    "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "UAU": "Y", "UAC": "Y",
    "CAU": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAU": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAU": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "UGU": "C", "UGC": "C", "UGG": "W",
    "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGU": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def find_orfs(rna: str) -> list[tuple[int, str]]:
    orfs: list[tuple[int, str]] = []
    n = len(rna)
    i = 0
    while i <= n - 3:
        if rna[i : i + 3] == "AUG":
            j = i
            protein: list[str] = []
            found_stop = False
            while j <= n - 3:
                codon = rna[j : j + 3]
                if codon in _STOPS:
                    found_stop = True
                    break
                protein.append(_TABLE.get(codon, "X"))
                j += 3
            if found_stop:
                orfs.append((i, "".join(protein)))
            i = j + 3 if found_stop else n
        else:
            i += 3
    return orfs


TARGET = find_orfs
INPUT_HINT = "An uppercase RNA string of length 0-90 from {A, C, G, U}."
REFERENCE_EXAMPLES = [
    (("",), []),
    (("AUG",), []),                              # AUG with no stop → not reported
    (("AUGUAA",), [(0, "M")]),
    (("AUGUAG",), [(0, "M")]),
    (("AUGUGA",), [(0, "M")]),
    (("AUGGCCUAA",), [(0, "MA")]),
    (("AAUGUAA",), []),                          # AUG at position 1 (frame 1), not frame 0
    (("AUGAAAUAACCC",), [(0, "MK")]),
]
