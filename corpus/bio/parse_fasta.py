"""Parse a FASTA-format string into a dict {header: sequence}.

A FASTA record consists of:
- A header line beginning with '>'. The header is everything on that line AFTER the '>',
  with any leading/trailing whitespace stripped.
- One or more sequence lines, concatenated together with whitespace stripped from each.

If the same header appears twice, the LAST occurrence wins (later record overwrites earlier).
Empty input returns {}. Whitespace-only lines outside any record are ignored.
"""


def parse_fasta(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current_header: str | None = None
    current_seq: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(">"):
            if current_header is not None:
                out[current_header] = "".join(current_seq)
            current_header = line[1:].strip()
            current_seq = []
        elif current_header is not None and line:
            current_seq.append(line)
    if current_header is not None:
        out[current_header] = "".join(current_seq)
    return out


TARGET = parse_fasta
INPUT_HINT = "A FASTA-format string with 0-5 records, header lines beginning with '>', sequences over {A,C,G,T}."
REFERENCE_EXAMPLES = [
    (("",), {}),
    ((">seq1\nACGT",), {"seq1": "ACGT"}),
    ((">seq1\nAC\nGT",), {"seq1": "ACGT"}),
    ((">a\nAA\n>b\nTT",), {"a": "AA", "b": "TT"}),
    ((">dup\nAA\n>dup\nTT",), {"dup": "TT"}),
    ((">x\n",), {"x": ""}),
]
