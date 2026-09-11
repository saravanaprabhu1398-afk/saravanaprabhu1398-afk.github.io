---
description: Draft the next blog post from the topic backlog, build it locally, and stage a LinkedIn version. Publishes nothing.
---

Draft one blog post for this site. **Publish nothing.** No `git push`, no
`linkedin.py post`. The output of this command is a local draft for review.

## 1. Pick the topic

If the user named a topic in `$ARGUMENTS`, use that. Otherwise read
`content/topics.md` and take the **first unchecked** item in the Queue.

If the queue is empty, stop and say so rather than inventing a topic.

## 2. Ground it before writing

Do not write from the title alone — that is how a post ends up generic. First:

- Read the relevant parts of `index.html` for how this work is already described.
- If the topic names one of the user's repos (FlightPulse, Guardrail), look at it.
- Where you need a fact you do not have — a number, an incident, a config detail —
  **ask the user rather than inventing one.** A fabricated metric in a post under
  their name is worse than a thinner post. Collect the questions and ask them in
  one batch before drafting, not one at a time.

## 3. Voice

Match the site's existing copy, which is:

- Declarative and concrete. Specific numbers, named tools, real failure modes.
- Willing to say what did not work. The interesting part is usually the failure.
- No hype vocabulary — no "game-changing", "leverage", "unlock", "in today's
  fast-paced world", no rhetorical-question openers.
- Short paragraphs. One idea each. Em dashes are fine; the site uses them.
- Opinions with reasons attached, not opinions as decoration.

Length: 800–1400 words. A post that earns 700 words should be 700 words.

## 4. Write the file

`content/posts/<YYYY-MM-DD>-<slug>.md`, dated today:

```markdown
---
title: Sentence case, specific, no colon-subtitle pattern
summary: One sentence. This becomes the card, the meta description and the OG blurb.
tags: [Primary, Secondary]
date: YYYY-MM-DD
draft: true
---

Body in Markdown. Supported: headings, fenced code with a language,
tables, nested lists, blockquotes, images, links, `inline code`,
**bold**, *italic*.

--- LINKEDIN ---
The LinkedIn version. Not a summary of the post — a piece that stands
on its own and happens to link to it.
```

**Always set `draft: true`.** The user flips it, not you.

### The LinkedIn section

Rules that come from the platform, not from taste:

- Under 3000 characters. Aim for 900–1500.
- The first two lines are all anyone sees before "see more". Put the sharpest
  claim there. Never open with "I'm excited to share".
- Single-sentence paragraphs, blank line between. Dense blocks do not get read.
- No markdown — LinkedIn renders it literally. Plain text only.
- 3–5 hashtags at most, on their own line, specific over broad
  (`#DataEngineering` `#Lakehouse`, not `#Tech` `#Innovation`).
- End with `{url}` on its own final line. The build substitutes the real post
  URL, and `linkedin.py` turns a trailing bare URL into a link card.

## 5. Build and update the queue

```bash
python3 tools/build.py --drafts
```

Then tick the item in `content/topics.md` (`- [ ]` → `- [x]`) and move it to the
Published section only once the user actually publishes it.

## 6. Report

Tell the user:

- The file path, word count and read time
- The LinkedIn draft's character count
- Any fact you asked about and any assumption you had to make
- These two commands, without running either:

```bash
python3 tools/linkedin.py preview <slug>
```

To publish: they remove `draft: true`, rebuild, commit and push the site; and run
`python3 tools/linkedin.py post <slug>` themselves. Do not run those for them
unless they ask in that same message.
