# refresh-evidence

A Claude Code skill that refreshes your CV, cover-letter templates and LinkedIn text from your recent work, once a year or whenever you want.

It is built around two constraints:

- **Few tokens.** Scripts do all the extraction (git history, GitHub review activity). The model only sees small, anonymized digests, and the summarizing is done by the cheapest model tier.
- **NDA-safe.** Client, project and people names never go into an output. Everything derived from confidential work stays in a `state/` folder that is never committed, and every output passes a blocklist scrub.

`SKILL.md` is the instruction file Claude follows. This README is for you: how to set it up, what each part does, and what to do when something fails.

## Contents

1. [How it works](#how-it-works)
2. [Requirements](#requirements)
3. [Quick start](#quick-start)
4. [Folder layout](#folder-layout)
5. [Configuration](#configuration)
6. [Command reference](#command-reference)
7. [Safety model](#safety-model)
8. [Templates and judgment rules](#templates-and-judgment-rules)
9. [State files and outputs](#state-files-and-outputs)
10. [Troubleshooting](#troubleshooting)
11. [Testing](#testing)
12. [Before you push to a git remote](#before-you-push-to-a-git-remote)
13. [Roadmap](#roadmap)
14. [Known limits](#known-limits)

## How it works

```
 1 Config check      scripts   state folder + config + blocklist exist?
 2 Digest            scripts   git log + GitHub reviews -> small anonymized digests   (0 model tokens)
 3 Estimate          scripts   token and cost estimate vs your cap                     (0 model tokens)
        you: approve the numbers
 4 Summarize         cheap model, one subagent per ~30,000 characters of digests
 5 Scrub gate        scripts   check-draft (format) + blocklist scrub on the draft
 6 Merge and review  you: edit the evidence; scripts re-scrub; mark-run records the date
 7 Propose edits     model proposes small CV / cover letter / LinkedIn edits; scripts scrub them
        you: render the PDF in your own terminal and check the layout
```

Stages 2 and 3 are the "dry run". They cost nothing and show what a model call would cost before you agree to it. Claude stops after each stage, and state is saved, so a later session resumes at the next unfinished stage.

The first run is a **full** run (all history). Later runs are **delta** runs that only look at activity since the last `mark-run`. Pass `--full` to force a full run.

## Requirements

| Tool | Why | Notes |
|------|-----|-------|
| Claude Code | runs the skill | |
| Python 3.9+ | all scripts | standard library only, nothing to `pip install` |
| git | reads commit history | |
| `gh` (GitHub CLI) | counts PRs you reviewed | must be logged in for each host in `gh_hosts` (`gh auth status`) |
| Node 18+ and npm | Markdown to HTML with `marked` | `cd scripts && npm install` once |
| Google Chrome (macOS path) | HTML to PDF | path is set in `scripts/render_pdf.py`; Chrome cannot run inside the agent sandbox, so you render PDFs in your own terminal |

## Quick start

1. Install this repository as a Claude Code plugin (or copy `skills/refresh-evidence` where your Claude Code finds skills). Check your Claude Code docs for the current install steps.
2. Install the one JavaScript dependency:
   ```
   cd career-toolkit/scripts && npm install
   ```
3. Create the state folder (inside your private Career folder, never inside this repository):
   ```
   python3 career-toolkit/scripts/pipeline.py init state
   ```
4. Create `state/config.json` from `state/config.example.json` ([Configuration](#configuration)).
5. Create `state/blocklist.txt` from `templates/blocklist.example.txt` and put your real NDA terms in it.
6. Ask Claude: "run refresh-evidence". It follows `SKILL.md` stage by stage and stops for your approval where needed.

## Folder layout

`career-toolkit/` is the repository. `state/` lives in your private Career folder and is never part of the repository.

```
career/                       your career folder (not a repo)
├── state/                    confidential, never commit
│   ├── .gitignore            written by `init`
│   ├── config.example.json   written by `init`
│   ├── notes.md              written by `init`; your lasting rulings
│   ├── config.json           YOU create
│   ├── blocklist.txt         YOU create
│   ├── label-map.json        created by `digest`
│   ├── digests/              created by `digest`
│   ├── evidence.md           created in stage 6
│   ├── last_run.json         created by `mark-run`
│   └── run.log               created by `digest`
├── cv-en.md, cv-pt.md, ...   your outputs (outside the repo)

career-toolkit/               THE REPO
├── skills/refresh-evidence/SKILL.md   instructions Claude follows
├── docs/refresh-evidence.md  this file
├── templates/                blocklist example, CV, cover letter, LinkedIn skeletons
├── scripts/                  all tools (below)
└── tests/                    unittest suite
```

Files you must create yourself:

| File | What it contains |
|------|------------------|
| `state/config.json` | your emails, repo paths, GitHub hosts and token cap |
| `state/blocklist.txt` | one regular expression per line: every client, project, person, host and internal-tool term you must never publish |

## Configuration

### `state/config.json`

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `authors` | list of strings | required | **Every** email you commit with. Matching is exact (case-insensitive), so `a@b.com` does not match `xa@b.com`. Find yours with `git shortlog -sne` in a repo. |
| `repos` | list of `{ "path", "kind" }` | required | Local clones to read. `path` may start with `~`. `kind` is a free label (for example `client`). Two repos with the same folder name are reported as a gap. |
| `gh_hosts` | list of strings | `[]` | GitHub hosts to count reviewed PRs on, for example `github.com` or an enterprise host. Leave empty to skip PR activity. |
| `cap_tokens` | positive whole number | `60000` | Stage 3 stops if the digests would exceed this many input tokens. |
| `price_per_mtok` | number, 0 or more | `1.0` | Dollars per million tokens, used for the cost estimate only. |

A wrong type stops the run with a message naming the field (never its value).

### `state/blocklist.txt`

- One **regular expression per line**, matched case-insensitively. Lines starting with `#` and blank lines are ignored.
- Use `\b` word boundaries for short or common words, so `\bconta\b` does not match "contact".
- An entry that does not compile, or that matches the empty string (a trailing `|`, `.*`), is rejected with its entry **number** (never its text). Fix it before digesting.
- Colleague **first names** are not redacted automatically (see [Safety model](#safety-model)); add the ones that matter here.
- `templates/blocklist.example.txt` shows the format. Never put real terms in the example file: it is committed.

### `state/notes.md`

Lasting rulings that Claude must respect on every run (for example "say co-designed, never sole author"). Claude reads this file first.

## Command reference

Every command is run as `python3 scripts/pipeline.py <command> ...` unless noted.

| Command | What it does |
|---------|--------------|
| `init STATE` | Creates the state folder with its `.gitignore`, `config.example.json` and `notes.md`. Safe to re-run; never overwrites. |
| `digest STATE [--full]` | Reads git history and GitHub review activity, redacts blocklist matches, writes `digests/repo-N.md` and `digests/reviews-N.md` plus `.report.json`. Staged: the previous set is only replaced if the whole run completes, and it is kept in `digests/.prev/`. Warns about stray sensitive files outside `STATE`. |
| `estimate STATE` | Token and cost estimate for the digests, against `cap_tokens`. Digest input only; it excludes the prompts and later stages. |
| `scrub STATE FILE...` | Checks files against `state/blocklist.txt`. Prints file, line number and entry number, never the term. |
| `check-draft FILE` | Checks that every line of an evidence draft is a well-formed evidence item with no URLs, paths or code. Prints line numbers only. |
| `mark-run STATE [--accept-gaps] [--accept-strays]` | Records the digest date in `last_run.json` so the next run is a delta. Refuses while there are open gaps or stray sensitive files, unless you pass the matching flag. |
| `guard DIR [--blocklist FILE]` | Repo boundary check; see the Guard section at the end. Exit 1 on any violation. |
| `check-strays STATE` | Lists sensitive-named files (blocklist, config, evidence...) found outside `STATE`. |

Unknown flags are rejected (exit 64) so a typo such as `--ful` cannot silently run the wrong scope.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | OK |
| 1 | A check failed (`scrub`, `check-draft`, `check-strays`) or the render failed |
| 2 | `estimate`: over the cap, or no digests |
| 3 | `mark-run`: open gaps |
| 4 | `mark-run`: stray sensitive files outside `STATE` |
| 64 | Usage error or unknown flag |

### Other scripts

| Script | Purpose |
|--------|---------|
| `render_pdf.py MD PDF [--css FILE]` | Markdown to PDF through `marked` and headless Chrome. Refuses Markdown containing script, iframe, object, embed, event-handler attributes or `javascript:`; locks the page down with a content security policy; removes its temp file. Run it in your own terminal. |
| `guard.py DIR [--blocklist FILE]` | Repo boundary check behind `guard`. |
| `nda_scrub.py [--blocklist FILE] FILE...` | The scrub as a stand-alone tool (default blocklist `state/blocklist.txt`). |
| `estimate.py DIR CAP PRICE` | The estimate as a stand-alone tool. |
| `harvest_git.py` | Library: commit digests, author matching, name redaction, injection filter. |
| `harvest_prs.py` | Library: reviewed PRs via `gh`, rate-limit retry, comment sampling. |
| `labels.py` | Library: neutral labels (`repo-1`), redaction, text cleaning. |
| `state.py` | Library: state folder, config loading and validation, last-run date, stray-file scan. |
| `draft_check.py` | Library and CLI behind `check-draft`. |
| `runlog.py` | Library: the counts-only `run.log`. |
| `cv.css` | Print styles used by `render_pdf.py`. |
| `pdftext.swift` | `swift scripts/pdftext.swift file.pdf` prints a PDF's text per page, so you can scrub what is really in the file. |

## Safety model

What is protected, and how:

| Risk | Protection |
|------|------------|
| Real names reach the model | Repos get neutral labels (`repo-1`). Commit subjects are stripped of URLs, emails and ticket IDs, matched against your blocklist, and colleague **full names and emails** are redacted from the repo history automatically. |
| Names leak into a CV or letter | Every output passes the blocklist scrub; `mark-run` and the stages refuse to continue on a hit. |
| Prompt injection through commit messages | Hidden characters are removed; subjects that read like instructions are dropped and counted (`suspect_dropped`); the subagent is told digest text is untrusted; `check-draft` rejects any draft line that is not a plain evidence item. |
| Confidential files committed by accident | `state/` lives outside the repo, has its own `.gitignore`, and `check-strays` / `mark-run` flag sensitive-named files found elsewhere. |
| Local access | The scripts create state files readable only by you (mode 600, folders 700). |
| Unsafe HTML in a PDF | Content security policy and a markup check in `render_pdf.py`. |

What it cannot guarantee:

- **The blocklist is yours to maintain.** Names that are in no blocklist and not in the git history of your repos can pass through.
- **Single-word names** ("Maria", "Jenkins") are not redacted automatically because they collide with tool names. Add the ones that matter to `blocklist.txt`.
- A summarizing subagent can still read files on disk. The input cleaning, the prompt and `check-draft` limit what an injected instruction can plant in your materials; they do not stop a read.
- Hand-written changes you make to outputs are scrubbed, but nothing can judge whether a sentence is true: the judgment rules below help, and you remain the reviewer.

## Templates and judgment rules

`templates/` holds three skeletons with `{{PLACEHOLDER}}` slots: `cv.template.md`, `cover-letter.template.md` and `linkedin.template.md`. Search for `{{` to find what is left to fill.

Claude applies these rules when proposing edits (full list in `SKILL.md`):

- No invented metrics; items without evidence stay marked "no metric".
- Review and mentoring claims follow the data. "Mentoring" only if written feedback shows up repeatedly; otherwise "regular peer review".
- Team work is "co-designed" or "contributed to", never sole authorship, unless you say otherwise.
- Years of experience are counted honestly: total, and the shorter span in the core stack.
- Internal tool names become generic terms ("container tooling").
- Contact details: email, LinkedIn URL, city and country only.
- Education and AI-tool wording come only from what you state.
- Entries are wrapped in `<div class="entry">` so page breaks never split them.

## State files and outputs

| Path (under `state/`) | What it is | Safe for Claude to read? |
|-----------------------|------------|--------------------------|
| `config.json`, `blocklist.txt`, `label-map.json` | Your configuration and the label-to-real-name map | **No.** Claude is told never to read or print them. |
| `digests/repo-N.md`, `reviews-N.md` | Anonymized digests | Claude does not read them either; subagents do. |
| `digests/.report.json` | Counts per run: `written`, `skipped`, `gaps`, `redacted`, `suspect_dropped`, `names_redacted`, `possible_missing`, `unused_entries`, `run_date` | Yes (counts only) |
| `digests/.prev/` | The previous digest set, kept for one generation | No |
| `evidence.md`, `evidence-draft.md` | Approved and candidate evidence items | Yes (anonymized) |
| `evidence.md.bak` | Backup taken before a full run replaces the evidence | Yes |
| `notes.md` | Your lasting rulings | Yes |
| `last_run.json` | Date of the last approved run | Yes |
| `run.log` | Counts-only progress log (never names or text) | Yes |

Delta runs start from the date of the last **digest**, not the approval date, so days between digest and approval cannot be skipped. The cost is up to one day of overlap, which can list an item you already approved; you review the evidence anyway.

In a delta run the review digest counts PRs "active in period" (opened or updated since the last run). GitHub cannot search by review date, so this is an approximation.

`.report.json` fields worth knowing:

- `possible_missing`: commits under your name with an email that is not in `authors`, per repo (a count; the email is never stored). Add the email to `config.json` and re-run.
- `unused_entries`: blocklist entry numbers that matched nothing in this run. In a delta run that is normal and does not mean the entry is dead.

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| `blocklist entry #N is invalid` | Entry N (counting non-comment lines) does not compile or matches everything. Fix that line. |
| `create state/blocklist.txt ...` | The digest needs at least one pattern. |
| `open gaps` (exit 3) | A source failed; see `gaps` in `.report.json` (class name only). Fix it and re-run `digest`, or `mark-run --accept-gaps` if you knowingly accept it. |
| `stray files outside STATE` (exit 4) | Delete the listed files (copies of confidential files), or `--accept-strays` if you keep them on purpose. |
| `gh rate limit: waiting ...` | Normal on a first run; the script waits 65 seconds and retries up to 6 times. Do not interrupt it. |
| `... use an email not in authors` | Add that email to `authors` in `config.json`, then re-run. Find it with `git shortlog -sne`. |
| `no digests` on a delta run | If the report shows no gaps, nothing new happened since the last run. |
| `render failed: Chrome not found` | Install Chrome, or change `CHROME` in `scripts/render_pdf.py`. |
| `render failed: marked is not installed` | `cd scripts && npm install`. |
| `render failed: unsafe markup ... line(s)` | Remove the script, iframe, object, embed, `on...=` attribute or `javascript:` link on those lines. |
| `config.json: 'cap_tokens' must be ...` | A field has the wrong type; fix it. |
| A Python traceback ending in `ValueError` or `RuntimeError` | The last line is the message (for example a missing `config.json` or an unsafe `state/.gitignore`). |

The run log (`state/run.log`) shows what each source did and how long it took.

## Testing

```
python3 -m unittest discover -s tests
```

Run it from this folder. It uses only the standard library, temporary git repositories and fake `gh` runners; it never calls GitHub and never touches your real `state/`. It covers each script, the redaction and scrub behavior, the state folder rules, and that `SKILL.md`, the templates and this README pass the example blocklist.

## Before you push to a git remote

- [ ] `python3 scripts/pipeline.py check-strays ../state` prints `OK`.
- [ ] `git status` shows no `state/`, `blocklist.txt`, `config.json`, `evidence*.md`, `*.pdf`, `*.bak` or `*.log` files.
- [ ] `templates/blocklist.example.txt` has example terms only.
- [ ] No real client, project, person or host names in tests, templates, comments or docs. Tests use made-up names.
- [ ] Tests pass.

## Roadmap

Parked on purpose, to be done if and when they start to hurt:

- Remove the `marked` options (`mangle`, `headerIds`) that versions 8 and later ignore.
- `git check-ignore` in `mark-run` (only matters if `state/` ever moves inside a repository).
- Run the PR comment sampling in parallel (limited by GitHub rate limits anyway).
- An overall time budget for rate-limit retries (today: up to 6 waits of 65 seconds per call).
- Exact review dates for delta runs (one extra API call per PR).
- A read-only, cheap-model summarizer agent definition for a hard tool limit.
- Optional single-word name redaction with a stoplist of tool names.
- Support for GitHub noreply addresses and other alternate identities.
- Short messages instead of tracebacks for configuration errors.
- Better token modelling in `estimate`.

## Known limits

- macOS and Google Chrome only for PDF rendering (the Chrome path is hard-coded).
- PR activity needs `gh`; other code hosts are not supported.
- Only commits by the emails in `authors` are read; other identities show up only as the `possible_missing` count.
- Commit messages are the only free text from git. Repos with poor commit messages produce thin evidence.
- Estimates cover the digests only.
- The skill is built for a single person's career folder, not for teams.

## Guard (repo boundary check)

`python3 scripts/pipeline.py guard DIR [--blocklist FILE]` fails (exit 1) if the repo tree contains private data: any file under `applications/` other than `.gitkeep`, a `state/` folder, files named like private data, PDF, `.bak` or `.log` files, or lines that match the blocklist patterns. It prints paths and line numbers only. Pass your real blocklist (kept outside the repo) with `--blocklist` to check against your own terms.
