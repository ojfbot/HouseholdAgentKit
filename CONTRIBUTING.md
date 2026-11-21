# Contributing

- Open or pick an issue first. One component, contract suite or rung per issue.
- Branch `<lane>/<slice>`; conventional commits; rebase onto `main` before review. Merges are rebase-only.
- `uv sync --frozen`, then make `uv run kit doctor --rung 1`, `uv run pytest -q -m "not slow and not mutation"` and the lint commands in `.github/workflows/ci.yml` pass locally.
- Everything is synthetic. Do not add real data, scraped data, secrets, model weights or generated datasets.
- A contract change is its own pull request, labeled `contract`, and waits for the owner.
- A bug or a failed eval becomes an eval case before it gets a fix.
- A new `kit doctor` check comes with a planted break that it goes red on.

Agents: the full rules are in [AGENTS.md](AGENTS.md).
