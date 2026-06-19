# Copilot integration assets

Everything here wires the Brain Memory Layer into the GitHub Copilot CLI. There
are two tiers — install only what your setup uses.

| Asset | Tier | What it is |
|---|---|---|
| `copilot-instructions.snippet.md` | **Required** | Drop-in block for `~/.copilot/copilot-instructions.md`. The minimal contract every agent follows. |
| `../skills/brain-sync/` | **Required** | The skill that carries the recall/capture detail. Installs to `~/.copilot/skills/brain-sync/`. |
| `agents/brain-data-retrieval.agent.md` | Optional | Dedicated fetch agent — only if you run a multi-agent pipeline. |
| `agents/brain-consolidation.agent.md` | Optional | Dedicated write-back agent — only if you run a multi-agent pipeline. |

A **single-agent** Copilot user needs just the two Required items: the snippet
tells the agent when to call `brain`, and the skill explains how. The two
optional agents only matter if you split work across a retrieval → work →
consolidation pipeline.

## Install

The package installer does this for you:

```bash
./install.sh --with-copilot
```

It will:
1. install the `brain-sync` skill into `~/.copilot/skills/`,
2. install the two optional agents into `~/.copilot/agents/`,
3. append the instructions snippet to `~/.copilot/copilot-instructions.md`
   (only if the `## Memory layer (brain)` heading isn't already present).

Re-running is safe (idempotent — it won't duplicate the snippet).

## Manual install

```bash
mkdir -p ~/.copilot/skills ~/.copilot/agents
cp -R skills/brain-sync           ~/.copilot/skills/
cp copilot/agents/*.agent.md      ~/.copilot/agents/
cat copilot/copilot-instructions.snippet.md >> ~/.copilot/copilot-instructions.md
```

## Note on the snippet

The snippet intentionally omits company specifics so it's portable across
teams. If your org has shared domains/scopes, document the canonical `--scope`
names in your team template alongside the snippet — but keep the contract itself
unchanged so every engineer's brain behaves identically.
