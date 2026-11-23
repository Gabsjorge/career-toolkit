# career-toolkit

Claude Code skills that help one person keep a CV and cover letter current, turn each job Offer into an Application (Fit table, tailored CV, cover letter), and keep a Study plan aligned with the market.

It is also a portfolio piece: it shows AI used in a measured, safe way. Scripts do the extraction, counting and checking; a cheap model reads Offers; a stronger model writes wording; every claim in a CV traces to an Evidence ID.

Terms such as Offer, Evidence and Fit table are defined in [CONTEXT.md](CONTEXT.md).

## Status

| Skill | State |
|---|---|
| `refresh-evidence` | available, with Evidence IDs and a machine gate; see [docs/refresh-evidence.md](docs/refresh-evidence.md) |
| `tailor-offer` | available; see [docs/tailor-offer.md](docs/tailor-offer.md) and the demo in [examples/persona](examples/persona) |
| `study-plan` | available, pending a live test; see [docs/study-plan.md](docs/study-plan.md) |
| `search-offers` | reserved |

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
