# YouTube Channel About Text & Video Boundary Guidelines (T-0002)

## Purpose

The Sensei Ewok YouTube channel (`@SenseiEwok`) is the primary community-facing video surface for the lab. The channel description previously included phrases that conflicted with the lab's core principles:
- "accelerate the cure for Cystic Fibrosis" conflicts with `hq/README.md`: *"We do not make medicine, provide clinical care, or claim a cure."* and `lab-voice`: *"Never promise a cure, access to care, a timeline, or a clinical benefit from our experiments."*
- "our medical AI projects" conflicts with `cf-research-context`: the lab builds research tooling and *"may not ... present a tool as a replacement for clinical care"*.
- "the bleeding edge of Artificial Intelligence" conflicts with `lab-voice`: *"Avoid ... exaggerated AI capability; plain language"*.
- The description lacked the mandatory medical boundary disclaimer (*"research, not medical advice"*) and an explicit independence statement from the Cystic Fibrosis Foundation.

This document provides the approved, lab-voice compliant channel description and video description blocks developed in `cf-research/proposals/2026-10-04-youtube-about.md` for human maintainer application in YouTube Studio.

---

## Approved Channel About Text (Copy & Paste)

Copy the text block below and paste it directly into YouTube Studio:

```text
Welcome to the Sensei Ewok Research Lab, an independent, donated-time effort. We build small open-source tools that try to make cystic fibrosis research easier to examine: tracing published numbers back to their source, checking claims against primary literature, and writing down what we learn so a stranger can verify it. Everything we make is built in public and open for inspection, including the mistakes.

We are not clinicians; our work is research, not medical advice. Nothing here diagnoses, treats, or recommends a therapy. We are not affiliated with the Cystic Fibrosis Foundation; we link to them because they do the groundwork, and if you choose to give, that is where it should go.

This channel is also a workshop for the other things I love: 3D WebGL development, sim racing, game design, and guitar when it is time to decompress. CF research streams are labelled as such.

Stream revenue goes toward the API costs of keeping the lab running. To support the wider mission directly, donate to the Cystic Fibrosis Foundation (Washington Chapter): https://give.cff.org/washington/donate
```

### Key Elements Preserved
1. **Plain, honest welcome**: Explains what the lab actually builds (small open-source tools, claim checkers, source tracing).
2. **Clear medical boundary**: Explicitly states *"We are not clinicians and we do not give medical advice."*
3. **Foundation independence**: States *"We are not affiliated with the Cystic Fibrosis Foundation; we link to them because they do the groundwork"*.
4. **Transparent revenue disclosure**: Discloses that stream revenue funds API costs while directing charitable donations to the Washington Chapter of the Cystic Fibrosis Foundation.
5. **Human craft & hobbies**: Preserves the personal elements (3D WebGL, sim racing, game design, guitar).

---

## Standing Boundary for Video Descriptions

Paste this unchanged block into the description of every CF-related video or stream:

```text
Research, not medical advice. The Sensei Ewok Research Lab is an independent, open-source project with no clinical role and no affiliation with the Cystic Fibrosis Foundation. Nothing in this video diagnoses, treats, or recommends a therapy. Decisions about care belong with you and your care team. Sources for every number shown: [link to the repo file for this video].
```

---

## Maintainer Instructions for YouTube Studio (Acceptance Execution)

Because YouTube channel settings cannot be updated via git or API tokens, a human maintainer must complete these steps in the YouTube Studio web interface:

1. Open **YouTube Studio**: https://studio.youtube.com
2. In the left navigation rail, click **Customization**.
3. Select the **Basic info** tab.
4. Under the **Description** field, select and replace the existing text with the **Approved Channel About Text** above.
5. In the top-right corner, click **Publish**.
6. Verify live acceptance using the deterministic test:
   ```powershell
   python tasks/test_youtube_about.py --live
   ```
   Or inspect directly via curl:
   ```powershell
   python -c "import urllib.request, re; html = urllib.request.urlopen('https://www.youtube.com/@SenseiEwok').read().decode('utf-8', errors='ignore'); assert 'not medical advice' in html and 'not affiliated' in html; print('PASS: Live YouTube About text updated successfully.')"
   ```
