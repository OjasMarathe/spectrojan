# Metamorphic Spec Testing — Results

Each row: a (target, candidate spec) pair. I apply five semantics-preserving
code transforms to the reference implementation and report the fraction the spec accepts.
A robust spec accepts ALL transforms; failures indicate the spec is overfit to syntax.

| Target | Spec | Transforms applied | Accepted | Robustness |
|---|---|---|---|---|
| `count_kmers` | `groq:llama-3.3-70b-versatile#0` | 4 | 4 | 100% |
| `count_kmers` | `groq:llama-3.3-70b-versatile#1` | 4 | 4 | 100% |
| `filter_reads_by_quality` | `groq:llama-3.3-70b-versatile#0` | 3 | 3 | 100% |
| `filter_reads_by_quality` | `groq:llama-3.3-70b-versatile#1` | 3 | 3 | 100% |
| `find_orfs` | `groq:llama-3.3-70b-versatile#1` | 4 | 4 | 100% |
| `gc_content` | `groq:llama-3.3-70b-versatile#0` | 3 | 2 | 67% |
| `is_safe_sequence` | `groq:llama-3.3-70b-versatile#0` | 3 | 0 | 0% |
| `is_safe_sequence` | `groq:llama-3.3-70b-versatile#1` | 3 | 2 | 67% |
| `kth_largest` | `gemini:gemini-2.5-flash#1` | 2 | 2 | 100% |
| `reverse_complement` | `groq:llama-3.3-70b-versatile#0` | 3 | 3 | 100% |
| `reverse_complement` | `groq:llama-3.3-70b-versatile#1` | 3 | 3 | 100% |

**Summary**: 8/11 (spec, transform-suite) pairs were fully robust.

Metamorphic failures (robustness < 100%) flag specs that are syntactically rigid — rejecting alternative *but equivalent* implementations of the same function. This is a covert failure mode orthogonal to under-constraint.