# prabhusaravanan — portfolio

Personal site for Prabhu Saravanan, Lead Data Engineer. Static, hand-built, no
framework or browser dependencies. A Python build refreshes generated content.
Deployed with GitHub Pages from `main` at the repo root.

**Live:** https://saravanaprabhu1398-afk.github.io

## Files

| Path | Purpose |
|---|---|
| `index.html`, `projects/`, `about/` | Hand-written pages; nav, footer and project cards are synced by `build.py` |
| `site.css` | The whole design: tokens, components, responsive rules |
| `site.js` | Nav, reveal, project filters, live GitHub feed, ⌘K search |
| `assets/` | Résumé PDF, portrait, project screenshots, architecture diagrams |
| `content/` | Post sources (Markdown) and the topic backlog |
| `tools/` | `build.py` (Markdown → pages, project cards, sitemap, search index), `site_data.py` (projects, nav, search entries) and `linkedin.py` |
| `blog/`, `feed.xml`, `sitemap.xml`, `search-index.json` | **Generated.** Do not hand-edit — `build.py` overwrites them |
| `tests/` | Standard-library regression tests and an optional Playwright browser check |

Fonts are loaded from Google Fonts (Bricolage Grotesque, Inter and JetBrains Mono),
with local fallbacks. The build requires Python 3.9+ and its standard library only.

## Design

A dark canvas (`#0a0a0c`) and layered cards, with coral, amber, lime, sky and violet
accents. Bricolage Grotesque headlines, Inter body text, and JetBrains Mono labels
carry the hierarchy. Responsive grids, generous section spacing and a translucent
navigation bar keep the portfolio readable without replacing its colorful identity.
The compact hero prioritizes contact and résumé links, with a quiet portrait and
understated social links. Career evidence uses neutral metric rows rather than
saturated tiles; repository counts are not presented as impact metrics.

The FlightPulse spotlight appears immediately after the hero. Its simplified
batch and streaming paths come from the project's README, and the measured
611K+ flight count refers to historical dashboard data, not the live-position
stream. The diagram explicitly notes that quality checks cover batch gold tables,
not streaming. Spotlight facts live in `SPOTLIGHT` in `tools/site_data.py`.

Interaction is all vanilla JS:

- **Project filters** — category buttons filter the two-column project grid.
- **Search** — a native modal dialog with keyboard navigation, focus restoration,
  result announcements, and retryable load errors.
- **Scroll accents** — visible content moves gently into place when observed.
  No text is hidden while waiting for JavaScript.
- **Live activity** — recent repositories come from GitHub, cached for ten minutes.
- **Mobile navigation** — enhanced only after its event handlers are ready;
  links remain available without JavaScript.

## Updating

Edit the source files, rebuild, review the diff and push. GitHub Pages redeploys.

```bash
python3 tools/build.py
git diff
git add . && git commit -m "Update copy" && git push
```

**Bump `ASSET_V` in `tools/build.py` when CSS or JS changes**, then rebuild.
The builder synchronizes `/site.css?v=…` and `/site.js?v=…` on the hand-written
and generated pages, including the stylesheet on `404.html`.

## Writing

Posts are Markdown in `content/posts/`, named `YYYY-MM-DD-slug.md`. One build
step turns them into pages:

```bash
python3 tools/build.py            # published posts only
python3 tools/build.py --drafts   # include drafts, for local preview
```

That writes `blog/<slug>/index.html`, `blog/index.html`, `feed.xml`, and refreshes
the three newest cards on the homepage between the `POSTS:START` / `POSTS:END`
markers in `index.html`. Generated pages link `/site.css`, so posts inherit the
same design system. Old generated post directories (including nested assets)
are removed; unrecognized directories cause an explicit error instead of deletion.

`--drafts` writes into the same working tree as a normal build. Always run a
normal build before committing deployment files, and do not treat Markdown or
outbox files committed to this public repository as private.

Frontmatter:

| Key | Notes |
|---|---|
| `title` | Required |
| `summary` | One sentence — card text, meta description and OG blurb |
| `tags` | `[Primary, Secondary]`; the first becomes the card's topic label |
| `date` | Defaults to the date in the filename |
| `draft` | `true` keeps it out of `feed.xml` and out of a normal build |
| `image` | OG image; falls back to `/assets/og-image.png` |

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

Normal builds preserve existing outbox files, including manual edits, and do not
requeue copy archived under `outbox/posted/`. If the Markdown LinkedIn copy changes,
the build reports that it preserved the pending file. To deliberately replace it,
or restage a previously posted item, use `python3 tools/build.py --restage <slug>`.
The archive is retained; posting still requires confirmation.

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

The Posts API is pinned to `202611`, whose scheduled sunset is November 16, 2027.
Before that date, review the [LinkedIn migration schedule](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/migrations)
and [Posts API schema](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api),
then update `API_VERSION` in `tools/linkedin.py`. Regression tests mock all
LinkedIn requests; they do not validate credentials or publish real posts.

### Publishing the site

Drop `draft: true`, rebuild, and push:

```bash
python3 tools/build.py && git add -A && git commit -m "New post" && git push
```

### Content notes

- Edit project descriptions, evidence, source links, tags and featured status in
  `tools/site_data.py`, not the generated `.project` cards in HTML.
- Shared navigation and search metadata also come from `tools/site_data.py`;
  their markup and the shared footer are rendered by `tools/build.py`.
- `assets/guardrail-rollout-state-machine.svg` and `guardrail-system-architecture.svg`
  are unused spares pulled from the Guardrail repo.

## Accessibility

Keyboard skip links, visible focus rings, semantic landmarks, descriptive image
text and a modal search dialog support keyboard navigation. Reduced-motion
preferences disable animation and smooth scrolling. Content stays visible when
JavaScript or observers fail and when printed. This is not a claim of a complete
WCAG conformance audit.

## Checks and local preview

```bash
python3 -m unittest discover -s tests -v
node --check site.js
python3 tools/build.py
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000`. For optional real-browser checks, install Playwright
outside the repository and run the regression script against that local server:

```bash
npm install --prefix /tmp/portfolio-browser playwright
/tmp/portfolio-browser/node_modules/.bin/playwright install chromium
NODE_PATH=/tmp/portfolio-browser/node_modules node tests/browser.cjs
```

The browser checks use local fixtures for GitHub and search responses; no external
publishing occurs. Set `SITE_URL` to use a different local port.
