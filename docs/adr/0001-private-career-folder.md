# The Career folder stays outside the public repo

The repo is public and also a portfolio. A real CV, Evidence and Applications name real employers and Offers. We keep them in a private Career folder whose path comes from the user's own config. The repo holds only code, templates and a fictional demo persona. `applications/` exists but stays empty, and a guard script fails the build if private files appear.

Considered: private files inside the repo, hidden by `.gitignore` only. Rejected, because one wrong `git add` would publish them.
