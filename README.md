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

No dependencies beyond Google Fonts (Archivo + JetBrains Mono).

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
