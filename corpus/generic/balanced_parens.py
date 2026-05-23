"""Check that a string of brackets is balanced.

Accepted bracket pairs are (), [], {}. Any non-bracket character should be ignored.
Returns True iff every opening bracket has a matching closing bracket of the same kind
in correct nesting order. Empty string is balanced.
"""


def is_balanced(s: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    openers = set(pairs.values())
    closers = set(pairs.keys())
    stack: list[str] = []
    for c in s:
        if c in openers:
            stack.append(c)
        elif c in closers:
            if not stack or stack[-1] != pairs[c]:
                return False
            stack.pop()
    return not stack


TARGET = is_balanced
INPUT_HINT = "A string of length 0-30 from {(, ), [, ], {, }, a, b, c, ' '}."
REFERENCE_EXAMPLES = [
    (("",), True),
    (("()",), True),
    (("()[]",), True),
    (("([])",), True),
    (("(",), False),
    ((")",), False),
    (("([)]",), False),
    (("a(b)c",), True),
    (("{[()]}",), True),
]
