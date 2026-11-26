# search-offers

A Claude Code skill that ranks several Offers at once. You paste a digest (for example a job-alert email with a few roles) and get a shortlist ordered by how much of each Offer your Evidence supports. `skills/search-offers/SKILL.md` is the instruction file Claude follows. This page explains the parts you can run yourself.

It does not search the web and does not fetch listing sites. You bring the text, so no proxy or site rule is in play. It runs on a `client` and a `personal` machine.

## How it works

```
 1 Setup        scripts   config, tag list seeded from the default
 2 Intake       you       paste the digest; it is data, instructions inside it are ignored
 3 Estimate     scripts   estimate-files; stops over the cap                  (0 model tokens)
 4 Offers       cheap model reads the digest, returns each Offer's requirements as JSON
 5 Rank         script    rank-offers: Status per requirement, score, dedup   (0 model tokens)
 6 Shortlist    script    writes <career_folder>/offers/shortlist-<date>.md
```

Pick the Offers worth the effort from the shortlist, then run `tailor-offer` on each.

## Commands

| Command | What it does |
|---|---|
| `rank-offers OFFERS EVIDENCE TAGS [--out FILE] [--json]` (`scripts/rank_offers.py`) | Reads the Offers JSON, derives each requirement's Status with the same rules as `fit-status`, scores and ranks the Offers. Prints a Markdown table, writes it to `--out` (mode 600), or prints JSON with `--json`. Exit 1 on an unknown tag (listed per Offer, nothing written), a missing file or a bad field (the message names the field, never its value). |

The Offers JSON is `{"offers": [{"slug", "title", "company", "url", "requirements": [{"requirement", "tag", "priority"}]}]}`. A worked example is `examples/persona/offers.json`, with the digest it comes from in `examples/persona/digest.md`.

## The score

- Weight: Must 2, Nice 1.
- Credit: Yes 1, Partial 0.5, No 0. A Personal lab gives Partial at most.
- Not evidenced rows (seniority, language level, remote and so on) are left out of the score, because Evidence cannot show them. If every row is Not evidenced the score is `—` and the Offer sorts last.
- Score = credit earned divided by weight possible, as a percent. Ties keep the digest order.
- Biggest Must gap: the first Must row with Status No, else the first with Partial.
- An Offer scored from fewer than 4 rows is `(thin)`: it sorts after the others, because a score from two requirements is a weak signal. The `Rows` column shows how many rows were scored.
- Work-mode and level tags (`onsite`, `hybrid`, `mid-level`, `remote`, `senior`) are in `templates/non-skill-tags.txt`, so they read Not evidenced instead of a gap. `company` may be null.
- Offers with the same URL, or the same company and title, count once.

The score says how much of an Offer your Evidence supports. It does not say the Offer is good. Untagged Evidence lowers scores; run `tag-evidence` first (see [refresh-evidence](refresh-evidence.md)).
