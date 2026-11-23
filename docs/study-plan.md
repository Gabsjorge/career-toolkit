# study-plan

A Claude Code skill that builds a Study plan with two tracks, Senior Backend and Tech Lead / Architect, from the gaps in your Fit tables. `skills/study-plan/SKILL.md` is the instruction file Claude follows. This page explains the parts you can run yourself.

## How it works

```
 1 Setup        scripts   config, track map seeded from the default
 2 Count        script    gap-count over every applications/*/fit-table.md   (0 model tokens)
 3 Unmapped     you       give each unmapped tag a track and a type
 4 Estimate     scripts   estimate-files; stops over the cap                 (0 model tokens)
 5 Plan         stronger model writes reasons, resources, order, "done when" from the JSON
 6 Output       first run writes a new study-plan.md; later runs back up, then overwrite
 7 Check        script    gap-count --check; numbers in the plan must match the JSON
 8 Links, labs  harness fetch only; links stay (unchecked) unless fetched; labs proposed as text
```

The first run writes `<career_folder>/docs/study-plan.md` and leaves your own `level-career-up.md` untouched. Later runs update `study-plan.md` after a backup.

## Commands

| Command | What it does |
|---|---|
| `gap-count APPS TRACKS [--check PLAN]` (`scripts/gap_count.py`) | Reads `APPS/*/fit-table.md` and prints JSON per track: `tag`, `type`, `gaps`, `no`, `partial`, `must_weighted`, `tables` (how many Offers asked for it). With `--check`, compares the number rows of a plan (`\| track \| tag \| gaps \| weighted \| offers \|`) with the counted values and prints `OK` or the `track/tag` that differ. Exit 1 on a bad tag map, a missing folder or a mismatch. |

## What counts as a gap

- A row with Status Partial or No. Yes, Not evidenced and untagged rows are not gaps.
- Weight: Must counts 2. Nice, and an unknown Must/Nice (`—`, as in tables backfilled from the old format), count 1.
- The JSON also holds `tables_read`, `tables_skipped` (a table that cannot be read whole, by folder name), `rows`, `untagged_rows` and `unmapped_tags`. Nothing is guessed: a tag with no track is listed, not assigned.

## The track map

`templates/tag-tracks.default.txt` is copied once to `<career_folder>/state/tag-tracks.txt`, which you edit. One line per tag: `tag = track, type`.

- Track: `backend`, `lead` or `backend+lead` (the tag counts in both tracks).
- Type: `tech`, `skill` or `language`.
- Non-skill tags (`templates/non-skill-tags.txt`) are not mapped.

A bad line is reported by number, never by value.

## Links and labs

The model marks every resource link `(unchecked)`. It changes that only when the harness fetch tool loaded the page. A finished Personal lab is proposed as an Evidence item (`kind: lab`) in text; you approve the wording and add it with `refresh-evidence`.
