"""Greatest common divisor of two non-negative integers.

Returns gcd(a, b) using the Euclidean algorithm. gcd(0, 0) is defined as 0.
gcd(a, 0) = a and gcd(0, b) = b. Inputs must be non-negative; negative inputs are
not in the intended domain.
"""


def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


TARGET = gcd
INPUT_HINT = "(a: non-negative int in [0, 1000]; b: non-negative int in [0, 1000])."
REFERENCE_EXAMPLES = [
    ((0, 0), 0),
    ((0, 5), 5),
    ((5, 0), 5),
    ((6, 9), 3),
    ((9, 6), 3),
    ((7, 11), 1),
    ((100, 75), 25),
]
