# Attack-to-Strengthening Demo — Bio Honeypot

_Generated 2026-05-22T18:14:00_

## The story arc

1. An LLM is asked to write a specification for a sequence-screening predicate, given only the signature and a high-level intent (the realistic biosecurity setting).
2. SpecTrojan synthesizes an Evil Twin that satisfies the spec but admits threat-bearing inputs.
3. The same LLM is then shown the spec + reference + evil twin, and asked to propose a MINIMAL strengthening that closes the hole.
4. I verify automatically: does the strengthening still accept the reference? Does it reject the twin?
5. (Optional) Re-attack the strengthened spec to see whether SpecTrojan finds a fresh twin.

## Step 1 — the original weak spec

Model: `groq:llama-3.3-70b-versatile#0`

```python
def postcondition(seq: str, result: bool) -> bool:
    return isinstance(result, bool) and (result == True or any(not c.isascii() for c in seq) or any(not (c.isalnum() or c in '-_.()') for c in seq))
```

## Step 2 — the evil twin

Distance from reference: **0.28**

_Synthesis strategy: Return a constant value that the spec happens to permit (e.g. always True, the empty string/list, 0)._

```python
def is_safe_sequence(seq: str) -> bool:
    return True
```

## Step 3 — the proposed strengthening(s)

I ask the LLM up to 3 times, with rising temperature, for a credited repair. Each proposal is mechanically verified on two axes: *accepts-reference* and *closes-attack*. The first attempt that passes both is adopted; otherwise I report the closest near-miss.

### Attempt 1  ·  accepts-reference ✅  ·  closes-attack ❌

```python
def precondition(seq: str) -> bool:
    return isinstance(seq, str)

def postcondition(seq: str, result: bool) -> bool:
    return (not any(not c.isascii() for c in seq)) or (result == True) and (not any(not (c.isalnum() or c in '-_.()') for c in seq))
```

- Diagnosis: the proposed postcondition is logically too lenient — the twin's output is still accepted on every in-domain input I sampled. The most common reason is using `OR` where the LLM meant `IMPLIES`.

### Attempt 2  ·  accepts-reference ❌  ·  closes-attack ✅

```python
def precondition(seq: str) -> bool:
    return isinstance(seq, str)

def postcondition(seq: str, result: bool) -> bool:
    return (not seq or result) and \
           result == (not any(motif in seq for motif in ("DANGER", "BIOHAZARD")))
```

- Rejects the twin on input: `('DANGER',)`

### Attempt 3  ·  accepts-reference ❌  ·  closes-attack ❌

```python
def precondition(seq: str) -> bool:
    return isinstance(seq, str)

def postcondition(seq: str, result: bool) -> bool:
    return (not seq or result) and (result == True or not any(not c.isascii() for c in seq) or not any(not (c.isalnum() or c in '-_.()') for c in seq))
```

- Diagnosis: the proposed postcondition is logically too lenient — the twin's output is still accepted on every in-domain input I sampled. The most common reason is using `OR` where the LLM meant `IMPLIES`.

## Step 4 — control: hand-crafted ideal strengthening

To isolate whether the failures above come from the *LLM* (proposing broken repairs) vs the *verifier* (mis-judging good ones), I run the same verifier on a hand-crafted strengthening I know to be correct:

```python
def postcondition(seq, result):
    """Strengthened: result must be False whenever seq contains a forbidden motif."""
    forbidden = ("DANGER", "BIOHAZARD")
    upper = seq.upper()
    contains_threat = any(m in upper for m in forbidden)
    if contains_threat:
        return result is False
    return isinstance(result, bool)
```

- **Accepts reference?** ✅  ·  **Closes attack?** ✅

- Rejects the twin on input: `('DANGER',)`

This control shows the verifier credits a correct repair when one is provided. The LLM's failures above are *substantive logical errors*, not artifacts of our checking machinery — exactly the kind of error a forward-improvement loop should surface for human review.

## Step 5 — re-attack on the strengthened spec

_Skipped — the strengthening did not pass both verification checks._

## Takeaway

SpecTrojan turns spec validation into a forward-improvement loop. Each attack produces an artifact-level proof of insufficiency; each repair is mechanically verified against both directions (accepts-reference, closes-attack); each strengthening is itself re-attackable. The user is never left with a finding they cannot act on.
