# Running the evals

Persona only. Never point this at a real Career folder. Background: [docs/evals.md](../docs/evals.md).

1. Build the private folder (outside the repo): `python3 scripts/pipeline.py eval-setup examples/persona ~/tmp/eval-run`, then run the `export CAREER_TOOLKIT_CONFIG=...` line it prints.
2. In the same terminal (the export must still be set), start Claude with the plugin's full path, from any folder: `claude --plugin-dir ~/personal_repos/career-toolkit`. (`--plugin-dir .` only works when you are in the repo root.) Check that `/career-toolkit:tailor-offer` is listed.
3. For each file in `~/tmp/eval-run/offers/`, ask for `/career-toolkit:tailor-offer` and paste the Offer. The skill shows a token estimate first; that is the cost check. Say go when you accept it. Answer the skill's questions as a user would (approve nothing that has no Evidence ID).
4. After each Offer, save the skill's final message to `~/tmp/eval-run/results/<offer>/report.txt` and copy the three files from `~/tmp/eval-run/career/applications/<slug>/` into the same results folder (`fit-table.md`, `cv-<lang>.md`, `cover-letter-<lang>.md`).
5. Score: `python3 scripts/pipeline.py eval-score examples/persona ~/tmp/eval-run/results --out evals/results/$(date +%F).md`.

Cost: 8 runs, each one cheap-model call (requirements) and one session-model call (CV and letter). Each run shows its own estimate. The persona files are small, so the input is a few thousand tokens per Offer.

A report in `evals/results/` holds counts and tags of the fictional persona only. Check it before you commit it.
