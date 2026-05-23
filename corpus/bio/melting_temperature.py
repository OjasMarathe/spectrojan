"""Melting temperature (Tm) of a short DNA primer via the Wallace rule.

For primers of length < 14:  Tm = 4 * (G + C) + 2 * (A + T)        in degrees Celsius.
For primers of length >= 14: Tm = 64.9 + 41 * (G + C - 16.4) / N    (Marmur–Schildkraut variant).
Input is an uppercase DNA string over {A, C, G, T}. Returns Tm as a float.
Behavior on empty input is undefined (caller should not pass empty).
"""


def melting_temperature(primer: str) -> float:
    g = primer.count("G")
    c = primer.count("C")
    a = primer.count("A")
    t = primer.count("T")
    n = len(primer)
    if n < 14:
        return float(4 * (g + c) + 2 * (a + t))
    return 64.9 + 41.0 * (g + c - 16.4) / n


TARGET = melting_temperature
INPUT_HINT = "An uppercase DNA string of length 4-30 from {A, C, G, T}."
REFERENCE_EXAMPLES = [
    (("AAAA",), 8.0),
    (("GGGG",), 16.0),
    (("ACGT",), 12.0),
    (("ACGTACGTACGTAC",), 64.9 + 41.0 * (7 - 16.4) / 14),
]
