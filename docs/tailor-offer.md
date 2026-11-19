# tailor-offer

A Claude Code skill that turns one job Offer into an Application: a Fit table, a tailored CV and a cover letter. `skills/tailor-offer/SKILL.md` is the instruction file Claude follows. This page explains the parts you can run yourself.

## How it works

```
 1 Setup          scripts   config, tag list, Evidence IDs present?
 2 Intake         pasted text, or a URL fetched with the harness tool only
 3 Language       script    detect-lang (en / pt); you can override
 4 Estimate       scripts   estimate-files; stops over the cap                 (0 model tokens)
 5 Requirements   cheap model reads the Offer, returns JSON (requirement, tag, priority)
 6 Tags check     script    tags-check; you approve new tags
 7 Fit table      script    fit-status writes Status and Evidence IDs; the model never does
 8 CV             stronger model; every bullet ends with an ev: comment
 9 Cover letter   stronger model; honest about the stack gap
10 Checks         scripts   bullets-check, scrub; you approve or remove bullets with no ID
```

Output goes to `<career_folder>/applications/<slug>/`: `fit-table.md`, `cv-<lang>.md`, `cover-letter-<lang>.md`. The repository's own `applications/` folder stays empty.

## Commands

| Command | What it does |
|---|---|
| `tags-check TAGS REQS` | Checks the requirements JSON (`requirement`, `tag`, `priority` of `must` or `nice`) against the tag list. Prints `unknown tag: x` for a tag that needs your approval, and `alias: a -> b` for rewrites. Exit 1 on an unknown tag or bad structure. |
| `fit-status FIT EVIDENCE TAGS [--relations FILE] [--check]` | Writes Status and Evidence IDs into a Fit table. `--check` writes nothing and fails if the cells differ from the derived values. Exit 1 on an untagged row, an unknown tag, or (with `--check`) a mismatch. |
| `bullets-check CV EVIDENCE` | Lists CV bullets with no `ev:` comment, an unknown ID, a bad marker, or a Personal lab ID without the words "personal lab". Prints line numbers and reasons, never the text. |
| `detect-lang FILE` | Prints `en`, `pt` or `unknown` from stop-word counts. |
| `estimate-files CAP PRICE FILE...` | Token and cost estimate for the files a model step reads. Exit 2 over the cap. |

Run them as `python3 scripts/pipeline.py <command> ...`.

## Status rules

| Status | Rule |
|---|---|
| Yes | At least one Evidence ID of real work whose tags include the row's tag. |
| Partial | No real-work ID, but a Personal lab ID for the tag, or an ID for a related tag (`templates/tag-relations.txt`, pairs written `a ~ b`). |
| No | No Evidence ID. |

A row that mixes things Evidence shows with things it does not (for example "Docker, Kafka") can carry a ruling by you in its Notes cell, `[user-status: Partial]`. The ruling replaces the derived Status; the Evidence IDs stay derived, and `fit-status` prints `overridden=N`. Only you write it, the model never does.

A Personal lab never makes a row Yes. Evidence items without an ID cannot be cited, so run `assign-ids` first.

## Files

| File | Purpose |
|---|---|
| `<career_folder>/state/tags.txt` | Your tag list, seeded from `templates/tags.default.txt`. One lowercase tag per line, then an optional `[aliases]` section of `alias=tag` lines. |
| `templates/tag-relations.txt` | Related tags, one `a ~ b` pair per line. |
| `templates/fit-table.template.md` | Fit table skeleton. |
| `scripts/evidence.py`, `tags.py`, `fit_status.py`, `bullets_check.py`, `lang_detect.py` | Libraries and CLIs behind the commands. `estimate.py` also provides `estimate-files`. |

## CV markers

Each CV bullet ends with `<!-- ev:E0123 -->`, or `<!-- ev:E0123, E0124 -->`. The marker `<!-- ev:user -->` means you approved a bullet that has no Evidence ID. Claude never writes that marker itself.

## Demo

`examples/persona/` holds a fictional persona, one fictional Offer and the three output files. The tests run every check against it, so you can see the expected result without any private data.
