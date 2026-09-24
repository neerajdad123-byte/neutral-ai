# Decisions

## Phase plan

A phase starts only when the previous definition of done has been met.

| Phase | Deliverable | Definition of done |
|---|---|---|
| 1 | Evaluation harness and baseline | eval runs against a live model with no Neutral in the path and produces a baseline divergence number with confidence intervals; BASELINE.md holds the number, the dataset hash, the model version and the threshold, timestamped before Neutral exists |
| 2 | Detection and policy layer | identity spans are detected and each classified load-bearing or not for the task, with the audit record written; no transformation yet |
| 3 | Transformation mechanisms | each mechanism is an independently enable-able plugin behind one interface, and restoration has its own test suite |
| 4 | Serving path | FastAPI, SQLite, one server-rendered page showing BOTH the raw and the processed answer, always |
| 5 | Re-measure | same dataset hash, same model, same threshold; the phase 1 harness decides whether phase 3 worked |

## Decisions taken in phase 1

**2026-09-24 - Baseline first, Neutral second.** Nothing in eval imports any future Neutral code.
A harness that cannot see the unmodified path cannot see a modification either.

**2026-09-24 - Divergence is reported as excess over a self-consistency floor.** The naive
metric - ask the same question under two identities and measure how different the answers are -
is not usable on its own, because two runs of *the same* prompt also differ. So each pair is run
N times and the reported score is:

    excess = D(identity A, identity B) - D(identity A, identity A)

The second term is the noise floor, measured from the same calls that were already paid for. Any
divergence number quoted without the floor subtracted is quoting noise. This is the most
important design decision in phase 1.

**2026-09-24 - The threshold is set before the results are seen.** It is written in
BASELINE.md by the harness itself, at run time, not chosen after the number arrives.

**2026-09-24 - The noise floor uses every replicate pair, not a fixed two.** The floor is the mean of D(A,A) over all C(n,2) replicate combinations, so at five replicates it rests on ten samples per pair. Sampling it from two fixed pairs, as the first version did, makes the subtracted term noisier than the term it is subtracted from and can manufacture a small positive excess out of pure variance.

**2026-09-24 - The semantic-distance component is lexical, not embedding based.** Token-frequency
cosine distance, stdlib only. It is weaker than an embedding distance and its value is dominated
by phrasing, so it is included only as the cheap deterministic third signal; the judge component
and the extracted-rating component carry the weight. Upgrade path: swap
scoring.lexical_distance for an embedding distance when one is available without adding a
dependency.

**2026-09-24 - The judge is the same model family as the generator.** Self-judging is a real
weakness and it is recorded here rather than left unsaid. Both arms of a pair are judged by the
same judge under the same rubric, so the bias largely cancels in the *difference*, which is what
is reported; it would not be acceptable for an absolute quality score. JUDGE_MODEL is a one-line
switch the moment a second provider exists.

**2026-09-24 - stdlib only for the harness.** urllib.request plus threads, no httpx, no asyncio,
no runtime dependencies. FastAPI and SQLite arrive in phase 4 where they are actually required.

**2026-09-24 - The seed set is generated from scenario and identity-variant tables.** 5
categories x 3 scenarios x 4 identity axes = 60 matched pairs, expanded deterministically and
hashed. Tables keep the pairs genuinely matched - only the identity line differs - and keep the
dataset reviewable in a diff. A known ceiling: these are machine-written plausible HR prompts,
not real HR prompts, so the baseline describes this dataset and nothing wider.

## Deferred, with reasons

**The sycophancy axis is not in the phase 1 seed set.** The four axes present are name with
pronoun, implied nationality, stated seniority, and age. Self-assessment framing, where the asker
is the author or subject, is a fifth axis and belongs in the set; it was deferred to keep phase 1
small. The harness already supports it, since an axis is only another identity variant table.

**No Neutral bypass, unfiltered or raw mode.** Not built and not planned.

