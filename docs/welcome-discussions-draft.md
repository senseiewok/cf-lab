# Welcome to Sensei Ewok's CF Lab Discussions

Hello, and welcome.

Sensei Ewok's CF Lab is an independent software lab dedicated to building open research tools and examining evidence around cystic fibrosis. Everything here is open source, built in public on donated time, and published where anyone can inspect it.

This lab is not a clinic, medical practice, or charity, and it is not affiliated with the Cystic Fibrosis Foundation. This is an independent lab; its work is research, not medical advice. Nothing written here is clinical advice, and nothing we build promises a cure, a treatment timeline, or medical access. To people living with CF and those who care alongside them: you deserve care, dignity, and room for ordinary life. You do not owe anyone an inspiring story.

## Why this space exists

We opened this Discussions space as a quiet, welcoming porch for conversation. Here is what this space is for:

- **Research questions:** Asking about our open tools, the CFTR 3D model, the trial endpoint atlas, or how we read primary literature.
- **Data integrity and sources:** Pointing out typos, broken citations, new open-access papers, or data catalog entries we should review.
- **Tooling and AI workflows:** Discussing the multi-agent AI verification loop, local model benchmarking, or zero-build web standards.
- **Clarity and plain language:** Sharing thoughts on explainers and how we can make scientific evidence clearer.

## What to expect

Because this is a one-person project running on nights and weekends, replies may take a little time. We prioritize thoughtful, grounded answers backed by evidence over fast responses.

If you have a question, an observation, or a correction, please feel free to start a discussion. We are glad you are here.

---

### Maintainer Instructions for Posting (T-0093 Acceptance Check)

1. Review and approve the welcome note text above.
2. Go to the repository Discussions page on GitHub: https://github.com/senseiewok/cf-lab/discussions
3. Click **New discussion**, select the **General** (or **Announcements**) category, set the title to `Welcome to Sensei Ewok's CF Lab Discussions`, paste the text above, and click **Start discussion**.
4. Verify acceptance by running:
   ```powershell
   gh api graphql -f query='{repository(owner:\"senseiewok\",name:\"cf-lab\"){discussions(first:5){totalCount nodes{title url}}}}'
   ```
   Confirm that `totalCount` is 1 or greater and that the README Discussions link leads to the posted welcome note.
