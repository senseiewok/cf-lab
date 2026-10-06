# Seeded PowerShell review case

These scripts contain **planted defects** (credentials on a command line, disabled certificate checks, an unguarded delete, remote code execution, and similar) so that `scripts/review-diversity.ps1` can count how many a reviewer finds. `truth.json` lists them. The `clean-*.ps1` scripts have none and measure false alarms.

**Do not run these scripts.** They are test data, read only as text. Nothing in this repo executes them, and they are not examples to copy.
