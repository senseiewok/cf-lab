# Visual QA sweep

A frugal way to check how a set of pages looks: measure first, look at small crops, and spend one advanced-model call at the end. Pass or fail still comes from a measurement, not from a model saying "looks fine".

## Steps

| Step | What | Cost |
| --- | --- | --- |
| 1. Measure | In the browser, per page and width: horizontal overflow, text covered by positioned elements (overlap area in px²), console errors, failed requests, title, robots meta. `scripts/observe-page.py` covers most of these. | Script only |
| 2. Widths | Phone 390, tablet 820, desktop 1280. Emulate touch (`touch: true`) wherever a control appears only on touch screens. | Script only |
| 3. Crop | Screenshot tight crops of the parts in question (a selector or a clip), not whole pages. `scripts/pr-screenshots.py capture --topic <topic>` keeps each under a size cap and saves them in the dated folder `<lab files>/scratch/screenshots/<YYYY-MM-DD>/<topic>/` (`pr-screenshots.py where <topic>` prints it), so a later task can reuse them. | Small files |
| 4. Triage | A local vision model may sort the crops into "look again" and "fine". In one local run, images were downscaled hard and misses were common; treat a local "fine" as weak evidence. | Local |
| 5. One look | ONE advanced-model call with several images at once: the flagged crops plus a few random controls, the page's purpose, and the measurements from step 1. Ask for findings that name the image and the region. | One call |
| 6. Confirm | Accept a visual finding only with a measurement or a second look at the same crop. Fix, then measure again. | Script only |

Screenshots can hold personal data, and a cloud call sends them off the machine. Capture only pages that may be public, under the normal approval rules.

## Worked example (2026-10-11)

A number bubble that appears only on touch screens sat over text. A check without touch emulation cannot see it. The figures below are a one-off measurement, not a benchmark.

- **Before the fix:** the bubble covered 906 px² of text, measured in each of four layouts.
- **After the fix:** 0 px² in the same four layouts.

One way to measure it: intersect the bubble's `getBoundingClientRect()` with each text element's and add the areas. A number like this lets a reviewer accept the finding without trusting a model's eye.
