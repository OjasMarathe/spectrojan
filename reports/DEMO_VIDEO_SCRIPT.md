# SpecTrojan — 3-minute Demo Video Script

**Total runtime:** 3:00
**Tools needed:** screen recorder (QuickTime on Mac is fine — `Cmd+Shift+5`), iTerm/Terminal with a large legible font (18pt+), VS Code or any editor for the side-by-side code reveal.
**Style:** screen capture + voice-over. No camera-on-face needed unless you want to.

---

## Pre-recording setup (5 min)

1. Open three terminal windows side-by-side OR one terminal + one editor:
   - Terminal A: ready to run `python3 scripts/run_bio_honeypot.py`
   - Terminal B (or editor): `corpus/bio/is_safe_sequence.py` open + `reports/bio_honeypot_demo.md` open
2. Make terminal font ≥ 18pt, dark theme, ≥ 120 chars wide.
3. Make sure `.llm_cache/` already contains the Bio Honeypot specs+twins (so the live demo replays from cache in ~5 seconds instead of 60 seconds — same content, faster shoot). If you want a live LLM run, plan for ~60s of dead time and have a 2-line voice-over filler.
4. Take a few practice runs. Aim for clean takes.

---

## Scene-by-scene

### Scene 1 · 0:00 – 0:25 · The problem

**On screen:** A title card or a quick fade-in showing the project name, then cut to the `is_safe_sequence` source code.

**Voice-over** (read in ~25 seconds):
> "In February, four soundness vulnerabilities were found in libcrux, a *verified* cryptographic library. Not bugs in the proofs — bugs in the *specifications*. As LLMs increasingly write both the code AND the specs that govern it, this failure mode becomes systemic. Every spec-validation tool I know of finds bad *inputs*. SpecTrojan finds bad *implementations* — entire functions that satisfy the spec but are obviously wrong."

### Scene 2 · 0:25 – 0:50 · The setup

**On screen:** Open `corpus/bio/is_safe_sequence.py`. Highlight the `is_safe_sequence` function and the `FORBIDDEN_MOTIFS = ("DANGER", "BIOHAZARD")` line.

**Voice-over:**
> "Here's a sequence-screening predicate. It returns False on sequences containing forbidden motifs — DANGER, BIOHAZARD. We use benign proxy strings, not real pathogen markers — the methodology generalizes but the demo is dual-use safe by construction."
>
> "We ask an LLM to write a specification for this function from the SIGNATURE and a HIGH-LEVEL DOCSTRING only — no implementation. This mirrors the realistic biosecurity setting where the secret motif list isn't visible to the spec author."

### Scene 3 · 0:50 – 1:35 · Running the demo

**On screen:** In Terminal A, type and run:
```
python3 scripts/run_bio_honeypot.py
```

**Voice-over while it runs:**
> "SpecTrojan generates six candidate specs, four of which parse. For each spec, it runs Evil Twin Synthesis: an attacker LLM tries to write an alternative implementation that satisfies the spec but diverges from the reference. The attacker rotates through seven different attack strategies and gets failure feedback from previous attempts — CEGIS, but in implementation space."

**(when run finishes / cache replay finishes)**

> "Four specs broken. Sixteen evil twins synthesized. Thirty-five distinct Trojan moments."

### Scene 4 · 1:35 – 2:15 · The killer reveal

**On screen:** Open `reports/bio_honeypot_demo.md`. Scroll to the first "Broken spec" section. Have these two side-by-side (split terminal or just scroll between them):

```python
# The LLM wrote THIS as the specification
def postcondition(seq, result):
    return isinstance(result, bool) and (result == True or not seq)
```

```python
# SpecTrojan synthesized THIS — it also satisfies the spec
def is_safe_sequence(seq):
    return True
```

**Voice-over** (slow, deliberate — this is the punchline):
> "Look at this. The spec looks plausible. But the implementation SpecTrojan synthesized... is `return True`. Always safe. Admits every threat. Both functions satisfy the spec under property-based testing. A formal verifier would have rubber-stamped the Trojan."

**Show the table:**

| Input | Reference | Evil twin |
|---|---|---|
| `"ACGTDANGERACGT"` | `False` | `True` 🚨 |
| `"BIOHAZARD"` | `False` | `True` 🚨 |
| `"biohazard inside"` | `False` | `True` 🚨 |

> "On every threat input, the reference correctly rejects. The Trojan admits."

### Scene 5 · 2:15 – 2:45 · The forward improvement

**On screen:** Open `reports/strengthening_demo.md`. Show the attempt table.

**Voice-over:**
> "Every attack triggers a strengthening loop. We ask the LLM to repair the broken spec. The repairs are mechanically verified on two axes — does it still accept the reference, and does it reject the twin?"
>
> "In this run, all three LLM-proposed repairs were broken in different ways — under-strong, over-strong, both. The verifier caught all of them. Our hand-crafted control passes both checks, proving the verifier works."
>
> "SpecTrojan never silently accepts a broken repair."

### Scene 6 · 2:45 – 3:00 · Close

**On screen:** The architecture diagram from README, or just a clean shot of the GitHub repo URL.

**Voice-over:**
> "Three contributions. Evil Twin Synthesis. The attack-to-strengthening loop. The Bio Honeypot demo. All dual-use safe. Open-source. Github dot com slash YOUR-USERNAME slash spectrojan. Thanks."

---

## Recording tips

- **Run the bio honeypot once before recording** so the LLM cache is warm. Then the live run finishes in ~5–10 seconds (replay from cache) instead of 60 seconds.
- **Voice-over second**, not live. Record a silent screen capture first, then record audio over it. Easier to get clean takes.
- **Pace yourself.** 3 minutes feels short but contains a lot — speak deliberately, not fast.
- **One mic-drop moment.** The side-by-side reveal at 1:35 is the visual punchline. Slow down there.
- **Cut ruthlessly.** If you over-shoot 3:30, drop Scene 5 (strengthening). Scene 4 is non-negotiable.

## File format & length

- Apart Research's submission instructions say 3–5 minutes. 3:00 is the sweet spot.
- Export at 1080p (1920×1080), MP4/H.264, mono audio is fine for a voice-over demo.
- Upload to YouTube as **Unlisted** (not private — judges need to view without an account). Get the link.
- Put the link in the docx under "Code and Data → Demo video".
