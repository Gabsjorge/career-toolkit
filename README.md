# career-toolkit

Claude Code skills that help one person keep a CV and cover letter current, turn each job Offer into an Application (Fit table, tailored CV, cover letter), and keep a Study plan aligned with the market.

It is also a portfolio piece: it shows AI used in a measured, safe way. Scripts do the extraction, counting and checking; a cheap model reads Offers; a stronger model writes wording; every claim in a CV traces to an Evidence ID.

Terms such as Offer, Evidence and Fit table are defined in [CONTEXT.md](CONTEXT.md).

## Status

| Skill | State |
|---|---|
| `refresh-evidence` | available, with Evidence IDs and a machine gate; see [docs/refresh-evidence.md](docs/refresh-evidence.md) |
| `tailor-offer` | available; see [docs/tailor-offer.md](docs/tailor-offer.md) and the demo in [examples/persona](examples/persona) |
| `study-plan` | available; see [docs/study-plan.md](docs/study-plan.md) |
| `career-coach` (agent) | available; routes to the skills, see [docs/career-coach.md](docs/career-coach.md) |
| evals | manual evals on the demo persona; see [docs/evals.md](docs/evals.md) and [evals/README.md](evals/README.md) |
| `search-offers` | available; ranks a pasted digest of Offers by Fit, see [docs/search-offers.md](docs/search-offers.md) |

## Prerequisites

| Tool | Needed for |
|---|---|
| Claude Code | everything |
| Python 3.9+ | all scripts (standard library only, nothing to `pip install`) |
| git | cloning; `refresh-evidence` also reads your commit history |
| `gh` (GitHub CLI), logged in for each host you list | `refresh-evidence` only (counts PRs you reviewed) |
| Node 18+ and npm | PDF rendering only: `cd scripts && npm install` once |
| Google Chrome (macOS) | PDF rendering only; run it in your own terminal |

`tailor-offer` and `study-plan` need only the first three. Fetching an Offer URL uses only Claude's own fetch tool; if your network blocks it, paste the Offer text instead.

## Setup

Once:

1. Clone the repo and start Claude Code with the plugin loaded, from the repo root:
   ```
   git clone git@github.com:Gabsjorge/career-toolkit.git && cd career-toolkit
   claude --plugin-dir .
   ```
2. Create your config outside the repo, from `templates/config.example.json`, at `~/.config/career-toolkit/config.json` (or point `CAREER_TOOLKIT_CONFIG` at another file). Fields: `career_folder` (your private folder), `machine` (`personal` or `client`), `refresh_enabled`, `languages`. Check it:
   ```
   python3 scripts/pipeline.py config-check
   ```
   It prints `OK` or names the bad field. On `machine: client`, `refresh-evidence` stays off until you set `refresh_enabled: true`.
3. Create the private state folder inside your Career folder, then seed your blocklist with the NDA terms to keep out of any output:
   ```
   python3 scripts/pipeline.py init <career_folder>/state
   cp templates/blocklist.example.txt <career_folder>/state/blocklist.txt
   ```

Want to see the flow before using real data? The fictional persona in `examples/persona` works end to end: `python3 scripts/pipeline.py eval-setup examples/persona <empty folder outside the repo>` builds a private Career folder from it and prints the config line to export. See [docs/evals.md](docs/evals.md).

## How to use

Inside Claude Code, either describe your task and let the `career-coach` agent pick the skill ("I got a job offer", "what should I study?"), or call a skill directly. In order:

1. **`/career-toolkit:refresh-evidence`** builds and updates your Evidence (IDs, tags) and proposes CV and letter edits from recent work. Do this first, because tailoring needs Evidence. Details: [docs/refresh-evidence.md](docs/refresh-evidence.md).
2. **`/career-toolkit:search-offers`**: paste a digest of several Offers (for example a job-alert email). You get a ranked shortlist in `<career_folder>/offers/shortlist-<date>.md`, scored by how much of each Offer your Evidence supports. Nothing is searched or fetched. Details: [docs/search-offers.md](docs/search-offers.md).
3. **`/career-toolkit:tailor-offer`**: paste an Offer or a URL. You get `fit-table.md`, `cv-<lang>.md` and `cover-letter-<lang>.md` in `<career_folder>/applications/<slug>/`. Details: [docs/tailor-offer.md](docs/tailor-offer.md).
4. **`/career-toolkit:study-plan`** reads all your Fit tables and writes `<career_folder>/docs/study-plan.md` with two tracks. Details: [docs/study-plan.md](docs/study-plan.md).

What to expect: each skill shows a token estimate before a model step and stops over the cap; scripts, not the model, set Fit Status and count gaps; you approve every CV bullet that has no Evidence ID; Claude never commits or pushes for you.

## The private-data rule

This repo holds code, skills, templates and a fictional demo persona. It never holds a real CV, Evidence, Application, digest, config, blocklist or label map. The private Career folder lives elsewhere; its path comes from your own config ([ADR-0001](docs/adr/0001-private-career-folder.md)).

`applications/` exists but stays empty. `.gitignore` enforces it, and `python3 scripts/pipeline.py guard .` fails if private files appear. CI runs the guard and the unit tests only: no secrets, no model calls.

## Development

```
python3 -m unittest discover -s tests
python3 scripts/pipeline.py guard .
```

Python 3 standard library only.

## License

MIT

## Contributing

Commits follow [Conventional Commits](https://www.conventionalcommits.org) (`feat(scope): description`). Enable the check once per clone:

```
git config --local core.hooksPath .githooks
```

CI runs the same check on every commit.
