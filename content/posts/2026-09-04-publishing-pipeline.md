---
title: The publishing pipeline behind this blog
summary: A static site, a 400-line Python script and zero dependencies — why the boring option wins for a personal engineering blog.
tags: [Tooling, Static Sites, Automation]
date: 2026-09-04
draft: true
---

Every personal blog eventually faces the same fork: adopt a framework, or hand-write
HTML forever. The first buys you a build step, a lockfile, and a dependency tree that
rots the moment you stop looking at it. The second buys you a chore that scales
linearly with the number of posts you write.

This site takes a third option, which is neither clever nor novel — just small.

## The shape of it

Posts are Markdown files. A script turns them into pages. That is the whole design.

```
content/posts/*.md   ->   blog/<slug>/index.html
                          blog/index.html
                          feed.xml
                          index.html  (the three newest cards)
                          outbox/<slug>.txt
```

The script is Python standard library only. No `pip install`, no `node_modules`, no
lockfile to audit. It runs in about 40 milliseconds and its only real job is string
concatenation.

## Why not a static site generator

A generator is the obvious answer, and for most people it is the right one. The
argument against it here is narrow and specific.

| | Framework | This script |
|---|---|---|
| Dependencies | 40–400 packages | 0 |
| Design control | Fight the theme layer | It emits your own markup |
| Breaks when | An upstream major bumps | You edit it |
| Understandable in | An afternoon of docs | One sitting |

That third row is the one that matters. A personal site gets touched maybe six times
a year. The failure mode is not "this is hard to extend" — it is "I opened it after
eight months and the build no longer runs."

> The cost of a dependency is not what it takes to add it. It is what it takes to
> still have it working the next time you look.

The generated pages reuse `style.css` verbatim, so posts inherit the site's design
system rather than approximating it. There is no theme abstraction to fight because
there is no theme.

## The Markdown subset

The parser handles what technical writing actually uses:

- Headings, with generated `id` anchors
- Fenced code blocks with a language class
- Tables, wrapped in their own scroll container so a wide table never widens the page
- Nested lists, blockquotes, images, links, `inline code`, **bold**, *italic*

It does **not** handle footnotes, definition lists, or raw HTML passthrough. Adding
any of those is a ten-line change to one function, made the day it is first needed
rather than the day it might be.

Code spans are extracted before HTML escaping runs, so an example containing
`<script>` renders as text rather than executing — the single most common bug in
hand-rolled Markdown parsers.

## The part that touches the outside world

A post can carry a LinkedIn version after a `--- LINKEDIN ---` marker. The build
writes it to `outbox/`, and that is where it stops.

Publishing is a separate, explicitly invoked command that prints the exact payload,
states that the post will be public, and requires the slug typed back before it
sends anything. Automation drafts. A person publishes.

That asymmetry is deliberate. Generating text is cheap and reversible; putting it in
front of several thousand people is neither.

--- LINKEDIN ---
Every personal blog hits the same fork: adopt a framework, or hand-write HTML forever.

I took a third option for mine — Markdown files and a 400-line Python script with zero dependencies.

The argument isn't that frameworks are bad. It's that a personal site gets touched maybe six times a year, and the real failure mode isn't "hard to extend." It's opening it after eight months and finding the build no longer runs.

Zero dependencies means there is no upstream to rot.

One design decision I'd defend anywhere: the build script drafts the LinkedIn post, but publishing is a separate command that prints the payload and makes you type the slug back before it sends.

Automation drafts. A person publishes.

Generating text is cheap and reversible. Putting it in front of a few thousand people is neither.

Full write-up, including the Markdown-parser bug that bites almost everyone who rolls their own:

{url}
