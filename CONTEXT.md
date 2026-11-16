# Career toolkit

Skills that keep one person's CV and cover letter current, turn each job offer into a tailored application, and keep a study plan aligned with the market.

## Language

**Base CV**:
The files `cv-en.md` and `cv-pt.md` in the career folder. Every tailored CV starts from them.
_Avoid_: Master CV, template CV, Back_* files

**Offer**:
One job posting the user shares for analysis.
_Avoid_: Job, vacancy, opportunity

**Application**:
The folder `applications/<slug>/` for one Offer. It holds the Fit table, a tailored CV and a cover letter.
_Avoid_: Submission

**Fit table**:
A table of the Offer's requirements, each marked Yes, Partial or No against the user's evidence, with a study note per row.
_Avoid_: Gap analysis, match report

**Evidence**:
Anonymized, approved items about work the user did. Every claim in a CV or letter must trace to Evidence.
_Avoid_: Experience notes

**Evidence ID**:
A permanent sequential ID (`E0001`) on one Evidence item. It never changes and is never reused.
_Avoid_: Evidence hash, item number

**Personal lab**:
A public practice repo the user built and approved as Evidence. It is labeled "personal lab" and never "production".
_Avoid_: Side project, course item

**Tag**:
A name from the user's controlled tag list, for example `kafka`. Fit table rows and Evidence items use it, so gaps can be counted.
_Avoid_: Keyword, skill name

**Status**:
The mark on a Fit table row. Yes needs an Evidence ID that shows the Tag in real work. Partial needs an Evidence ID for a related Tag. No means no Evidence ID.
_Avoid_: Score, match level

**Machine flag**:
The config value `client` or `personal`. On `client`, the refresh skill stays off until the user turns it on.
_Avoid_: Mode, profile

**Study plan**:
The document `docs/level-career-up.md`. It ranks what to learn in two tracks, one per Target role, driven by gaps repeated across Fit tables.
_Avoid_: Roadmap, curriculum

**Target role**:
The role the user names as the goal. It limits which gaps the Study plan chases. There are two: Senior Backend Developer (deepen now) and Tech Lead / Software Architect (the later step).
_Avoid_: Dream job

**Career folder**:
The user's private folder that holds the Base CV, Evidence, Applications and the Study plan. It is never part of the public repo.
_Avoid_: Workspace, vault
