# Contributing to purrd

The repo follows a simple, auditable **GitHub Flow**: `main` is always stable and
protected, work happens on feature branches, merged via pull request with a green CI.

## Workflow

1. Start from an up-to-date `main`:
   ```bash
   git switch main && git pull
   ```
2. Create a dedicated branch:
   ```bash
   git switch -c feat/<topic>      # or fix/<topic>, docs/<topic>...
   ```
3. Commit using **Conventional Commits** (see below).
4. Push and open a PR against `main`:
   ```bash
   git push -u origin feat/<topic>
   ```
5. CI (`ruff` + `pytest`) must pass. Once reviewed, merge and delete the branch.

> `main` is protected: no direct pushes, everything goes through a PR.

## Conventional Commits

Format: `type(optional scope): description`. Types in use:

| type | usage |
|------|-------|
| `feat` | new feature |
| `fix` | bug fix |
| `docs` | documentation |
| `refactor` | refactoring with no behaviour change |
| `test` | add/update tests |
| `chore` / `ci` | tooling, CI, dependencies |

Examples: `feat(sequencer): vary patterns per bar`,
`fix(player): close the pipe cleanly on stop`.

## Local guards (pre-commit)

Install the hooks once; they run `ruff` before each commit and validate the commit
message (the equivalent of commitlint, but Python-native — no Node).

```bash
uv sync --extra dev
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Tests & lint locally

```bash
uv run pytest -q
uv run ruff check .
```

## Versions & milestones

[SemVer](https://semver.org/) versioning. A milestone = an annotated tag `vX.Y.Z`
on `main`, together with an entry in `CHANGELOG.md`.
