# prabhusaravanan — portfolio

Personal site for Prabhu Saravanan, Lead Data Engineer. Static, hand-built, no
framework and no build step. Deployed with GitHub Pages from `main` at the repo root.

**Live:** https://saravanaprabhu1398-afk.github.io

## Files

| Path | Purpose |
|---|---|
| `index.html` | The whole site — single page, semantic sections |
| `style.css` | Design system and all styling |
| `script.js` | Scroll behaviour, card stack, pipeline scrub, accordion, text reveals |
| `assets/` | Résumé PDF, portrait, project screenshots, architecture diagrams |
| `blog.css` | Article typography — loaded only under `/blog/` |
| `content/` | Post sources (Markdown) and the topic backlog |
| `tools/` | `build.py` (Markdown → pages) and `linkedin.py` (gated publishing) |
| `blog/`, `feed.xml` | **Generated.** Do not hand-edit — `build.py` overwrites them |

No dependencies beyond Google Fonts (Archivo + JetBrains Mono). The build is
Python standard library only — nothing to install.

## Design

Two tones that invert between bands — `#080807` and `#E8E8E3` — with a translucent
"liquid glass" surface layer over an animated ambient light field. Type is Archivo
at weight 500 with tight negative tracking; JetBrains Mono for small uppercase labels.

Interaction is all vanilla JS:

- **Card stack** — projects are `position: sticky` at staggered offsets, scaling and
  dimming as each is covered. Progress is measured from the *next* card closing in,
  since a sticky element never scrolls past its own stick point.
- **Pinned pipeline** — a 340vh section pins a viewport-height panel and scrubs the
  Source → Serve stages against scroll position.
- **Text reveals** — words are individually masked and rise on scroll. Words stay in
  normal flow, so the browser controls line breaking; measurement only sets stagger.
- **Pointer response** — a radial highlight tracks the cursor across glass surfaces.

## Updating

Edit the files and push. GitHub Pages redeploys automatically.

```bash
git add . && git commit -m "Update copy" && git push
```

**Bump the asset version when you change CSS or JS.** `index.html` links
`style.css?v=5` and `script.js?v=5` — increment both, or returning visitors keep
getting cached stale files.

## Writing

Posts are Markdown in `content/posts/`, named `YYYY-MM-DD-slug.md`. One build
step turns them into pages:

```bash
python3 tools/build.py            # published posts only
python3 tools/build.py --drafts   # include drafts, for local preview
```

That writes `blog/<slug>/index.html`, `blog/index.html`, `feed.xml`, and refreshes
the three newest cards on the homepage between the `POSTS:START` / `POSTS:END`
markers in `index.html`. Generated pages link `/style.css` and `/blog.css`, so
posts inherit the design system rather than approximating it.

Frontmatter:

| Key | Notes |
|---|---|
| `title` | Required |
| `summary` | One sentence — card text, meta description and OG blurb |
| `tags` | `[Primary, Secondary]`; the first becomes the card's topic label |
| `date` | Defaults to the date in the filename |
| `draft` | `true` keeps it out of `feed.xml` and out of a normal build |
| `image` | OG image; falls back to the FlightPulse screenshot |

Markdown support is a deliberate subset: headings with anchor ids, fenced code,
tables (wrapped in their own scroll box), nested lists, blockquotes, images,
links, inline code, bold, italic. Adding more is a small change to one function
in `tools/build.py`.

### Drafting

`/draft-post` takes the first unchecked item from `content/topics.md`, drafts it
with `draft: true`, writes a LinkedIn version, and rebuilds. It publishes nothing.

### Publishing to LinkedIn

Everything after `--- LINKEDIN ---` in a post is staged to `outbox/<slug>.txt`.
Staging is not posting.

```bash
python3 tools/linkedin.py auth            # one-time; tokens last 60 days
python3 tools/linkedin.py whoami          # is the token still alive?
python3 tools/linkedin.py preview <slug>  # prints the exact payload, posts nothing
python3 tools/linkedin.py post <slug>     # asks you to type the slug back first
```

Credentials go in `tools/.env` (copy `tools/.env.example`). That file and the
stored token are gitignored — check before committing.

One-time app setup at [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps):
create an app against a LinkedIn Page you admin, request the **Share on LinkedIn**
and **Sign In with LinkedIn using OpenID Connect** products (both self-serve), and
register `http://localhost:8000/callback` as a redirect URL.

### Publishing the site

Drop `draft: true`, rebuild, and push:

```bash
python3 tools/build.py && git add -A && git commit -m "New post" && git push
```

### Content notes

- Project cards live in the `#work` section as `<article class="work-row stack-card">`.
  Each needs a visual, a mono index (`01/04`), a metric chip, and tags.
- The Clinical Document Intelligence repo is private, so its card reads
  "available on request". If it goes public, swap that span for a link.
- `assets/guardrail-rollout-state-machine.svg` and `guardrail-system-architecture.svg`
  are unused spares pulled from the Guardrail repo.

## Accessibility

Every text tier meets WCAG AA against its background, including composited through
the glass layers. Keyboard skip link, visible focus rings, semantic landmarks, and
alt text throughout. All motion is gated behind `prefers-reduced-motion`, and no
content depends on an animation or observer firing to become visible.
