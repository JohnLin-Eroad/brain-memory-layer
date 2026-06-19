# Memory Model — decay, reinforcement, supersession

The recall model gives the brain a *memory of which knowledge is trusted, when
it was last useful, and what replaced it* — without ever losing data. It is
inspired by hippocampal memory consolidation: frequently-recalled, recently-used
knowledge stays strong; unused knowledge fades but never disappears.

All constants live at the top of [`bin/brain`](../bin/brain) and are repeated
here. If you change one, change both and bump the docs.

---

## 1. Decay — `effective_strength`

```
effective_strength = clamp(strength * 0.5 ** (age_days / half_life_days),
                           DECAY_FLOOR, 1.0)
age_days = now - last_retrieved_at
```

| constant | value | meaning |
|---|---|---|
| `DECAY_FLOOR` | 0.05 | a memory never decays below 5% — nothing vanishes |
| `DEFAULT_HALF_LIFE` | 7.0 d | fresh memories halve in relevance weight weekly… |
| `MAX_HALF_LIFE` | 180 d | …until reinforced enough to persist for months |

A memory with no `last_retrieved_at` sits at its stored `strength` (no decay
yet). Unmanaged rows (no `memory_state`) are treated as strength 1.0.

---

## 2. Ranking blend — `blend_score`

FTS5 `bm25()` gives a base relevance (we flip its sign so higher = better).
Decay modulates it **multiplicatively** so exact-match relevance always
dominates recall weight:

```
blended = relevance * (BLEND_BASE + BLEND_SLOPE * effective_strength)
        * (SUPERSEDE_PENALTY if superseded else 1)
```

| constant | value | effect |
|---|---|---|
| `BLEND_BASE` | 0.5 | a fully-decayed memory keeps 50% of its relevance |
| `BLEND_SLOPE` | 0.5 | a fresh memory gets the full 100% |
| `SUPERSEDE_PENALTY` | 0.25 | superseded memories drop to a quarter weight |

Net factor range: **[0.125, 1.0]**. The blend *reorders* results; it never
invents relevance for an unrelated memory.

---

## 3. Reinforcement — every read strengthens

On each `search` / `traverse` / `fetch`, matched memories are bumped:

```
new_strength   = min(1.0, effective_strength + BUMP[source])
new_half_life  = min(180, half_life * 1.05)     # +5% per successful recall
last_retrieved_at = now ;  retrieval_count += 1
```

| source | bump |
|---|---|
| `search` | +0.05 |
| `traverse` | +0.05 |
| `fetch` (direct `get`) | +0.20 |

Crucially the bump is applied to the **decayed** strength, not the stored value
— a single hit on a stale memory does not snap it back to 1.0. Pass
`--no-reinforce` for evaluation/automation reads so you don't pollute the model.

---

## 4. Confidence

A qualitative trust label, orthogonal to strength:

`verified` (confirmed true) › `observed` (seen but unconfirmed) ›
`inferred` (deduced) › `stale` (decayed or superseded).

Set explicitly via `brain confidence ID LEVEL`, or automatically: `supersede`
and the `sleep` decay sweep both set `stale`.

---

## 5. Supersession — resolving contradictions

```
brain supersede OLD NEW
```
- `OLD.superseded_by = NEW`, `OLD.confidence = stale`
- adds edge `NEW --supersedes--> OLD` (weight 1.5)
- OLD is penalised in ranking (×0.25) but **kept** — history and reversibility.

This is how two conflicting decisions coexist without the agent flip-flopping:
the winner ranks above the loser, deterministically.

---

## 6. Sleep — consolidation housekeeping

`brain sleep` (schedule daily):
- any memory with `effective_strength ≤ 0.10` → `confidence='stale'`
- prune `access_log` rows older than 90 days

Idempotent, non-destructive, single-pass. Mirrors overnight memory
consolidation: weak traces are flagged, telemetry is compacted.

---

## 7. Worked example

```
day 0   add "Use Flyway for migrations"   strength=1.00  eff=1.00
day 7   (untouched)                         eff≈0.50   (one half-life)
day 7   search "flyway" → hit               strength=min(1, .50+.05)=0.55, hl×1.05
day 21  (untouched)                         decays from the new baseline
…       a better decision arrives:
        supersede old new                   old: stale, ×0.25 in ranking forever
                                            new: ranks first
```
