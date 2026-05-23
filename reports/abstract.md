# SpecTrojan: Adversarial Specification Validation via Evil Twin Synthesis

**Track:** Specification Validation
**Hackathon:** The Secure Program Synthesis Hackathon, 2026

## Abstract (≈150 words)

Formal verification delivers safety only when the specification captures intended behavior — and recent failures in "verified" libraries show that bad specs, not insufficient proof effort, are now the bottleneck for trustworthy AI-generated code. Existing spec-validation tools search the *input* space, looking for a single input the spec mishandles. **SpecTrojan inverts the search to the *implementation* space**: given a candidate spec, an attacker LLM synthesizes an **Evil Twin** — an alternative implementation that satisfies the spec yet diverges from the reference on intent-bearing inputs. A successful twin is an artifact-level proof of insufficiency. I demonstrate this with a **Bio Honeypot**: a sequence-screening predicate whose generated spec admits a twin that lets a proxy threat motif through. I further introduce an **attack-to-strengthening loop** that proposes spec repairs from each successful attack. Mutation testing and cross-model disagreement serve as baselines; ETS finds defects neither baseline can reach.
