# Demo persona

Everything here is fictional: the person, the employers, the Offer and the evidence.

| File | What it is |
|---|---|
| `cv-en.md` | The persona's Base CV |
| `evidence.example.md` | Evidence with IDs and tags, including one Personal lab |
| `offers/offer-01-en.md` | A fictional Offer |
| `requirements.json` | The requirements a cheap model would extract from the Offer |
| `output/` | The Application: `fit-table.md`, `cv-en.md`, `cover-letter-en.md` |

The tag list is `templates/tags.default.txt`. The tests in `tests/test_demo_persona.py` run `tags-check`, `fit-status --check`, `bullets-check` and the example blocklist scrub against these files.
