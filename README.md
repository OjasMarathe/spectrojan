# SpecTrojan

> Find the implementation that haunts your specification.

**SpecTrojan** validates LLM-generated specifications by *adversarially synthesizing alternative implementations* that satisfy the spec but exhibit obviously wrong behavior. When formal verification succeeds against a weak spec, what gets verified is a Trojan Horse — a function that passes the contract but hides a different program inside.

**Submission for [The Secure Program Synthesis Hackathon]([https://www.apartresearch.com/event/secure-program-synthesis](https://apartresearch.com/sprints/secure-program-synthesis-hackathon-2026-05-22-to-2026-05-24)), Track 2 (Specification Validation), 2026.**

 **Read the report:** [`reports/SpecTrojan_Submission.docx`](reports/SpecTrojan_Submission.docx) 
 **Watch the demo video:** ([https://youtu.be/dzWM0CX3TfM])
 **Reproduce headline finding:** `python3 scripts/run_bio_honeypot.py`

---

## The headline finding, in two functions

```python
# An LLM was asked to write a specification for a sequence-screening predicate
# given only its signature and a high-level docstring (intent-only mode).
def postcondition(seq, result):
    return isinstance(result, bool) and (result == True or not seq)

# SpecTrojan synthesized this implementation — which ALSO satisfies the spec.
def is_safe_sequence(seq):
    return True
```

Both functions satisfy the same formal contract. On the threat-bearing input `"ACGTDANGERACGT"`, the reference correctly returns `False`. The synthesized Trojan returns `True` — admits every threat. A formal verifier checking against this contract would have rubber-stamped it.

In a single 60-second run, SpecTrojan synthesized **16 distinct evil twins** across 4 broken specs, totalling **35 logged Trojan moments** against the Bio Honeypot target. Full transcript: [`reports/bio_honeypot_demo.md`](reports/bio_honeypot_demo.md).

---

## The thesis

Every spec-validation tool I am aware of searches the **input space** — finding a single input where the spec mishandles. SpecTrojan searches the **implementation space** — synthesizing an entire alternative program the spec also admits.

A bad input is *evidence*. An **Evil Twin implementation** is an *artifact-level proof* of insufficiency, readable in 30 seconds: *"both of these functions satisfy the same spec, but they disagree on the things I actually care about. The spec failed."*

Why it matters for biosecurity: LLMs increasingly write bio-pipeline code — sequence screeners, lab-automation glue, BLAST result filters. When the same LLM authors both the screener *and* its specification, the verification is hollow if the spec is weak. SpecTrojan demonstrates this concretely with the **Bio Honeypot**.

---

## Architecture

```
                  +---------------------+
       function ->|  spec_generator     |---> K candidate specs (multi-model)
                  +---------------------+
                            |
                            v
                  +---------------------+
                  |  twin_synthesizer   |  <-- CORE: an LLM attacker
                  |  (Evil Twin Synth)  |       synthesizes spec-conformant
                  +---------------------+       alternative implementations
                            |
                            v
                  +---------------------+
                  | executor + distance |       verify twins satisfy the spec,
                  |        scorer       |       measure divergence from reference
                  +---------------------+
                            |
                            v
                  +---------------------+
                  |   strengthening     |       every successful attack
                  |        loop         |       auto-generates a repair candidate
                  +---------------------+
                            |
                            v
                     Trojan Report

Baselines (for comparison):
  baselines.mutator        AST mutation testing (small-edit perturbations)
  baselines.disagreement   cross-model spec disagreement on inputs
  metamorphic              semantics-preserving code transforms
```

## The three contributions

1. **Evil Twin Synthesis (ETS)** — adversarial program synthesis against specs. The LLM is weaponized *against* the specification, not employed to write it.
2. **Attack-to-Strengthening Loop** — every successful attack auto-produces a candidate spec repair, mechanically verified on two axes (*accepts-reference* and *closes-attack*).
3. **Bio Honeypot** — dual-use-safe demonstration that an LLM-written spec for a sequence-screening predicate can be Trojaned through its spec.

---

## Quickstart

```bash
git clone https://github.com/<your-github>/spectrojan
cd spectrojan
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then drop in your API keys

# The headline demo — synthesizes evil twins on the Bio Honeypot in ~60s
python3 scripts/run_bio_honeypot.py

# The forward-improvement loop
python3 scripts/run_strengthening_demo.py

# Metamorphic robustness across cached specs
python3 scripts/run_metamorphic_sweep.py

# Full corpus comparison sweep (uses real API budget)
python3 scripts/run_corpus_comparison.py --intent-only --n-specs 2
```

**API keys required:** Groq (free at <https://console.groq.com/keys>) and/or Gemini (free at <https://aistudio.google.com/apikey>). OpenAI is also supported. The pipeline auto-falls-back if one provider rate-limits.

---

## Repo layout

| Path | Contents |
|---|---|
| `src/spectrojan/twin_synthesizer.py` | **The core contribution** — CEGIS-style attacker LLM loop |
| `src/spectrojan/executor.py` | Hypothesis-driven spec-conformance checker |
| `src/spectrojan/distance.py` | Behavioral distance scorer (3 axes) |
| `src/spectrojan/strengthening.py` | Attack-to-strengthening loop |
| `src/spectrojan/metamorphic.py` | Semantics-preserving code transforms |
| `src/spectrojan/baselines/` | Mutation testing + cross-spec disagreement |
| `src/spectrojan/bio_honeypot.py` | The killer demo orchestration |
| `corpus/bio/` | 10 bioinformatics-adjacent functions + the honeypot |
| `corpus/generic/` | 5 generic algorithmic functions |
| `scripts/` | Reproduction scripts for every reported result |
| `reports/` | Generated demo reports + final submission docx |
| `evals/runs/` | Raw experimental output (gitignored by default) |
| `tests/` | pytest suite (25 tests, run with `pytest tests/`) |

## Dual-use safety

The Bio Honeypot uses **benign proxy motifs** (`"DANGER"`, `"BIOHAZARD"`) — not pathogen markers. The methodology generalizes to real screening criteria with no code change, but **no part of this repository can be repurposed as an actual pathogen-screening bypass.** See the [Limitations and Dual-Use appendix in the report](reports/SpecTrojan_Submission.docx) for the full risk analysis.

## Citation

```bibtex
@misc{spectrojan2026,
  title  = {SpecTrojan: Adversarial Specification Validation via Evil Twin Synthesis},
  author = {Ojas},
  year   = {2026},
  note   = {Submission to The Secure Program Synthesis Hackathon, Track 2}
}
```

## License

MIT (see `LICENSE`).
