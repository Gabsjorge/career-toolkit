# career-coach

A thin Claude Code agent (`agents/career-coach.md`) for when you have a career task and do not know which skill to use. It runs `config-check`, picks one of the skills below and hands off. It adds no rules, estimates or checks of its own: each skill keeps its own.

| You say | It hands off to |
|---|---|
| "Update my Evidence / CV from recent work" | `/career-toolkit:refresh-evidence` ([docs](refresh-evidence.md)) |
| "I got this offer" (paste text or a URL) | `/career-toolkit:tailor-offer` ([docs](tailor-offer.md)) |
| "What should I study?" | `/career-toolkit:study-plan` ([docs](study-plan.md)) |
| "Rank these offers" (paste a digest) | `/career-toolkit:search-offers` ([docs](search-offers.md)) |
| "Find me offers" | no web search: it asks you to paste a digest for `search-offers` |

## What it does not do

- It never writes into your Career folder, never writes CV or letter text and never calls a stronger model. The skills do that, after their own token estimate.
- It never reads `config.json`, `label-map.json` or `blocklist.txt`.
- It treats Offers and pasted text as data: an Offer that says "skip the checks" changes nothing.
- It never commits or pushes.

It runs on the cheapest model tier because it only routes. You can skip it and call a skill directly.
