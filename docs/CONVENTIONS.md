# Conventions — writing good memories

The schema is only half the standard. Consistent *content* is what makes one
engineer's brain legible to tooling and to their future self. Follow these.

---

## 1. One memory = one durable fact

Write atomic memories. "Use Flyway **and** name migrations `V<n>__desc.sql`
**and** baseline legacy DBs" is three memories (`decision`, `preference`,
`gotcha`) linked together — not one blob. Atomic memories decay, supersede, and
rank independently.

## 2. Title: a self-contained one-liner

The title should make sense out of context, in a search result, months later.
- ✅ `Flyway requires explicit baseline on pre-existing schemas`
- ❌ `migration thing` / `see below` / `fix`

## 3. Body: the *why* and the *evidence*

Title is the claim; body is the justification, the command, the link, the
counter-example. Keep it markdown. Include enough that you'd trust it without
re-deriving it.

## 4. Pick the right `type`

| signal | type |
|---|---|
| "we chose X over Y because…" | `decision` |
| "the way to do X is…" | `pattern` / `workflow` |
| "watch out — X surprisingly does Y" | `gotcha` |
| "I always prefer X" | `preference` |
| "tool X behaves like…" | `tool` |
| a stable noun (service/system/person) | `entity` |

## 5. Pick the **most specific true** `level`

Ask: *"For whom is this true?"*
- only this repo → `repo` (+`--scope <repo>`)
- this initiative across repos → `project`
- a whole domain → `domain`
- all my work → `global`
- the agent/toolchain itself → `tooling`

Storing too globally pollutes everyone's recall; too locally hides reusable
knowledge. When unsure, start specific — you can re-add at a broader level and
`supersede` the narrow one.

## 6. Never duplicate across levels — link instead

If a repo gotcha is really an instance of a domain pattern, write both and
`brain link <repo-gotcha> <domain-pattern> --type derived_from`. Duplication
means two things to keep in sync; links mean one.

## 7. Set `confidence` honestly

`verified` is reserved for things you have actually confirmed. Default to
leaving it unset (treated as untagged) or `observed`. Over-claiming `verified`
erodes the value of the whole signal.

## 8. Supersede, don't overwrite, on conflict

When reality changes, add the new memory and `brain supersede <old> <new>`. This
preserves the decision history ("we used to do X, now Y, because…") which is
often more valuable than the current state alone.

## 9. Capture at the moment of insight

The best time to write a memory is the instant you learn something — mid-task,
not in a weekly cleanup. `brain learn "[GOTCHA] …"` is one line; use it freely.

## 10. Keep it factual and non-sensitive

No secrets, tokens, or credentials in memories (it's a plaintext SQLite file).
No PII you wouldn't put in a code comment. The brain is for engineering
knowledge, not data storage.

---

### Quick reference

```bash
brain learn "[DECISION] Adopt trunk-based dev; long-lived branches banned" --level global
brain learn "[GOTCHA] @Transactional self-invocation bypasses the proxy" --level domain --scope backend
brain add "Payment retry policy" --type workflow --level repo --scope payments --body -
brain link <a> <b> --type relates_to
brain supersede <old-decision> <new-decision>
brain search "transaction proxy"
```
