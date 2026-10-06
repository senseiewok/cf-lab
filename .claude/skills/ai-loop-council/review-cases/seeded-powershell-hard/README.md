# Seeded PowerShell review case, harder set

Seven scripts with **one subtle planted defect each**, plus two clean scripts. Each defect was demonstrated by running its logic before it was planted (`truth.json` lists them). Unlike `../seeded-powershell/`, these are logic and PowerShell-semantics bugs, not obvious security smells, so there is room for one reviewer to find what another misses.

**Do not run these scripts.** They are test data, read only as text, and some would delete files or tag a build if executed.
