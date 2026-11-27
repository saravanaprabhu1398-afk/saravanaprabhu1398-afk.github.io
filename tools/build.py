#!/usr/bin/env python3
"""
Build the blog from Markdown.

Reads  content/posts/*.md
Writes blog/<slug>/index.html   one page per post, styled to match the site
       blog/index.html          the writing index
       feed.xml                 RSS 2.0
       index.html               refreshes the #blog cards between markers
       outbox/<slug>.txt        LinkedIn draft, if the post carries one

No third-party packages. Python 3.9+.

    python3 tools/build.py            # published posts only
    python3 tools/build.py --drafts   # include drafts (local preview)
"""

import argparse
import html
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import site_data as SD
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
BLOG_DIR = ROOT / "blog"
OUTBOX = ROOT / "outbox"
INDEX = ROOT / "index.html"
FEED = ROOT / "feed.xml"

SITE = "https://saravanaprabhu1398-afk.github.io"
AUTHOR = "Prabhu Saravanan"
ROLE = "Lead Data Engineer"
ASSET_V = "15"
FONT_PRELOAD = '<link rel="preload" href="/assets/fonts/bricolage-grotesque-latin-wght.woff2" as="font" type="font/woff2" crossorigin>'
HAND_PRELOAD = '<link rel="preload" href="/assets/fonts/caveat-latin-wght.woff2" as="font" type="font/woff2" crossorigin>'
# The favicon matches the "ps" brand badge in the navigation.
FAVICON = ('<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'%3E'
           '%3Crect width=\'32\' height=\'32\' rx=\'16\' fill=\'%2320232c\'/%3E%3Ctext x=\'16\' y=\'21\' '
           'font-family=\'Helvetica,Arial,sans-serif\' font-size=\'14\' font-weight=\'700\' fill=\'%23ffffff\' '
           'text-anchor=\'middle\'%3Eps%3C/text%3E%3C/svg%3E">')
DEFAULT_OG = "https://saravanaprabhu1398-afk.github.io/assets/og-image.png"

LINKEDIN_MARKER = re.compile(r'^-{3,}\s*LINKEDIN\s*-{3,}\s*$', re.M)
WORDS_PER_MIN = 220


# ---------------------------------------------------------------------------
# Markdown — a deliberate subset: headings, code, quotes, lists, tables,
# rules, images, links, bold, italic, inline code.
# ---------------------------------------------------------------------------

LIST_RE = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$')
HR_RE = re.compile(r'^\s*([-*_])\s*(?:\1\s*){2,}$')
HEAD_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
TABLE_SEP_RE = re.compile(r'^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$')


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text or "section"


def inline(text):
    """Inline spans. Code is stashed first so nothing rewrites its insides."""
    stash = []

    def keep(m):
        stash.append(m.group(1))
        return f"\x00{len(stash) - 1}\x00"

    text = re.sub(r'`([^`]+)`', keep, text)
    text = html.escape(text, quote=False)

    text = re.sub(
        r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)',
        lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}"'
                  + (f' title="{m.group(3)}"' if m.group(3) else '') + '>',
        text)

    def link(m):
        href = m.group(2)
        ext = href.startswith(("http://", "https://")) and SITE not in href
        attrs = ' target="_blank" rel="noopener"' if ext else ''
        return f'<a href="{href}"{attrs}>{m.group(1)}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'\x00(\d+)\x00',
                  lambda m: '<code>' + html.escape(stash[int(m.group(1))]) + '</code>',
                  text)
    return text


def parse_table(lines, i, n, out):
    def cells(row):
        row = row.strip().strip('|')
        return [c.strip() for c in row.split('|')]

    header = cells(lines[i])
    aligns = []
    for spec in cells(lines[i + 1]):
        left, right = spec.startswith(':'), spec.endswith(':')
        aligns.append('center' if left and right else 'right' if right else 'left')
    i += 2

    body = []
    while i < n and lines[i].strip() and '|' in lines[i]:
        body.append(cells(lines[i]))
        i += 1

    # An empty top-left header cell marks the first column as row labels.
    row_labels = bool(header) and header[0] == ''

    def row(vals, head=False):
        out_cells = []
        for k, v in enumerate(vals):
            align = aligns[k] if k < len(aligns) else 'left'
            style = f' style="text-align:{align}"' if align != 'left' else ''
            if head:
                tag, scope = 'th', ' scope="col"' if v else ''
            elif row_labels and k == 0:
                tag, scope = 'th', ' scope="row"'
            else:
                tag, scope = 'td', ''
            out_cells.append(f'<{tag}{scope}{style}>{inline(v)}</{tag}>')
        return '<tr>' + ''.join(out_cells) + '</tr>'

    parts = ['<div class="table-scroll"><table><thead>', row(header, head=True),
             '</thead><tbody>']
    parts += [row(r) for r in body]
    parts.append('</tbody></table></div>')
    out.append(''.join(parts))
    return i


def parse_list(lines, i, n, out):
    first = LIST_RE.match(lines[i])
    base = len(first.group(1))
    content_col = first.start(3)
    ordered = first.group(2)[0].isdigit()
    items = []

    while i < n:
        line = lines[i]
        if not line.strip():
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            indented = j < n and (len(lines[j]) - len(lines[j].lstrip())) > base
            if j < n and (LIST_RE.match(lines[j]) or indented) and items:
                items[-1].append('')
                i = j
                continue
            break

        m = LIST_RE.match(line)
        indent = len(line) - len(line.lstrip())
        if m and len(m.group(1)) == base:
            items.append([m.group(3)])
            i += 1
        elif indent > base and items:
            items[-1].append(line[min(indent, content_col):])
            i += 1
        else:
            break

    tag = 'ol' if ordered else 'ul'
    parts = [f'<{tag}>']
    for item in items:
        inner = md_to_html('\n'.join(item).strip('\n'))
        tight = re.fullmatch(r'<p>(.*)</p>', inner, re.S)
        parts.append('<li>' + (tight.group(1) if tight else inner) + '</li>')
    parts.append(f'</{tag}>')
    out.append(''.join(parts))
    return i


def md_to_html(src):
    lines = src.split('\n')
    out, i, n = [], 0, len(lines)

    while i < n:
        line = lines[i]

        if line.startswith('```'):
            lang = line[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>' + html.escape('\n'.join(buf)) + '</code></pre>')
            continue

        if not line.strip():
            i += 1
            continue

        if HR_RE.match(line):
            out.append('<hr>')
            i += 1
            continue

        m = HEAD_RE.match(line)
        if m:
            lvl, raw = len(m.group(1)), m.group(2)
            out.append(f'<h{lvl} id="{slugify(raw)}">{inline(raw)}</h{lvl}>')
            i += 1
            continue

        if line.lstrip().startswith('>'):
            buf = []
            while i < n and lines[i].lstrip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            out.append('<blockquote>' + md_to_html('\n'.join(buf)) + '</blockquote>')
            continue

        if '|' in line and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1]):
            i = parse_table(lines, i, n, out)
            continue

        if LIST_RE.match(line):
            i = parse_list(lines, i, n, out)
            continue

        buf = []
        while i < n and lines[i].strip() and not (
                lines[i].startswith('```')
                or HR_RE.match(lines[i])
                or HEAD_RE.match(lines[i])
                or lines[i].lstrip().startswith('>')
                or LIST_RE.match(lines[i])):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append('<p>' + inline(' '.join(buf)) + '</p>')

    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """`--- key: value ---` at the top of the file. Lists use [a, b, c]."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 4:].lstrip('\n')

    meta = {}
    for line in raw.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, _, value = line.partition(':')
        key, value = key.strip(), value.strip()
        if value.startswith('[') and value.endswith(']'):
            meta[key] = [v.strip().strip('"\'') for v in value[1:-1].split(',') if v.strip()]
        else:
            meta[key] = value.strip('"\'')
    return meta, body


def reading_time(body):
    words = len(re.findall(r'\w+', body))
    return max(1, round(words / WORDS_PER_MIN))


def load_posts(include_drafts=False):
    posts = []
    for path in sorted(POSTS_DIR.glob('*.md')):
        text = path.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(text)

        linkedin = ''
        split = LINKEDIN_MARKER.split(body, maxsplit=1)
        if len(split) == 2:
            body, linkedin = split[0].rstrip(), split[1].strip()

        is_draft = str(meta.get('draft', '')).lower() in ('true', 'yes', '1')
        if is_draft and not include_drafts:
            continue

        stem = path.stem
        m = re.match(r'(\d{4}-\d{2}-\d{2})-(.+)$', stem)
        date_str = meta.get('date') or (m.group(1) if m else '')
        slug = meta.get('slug') or (m.group(2) if m else stem)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            date = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        title = meta.get('title') or slug.replace('-', ' ').title()
        tags = meta.get('tags') or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        posts.append({
            'path': path,
            'slug': slug,
            'title': title,
            'summary': meta.get('summary', ''),
            'tags': tags,
            'topic': tags[0] if tags else 'Notes',
            'date': date,
            'draft': is_draft,
            'image': meta.get('image', DEFAULT_OG),
            'body': body,
            'linkedin': linkedin,
            'minutes': reading_time(body),
            'url': f'{SITE}/blog/{slug}/',
        })

    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


# ---------------------------------------------------------------------------
# Templates — the site's own markup, so post pages inherit site.css verbatim
# ---------------------------------------------------------------------------

def e(s):
    return html.escape(str(s), quote=True)


def icon(name):
    shapes = {
        'home': '<path d="m4 11 8-7 8 7v9H4Z"/><path d="M9 20v-7h6v7"/>',
        'folder': '<path d="M3 7V5h7l2 3h9v12H3Z"/><path d="M3 8h9"/>',
        'note': '<path d="M6 3h9l4 4v14H6Z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
        'person': '<circle cx="12" cy="8" r="4"/><path d="M4 21v-3c0-5 16-5 16 0v3"/>',
        'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
        'plane': '<path d="m3 13 7-2 2-8 2 8 7 2v2l-7-1-1 5 3 2H8l3-2-1-5-7 1Z"/>',
        'shield': '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
        'pipeline': '<rect x="2" y="4" width="6" height="6" rx="1"/><rect x="16" y="14" width="6" height="6" rx="1"/><path d="M5 10v7h11M8 7h11v7"/>',
        'clinical': '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M9 9h6M12 6v6M8 16h8"/>',
        'briefcase': '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M8 8V4h8v4M3 13h18M10 13v3h4v-3"/>',
        'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
        'search': '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
        'code': '<path d="m8 7-5 5 5 5M16 7l5 5-5 5M13.5 4l-3 16"/>',
        'network': '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7.5l3 8M16 7.5l-3 8M8.5 6h7"/>',
    }
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{shapes[name]}</svg>')


def nav_html(current):
    links = ''.join(
        f'<a href="{u}"' + (' aria-current="page"' if k == current else '') + f'>{label}</a>'
        for k, u, label in SD.NAV if k != 'home')  # the brand badge links home
    return f'''<a href="#top" class="skip-link">Skip to content</a>
<header class="nav">
  <a href="/" class="brand"><span class="brand-mark" aria-hidden="true">ps</span><span class="brand-name">Prabhu Saravanan</span></a>
  <div class="nav-bar">
    <div class="nav-tools">
      <button class="theme-toggle" type="button" aria-label="Use dark appearance" aria-pressed="false">{icon('sun')}</button>
      <button class="search-btn" data-open-search aria-label="Search the site" aria-keyshortcuts="Meta+K Control+K">{icon('search')}<kbd class="kbd-shortcut" aria-hidden="true"></kbd></button>
    </div>
    <span class="nav-sep" aria-hidden="true"></span>
    <nav class="nav-links" id="navLinks" aria-label="Main">{links}</nav>
    <button class="menu-btn" id="menuBtn" aria-label="Menu" aria-expanded="false" aria-controls="navLinks"><span></span></button>
  </div>
</header>
<dialog class="palette" id="palette" aria-labelledby="searchTitle">
  <div class="palette-box">
    <div class="palette-heading"><h2 id="searchTitle">Find something</h2><button type="button" class="palette-close" aria-label="Close search">Close <kbd>Esc</kbd></button></div>
    <input type="search" id="searchInput" name="q" placeholder="Projects, experience, résumés…" aria-label="Search the site" aria-describedby="searchStatus" autocomplete="off">
    <p class="search-status" id="searchStatus" role="status"></p>
    <ul aria-label="Search results"></ul>
    <div class="palette-hint">↑↓ to move · ↵ to open · esc to close</div>
  </div>
</dialog>'''


# Brand marks from Simple Icons (CC0, simple-icons@13.21.0); trademarks belong to their owners.
# Used only to name the tools I work with. Keys: slug -> (label, brand colour, 24x24 path).
BRANDS = {
    'databricks': ('Databricks', '#FF3621', 'M.95 14.184L12 20.403l9.919-5.55v2.21L12 22.662l-10.484-5.96-.565.308v.77L12 24l11.05-6.218v-4.317l-.515-.309L12 19.118l-9.867-5.653v-2.21L12 16.805l11.05-6.218V6.32l-.515-.308L12 11.974 2.647 6.681 12 1.388l7.76 4.368.668-.411v-.566L12 0 .95 6.27v.72L12 13.207l9.919-5.55v2.26L12 15.52 1.516 9.56l-.565.308Z'),
    'snowflake': ('Snowflake', '#29B5E8', 'M24 3.459c0 .646-.418 1.18-1.141 1.18-.723 0-1.142-.534-1.142-1.18 0-.647.419-1.18 1.142-1.18.723 0 1.141.533 1.141 1.18zm-.228 0c0-.533-.38-.951-.913-.951s-.913.38-.913.95c0 .533.38.952.913.952.57 0 .913-.419.913-.951zm-1.37-.533h.495c.266 0 .456.152.456.38 0 .153-.076.229-.19.305l.19.266v.038h-.266l-.19-.266h-.229v.266h-.266zm.495.228h-.229v.267h.229c.114 0 .152-.038.152-.114.038-.077-.038-.153-.152-.153zM7.602 12.4c.038-.151.076-.304.076-.456 0-.114-.038-.228-.038-.342-.114-.343-.304-.647-.646-.838l-4.87-2.777c-.685-.38-1.56-.152-1.94.533-.381.685-.153 1.56.532 1.94l2.701 1.56-2.701 1.56c-.685.38-.913 1.256-.533 1.94.38.685 1.256.914 1.94.533l4.832-2.777c.343-.267.571-.533.647-.876zm1.332 2.626c-.266-.038-.57.038-.837.19l-4.832 2.777c-.685.38-.913 1.256-.532 1.94.38.686 1.255.914 1.94.533l2.701-1.56v3.12c0 .8.647 1.408 1.446 1.408.799 0 1.407-.647 1.407-1.408v-5.592c0-.761-.57-1.37-1.293-1.408zm4.946-6.088c.266.038.57-.038.837-.19l4.832-2.777c.685-.38.913-1.256.532-1.94-.38-.686-1.255-.914-1.94-.533l-2.701 1.56V1.975c0-.799-.647-1.408-1.446-1.408-.799 0-1.446.609-1.446 1.408V7.53c0 .76.609 1.37 1.332 1.407zM3.265 5.97l4.832 2.777c.266.152.533.19.837.19.723-.038 1.331-.684 1.331-1.407V1.975c0-.799-.646-1.408-1.407-1.408-.799 0-1.446.647-1.446 1.408v3.12l-2.701-1.56c-.685-.38-1.56-.152-1.94.533-.419.646-.19 1.521.494 1.902zm9.093 6.011a.412.412 0 00-.114-.266l-.57-.571a.346.346 0 00-.267-.114.412.412 0 00-.266.114l-.571.57a.411.411 0 00-.114.267c0 .076.038.19.114.267l.57.57a.345.345 0 00.267.114c.076 0 .19-.038.266-.114l.571-.57a.412.412 0 00.114-.267zm1.598.533L11.94 14.53c-.039.038-.153.114-.229.114h-.608a.411.411 0 01-.267-.114L8.82 12.514a.408.408 0 01-.076-.229v-.608c0-.076.038-.19.114-.267l2.016-2.016a.41.41 0 01.267-.114h.608a.41.41 0 01.267.114l2.016 2.016a.347.347 0 01.114.267v.608c-.076.077-.114.19-.19.229zm5.593 5.44l-4.832-2.777c-.266-.152-.57-.19-.837-.152-.723.038-1.332.684-1.332 1.408v5.554c0 .8.647 1.408 1.408 1.408.799 0 1.446-.647 1.446-1.408v-3.12l2.7 1.56c.686.38 1.561.152 1.941-.533.419-.646.19-1.521-.494-1.94zm2.549-7.533l-2.701 1.56 2.7 1.56c.686.38.914 1.256.533 1.94-.38.685-1.255.913-1.94.533l-4.832-2.778a1.644 1.644 0 01-.647-.798c-.037-.153-.076-.305-.076-.457 0-.114.039-.228.039-.342.114-.343.342-.647.646-.837l4.832-2.778c.685-.38 1.56-.152 1.94.533.457.609.19 1.484-.494 1.864'),
    'dbt': ('dbt', '#FF694B', 'M17.9004 9.3763a8.1488 8.1488 0 0 0-3.0421-3.1206l1.7708.8385a10.2874 10.2874 0 0 1 3.74 3.0007l3.234-5.9295a2.8546 2.8546 0 0 0-.0611-2.9604C22.7566.0371 21.2112-.3409 19.9754.3327l-5.8749 3.2101a4.3612 4.3612 0 0 1-4.1761 0L4.1769.408a2.8545 2.8545 0 0 0-2.9592.0632c-1.1673.7853-1.5452 2.33-.8723 3.5655L3.55 9.9106a4.3612 4.3612 0 0 1 0 4.1772l-3.1272 5.743a2.86 2.86 0 0 0 .085 2.9974c.794 1.1438 2.3225 1.5054 3.5448.8385l6.0581-3.3049a10.2877 10.2877 0 0 1-3.0051-3.7454l-.8374-1.7708a8.148 8.148 0 0 0 3.1206 3.0421l10.5832 5.779c1.2213.666 2.7481.3055 3.5426-.8363a2.8699 2.8699 0 0 0 .0796-3.0018L17.9004 9.3763zm3.3801-7.7351c.6022 0 1.0904.4882 1.0904 1.0904s-.4882 1.0904-1.0904 1.0904-1.0904-.4882-1.0904-1.0904.4882-1.0904 1.0904-1.0904zM2.7442 3.822c-.6022 0-1.0904-.4882-1.0904-1.0904s.4882-1.0904 1.0904-1.0904 1.0904.4882 1.0904 1.0904S3.3464 3.822 2.7442 3.822zm0 18.5363c-.6022 0-1.0904-.4882-1.0904-1.0904 0-.6022.4882-1.0904 1.0904-1.0904s1.0904.4882 1.0904 1.0904c0 .6022-.4882 1.0904-1.0904 1.0904zm10.3585-11.4489c-1.2008-.0035-2.177.9672-2.1805 2.1679a2.1738 2.1738 0 0 0 .7052 1.6091c-1.4872-.2091-2.5234-1.5843-2.3142-3.0716.2091-1.4872 1.5843-2.5234 3.0716-2.3142a2.7194 2.7194 0 0 1 2.3142 2.3142 2.1623 2.1623 0 0 0-1.5963-.7054zm8.1778 11.4489c-.6022 0-1.0904-.4882-1.0904-1.0904 0-.6022.4882-1.0904 1.0904-1.0904s1.0904.4882 1.0904 1.0904c0 .6022-.4882 1.0904-1.0904 1.0904z'),
    'apachekafka': ('Kafka', '#231F20', 'M9.71 2.136a1.43 1.43 0 0 0-2.047 0h-.007a1.48 1.48 0 0 0-.421 1.042c0 .41.161.777.422 1.039l.007.007c.257.264.616.426 1.019.426.404 0 .766-.162 1.027-.426l.003-.007c.261-.262.421-.629.421-1.039 0-.408-.159-.777-.421-1.042H9.71zM8.683 22.295c.404 0 .766-.167 1.027-.429l.003-.008c.261-.261.421-.631.421-1.036 0-.41-.159-.778-.421-1.044H9.71a1.42 1.42 0 0 0-1.027-.432 1.4 1.4 0 0 0-1.02.432h-.007c-.26.266-.422.634-.422 1.044 0 .406.161.775.422 1.036l.007.008c.258.262.617.429 1.02.429zm7.89-4.462c.359-.096.683-.33.882-.684l.027-.052a1.47 1.47 0 0 0 .114-1.067 1.454 1.454 0 0 0-.675-.896l-.021-.014a1.425 1.425 0 0 0-1.078-.132c-.36.091-.684.335-.881.686-.2.349-.241.75-.146 1.119.099.363.33.691.675.896h.002c.346.203.737.239 1.101.144zm-6.405-7.342a2.083 2.083 0 0 0-1.485-.627c-.58 0-1.103.242-1.482.627-.378.385-.612.916-.612 1.507s.233 1.124.612 1.514a2.08 2.08 0 0 0 2.967 0c.379-.39.612-.923.612-1.514s-.233-1.122-.612-1.507zm-.835-2.51c.843.141 1.6.552 2.178 1.144h.004c.092.093.182.196.265.299l1.446-.851a3.176 3.176 0 0 1-.047-1.808 3.149 3.149 0 0 1 1.456-1.926l.025-.016a3.062 3.062 0 0 1 2.345-.306c.77.21 1.465.721 1.898 1.482v.002c.431.757.518 1.626.313 2.408a3.145 3.145 0 0 1-1.456 1.928l-.198.118h-.02a3.095 3.095 0 0 1-2.154.201 3.127 3.127 0 0 1-1.514-.944l-1.444.848a4.162 4.162 0 0 1 0 2.879l1.444.846c.413-.47.939-.789 1.514-.944a3.041 3.041 0 0 1 2.371.319l.048.023v.002a3.17 3.17 0 0 1 1.408 1.906 3.215 3.215 0 0 1-.313 2.405l-.026.053-.003-.005a3.147 3.147 0 0 1-1.867 1.436 3.096 3.096 0 0 1-2.371-.318v-.006a3.156 3.156 0 0 1-1.456-1.927 3.175 3.175 0 0 1 .047-1.805l-1.446-.848a3.905 3.905 0 0 1-.265.294l-.004.005a3.938 3.938 0 0 1-2.178 1.138v1.699a3.09 3.09 0 0 1 1.56.862l.002.004c.565.572.914 1.368.914 2.243 0 .873-.35 1.664-.914 2.239l-.002.009a3.1 3.1 0 0 1-2.21.931 3.1 3.1 0 0 1-2.206-.93h-.002v-.009a3.186 3.186 0 0 1-.916-2.239c0-.875.35-1.672.916-2.243v-.004h.002a3.1 3.1 0 0 1 1.558-.862v-1.699a3.926 3.926 0 0 1-2.176-1.138l-.006-.005a4.098 4.098 0 0 1-1.173-2.874c0-1.122.452-2.136 1.173-2.872h.006a3.947 3.947 0 0 1 2.176-1.144V6.289a3.137 3.137 0 0 1-1.558-.864h-.002v-.004a3.192 3.192 0 0 1-.916-2.243c0-.871.35-1.669.916-2.243l.002-.002A3.084 3.084 0 0 1 8.683 0c.861 0 1.641.355 2.21.932v.002h.002c.565.574.914 1.372.914 2.243 0 .876-.35 1.667-.914 2.243l-.002.005a3.142 3.142 0 0 1-1.56.864v1.692zm8.121-1.129l-.012-.019a1.452 1.452 0 0 0-.87-.668 1.43 1.43 0 0 0-1.103.146h.002c-.347.2-.58.529-.677.896-.095.365-.054.768.146 1.119l.007.009c.2.347.519.579.874.673.357.103.755.059 1.098-.144l.019-.009a1.47 1.47 0 0 0 .657-.885 1.493 1.493 0 0 0-.141-1.118'),
    'terraform': ('Terraform', '#844FBA', 'M1.44 0v7.575l6.561 3.79V3.787zm21.12 4.227l-6.561 3.791v7.574l6.56-3.787zM8.72 4.23v7.575l6.561 3.787V8.018zm0 8.405v7.575L15.28 24v-7.578z'),
    'python': ('Python', '#3776AB', 'M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04.84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32.33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33.08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z'),
    'github': ('GitHub', '#181717', 'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12'),
    'linkedin': ('LinkedIn', '#0A66C2', 'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z'),
}


def brand_svg(slug):
    return (f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="{BRANDS[slug][2]}"/></svg>')


# The dock carries proof (the stack the projects actually use) and the ways to reach me.
# Page navigation lives in the menu bar only, so nothing is repeated three times.
STACK = ['databricks', 'snowflake', 'dbt', 'apachekafka', 'terraform', 'python']
ELSEWHERE = [('https://github.com/saravanaprabhu1398-afk', 'github'),
             ('https://www.linkedin.com/in/prabhu-saravanan-a53317226', 'linkedin')]


def brand_tile(slug, cls):
    label, colour, _ = BRANDS[slug]
    return f'<span class="{cls}" style="--brand:{colour}">{brand_svg(slug)}</span>'


DOCK = ('<div class="dock" role="region" aria-label="Stack and contact">'
        '<ul class="dock-stack" aria-label="Core stack">' + ''.join(
            f'<li>{brand_tile(slug, "dock-icon dock-tech")}<span>{BRANDS[slug][0]}</span></li>'
            for slug in STACK) + '</ul><span class="dock-divider" aria-hidden="true"></span>'
        '<nav class="dock-links" aria-label="Elsewhere">' + ''.join(
            f'<a href="{url}" rel="noopener">{brand_tile(slug, "dock-icon dock-tech")}<span>{BRANDS[slug][0]}</span></a>'
            for url, slug in ELSEWHERE)
        + f'<a href="mailto:prabhu.saravanan.de@gmail.com"><span class="dock-icon dock-mail">{icon("mail")}</span><span>Email</span></a>'
        '</nav></div>')


def render_orbit():
    """Stack logos that orbit the database chip in the home hero, three rings of two."""
    rings = [STACK[0:2], STACK[2:4], STACK[4:6]]
    angles = [(0, 180), (60, 240), (120, 300)]
    out = '<span class="orbit" aria-hidden="true">'
    for n, (pair, degs) in enumerate(zip(rings, angles), 1):
        out += f'<span class="ring r{n}">' + ''.join(
            f'<span class="bubble" style="--a:{a}deg">{brand_tile(slug, "bubble-tile")}</span>'
            for slug, a in zip(pair, degs)) + '</span>'
    return out + '</span>'


FOOTER = '''<footer class="footer">
  <div class="wrap">
    <span>Prabhu Saravanan — Abu Dhabi, UAE</span>
    <nav aria-label="Footer"><a href="/projects/">Projects</a><a href="/blog/">Writing</a><a href="/about/">About</a><a href="/feed.xml">RSS</a><a href="https://github.com/saravanaprabhu1398-afk" rel="noopener">GitHub</a><a href="https://www.linkedin.com/in/prabhu-saravanan-a53317226" rel="noopener">LinkedIn</a></nav>
  </div>
</footer>''' + DOCK + '''
<script src="/site.js?v=''' + ASSET_V + '''"></script>'''


def shell(title, description, canonical, image, body, extra_head='', current='writing'):
    return f'''<!DOCTYPE html>
<!-- Generated by tools/build.py -->
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">

<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{e(image)}">
<meta name="theme-color" content="#f3f4f8">
<script src="/theme.js?v={ASSET_V}"></script>

<link rel="alternate" type="application/rss+xml" title="{e(AUTHOR)} &#8212; Writing" href="/feed.xml">
{FAVICON}
{FONT_PRELOAD}
<link rel="stylesheet" href="/site.css?v={ASSET_V}">
{extra_head}</head>
<body>
{nav_html(current)}

<main id="top">
{body}
</main>

{FOOTER}
</body>
</html>
'''


def render_post(post):
    date_label = post['date'].strftime('%d %b %Y').upper()
    tags = ''.join(f'<span>{e(t)}</span>' for t in post['tags'])
    draft_flag = ('<span class="post-status">Draft</span>' if post['draft'] else '')

    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post['title'],
        "description": post['summary'],
        "datePublished": post['date'].strftime('%Y-%m-%d'),
        "author": {"@type": "Person", "name": AUTHOR, "jobTitle": ROLE},
        "mainEntityOfPage": post['url'],
        "image": post['image'],
    }
    ld_tag = ('<script type="application/ld+json">'
              + json.dumps(ld, ensure_ascii=False) + '</script>\n')

    body = f'''  <article class="wrap article" style="padding-top:48px">
    <div>

        <div class="post-meta article-meta">
          {draft_flag}<em>{e(post['topic'])}</em>
          <span class="sep" aria-hidden="true">&#183;</span>
          <time datetime="{post['date'].strftime('%Y-%m-%d')}">{date_label}</time>
          <span class="sep" aria-hidden="true">&#183;</span>
          <span>{post['minutes']} MIN READ</span>
        </div>

        <h1 class="article-title">{e(post['title'])}</h1>
        <p class="article-lede">{e(post['summary'])}</p>

        <div class="article-body">
{md_to_html(post['body'])}
        </div>

        <div class="article-tags">{tags}</div>

        <div class="article-foot">
          <a class="btn" href="/blog/">&#8592; All writing</a>
          <a class="btn" href="/#contact">Get in touch</a>
        </div>

    </div>
  </article>'''

    return shell(f"{post['title']} — {AUTHOR}", post['summary'] or post['title'],
                 post['url'], post['image'], body, ld_tag)


def render_blog_index(posts):
    if posts:
        cards = []
        for p in posts:
            date_label = p['date'].strftime('%d %b %Y').upper()
            status = ('<span class="post-status">Draft</span>' if p['draft'] else '')
            cards.append(f'''          <article class="post">
            <a class="post-link" href="/blog/{p['slug']}/">
              <div class="post-meta">{status}<em>{e(p['topic'])}</em><span class="sep" aria-hidden="true">&#183;</span><time datetime="{p['date'].strftime('%Y-%m-%d')}">{date_label}</time><span class="sep" aria-hidden="true">&#183;</span><span>{p['minutes']} MIN</span></div>
              <h2>{e(p['title'])}</h2>
              <p>{e(p['summary'])}</p>
              <span class="post-more">Read <i aria-hidden="true">&#8594;</i></span>
            </a>
          </article>''')
        listing = '\n'.join(cards)
    else:
        listing = ('          <article class="post"><h2>Nothing published yet</h2>'
                   '<p>First piece is in the works.</p></article>')

    body = f'''  <section id="writing" style="padding-top:48px">
    <div class="wrap">
      <div>
        <span class="eyebrow"><span class="dot"></span>Writing</span>
        <h1 class="article-title" style="margin-top:14px">Field notes</h1>
        <p class="article-lede">Notes from building data and AI platforms in production &#8212; lakehouse
        architecture, experimentation integrity, and governing AI assets like data assets.</p>

        <div class="post-list">
{listing}
        </div>

        <p class="feed-note"><a href="/feed.xml">RSS feed</a></p>
      </div>
    </div>
  </section>'''

    return shell(f'Writing — {AUTHOR}',
                 'Field notes on data engineering, lakehouse architecture and AI platform work.',
                 f'{SITE}/blog/', DEFAULT_OG, body)


HOME_START = '<!-- POSTS:START -->'
HOME_END = '<!-- POSTS:END -->'


def update_home(posts):
    """Refresh the #blog cards on the homepage between the two markers."""
    src = INDEX.read_text(encoding='utf-8')
    if HOME_START not in src or HOME_END not in src:
        print('  ! index.html has no POSTS markers — homepage cards not updated')
        return False

    if posts:
        cards = []
        for p in posts[:3]:
            date_label = p['date'].strftime('%d %b %Y').upper()
            status = ('<span class="post-status">Draft</span>' if p['draft'] else '')
            cards.append(f'''          <article class="post">
            <a class="post-link" href="/blog/{p['slug']}/">
              <div class="post-meta">{status}<em>{e(p['topic'])}</em><span class="sep" aria-hidden="true">&#183;</span><time datetime="{p['date'].strftime('%Y-%m-%d')}">{date_label}</time></div>
              <h3>{e(p['title'])}</h3>
              <p>{e(p['summary'])}</p>
            </a>
          </article>''')
        block = ('        <div class="post-list">\n' + '\n'.join(cards)
                 + '\n        </div>\n\n'
                 + '        <a class="btn" href="/blog/">All writing '
                   '<span aria-hidden="true">&#8594;</span></a>')
    else:
        block = ('        <div class="post-list"><article class="post">'
                 '<h3>Nothing published yet</h3></article></div>')

    new = re.sub(
        re.escape(HOME_START) + r'.*?' + re.escape(HOME_END),
        lambda m: HOME_START + '\n' + block + '\n        ' + HOME_END,
        src, flags=re.S)
    if new != src:
        INDEX.write_text(new, encoding='utf-8')
    return True


def render_feed(posts):
    items = []
    for p in posts:
        if p['draft']:
            continue
        items.append(f'''  <item>
    <title>{e(p['title'])}</title>
    <link>{e(p['url'])}</link>
    <guid isPermaLink="true">{e(p['url'])}</guid>
    <pubDate>{format_datetime(p['date'])}</pubDate>
    <description>{e(p['summary'])}</description>
{''.join(f"    <category>{e(t)}</category>{chr(10)}" for t in p['tags'])}  </item>''')

    built = format_datetime(datetime.now(timezone.utc))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{e(AUTHOR)} — Writing</title>
  <link>{SITE}/blog/</link>
  <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Field notes on data engineering, lakehouse architecture and AI platform work.</description>
  <language>en</language>
  <lastBuildDate>{built}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
'''


def write_outbox(posts, restage=None):
    """Preserve pending edits and posted history unless explicitly restaged."""
    written = []
    for p in posts:
        if not p['linkedin']:
            continue
        text = p['linkedin'].replace('{url}', p['url'])
        target = OUTBOX / f"{p['slug']}.txt"
        archived = OUTBOX / 'posted' / target.name
        if p['slug'] != restage and archived.exists():
            print(f"  = {target.name} already posted; not restaged")
            continue
        if p['slug'] != restage and target.exists():
            if target.read_text(encoding='utf-8') != text:
                print(f"  ! Preserved pending edits in outbox/{target.name}; "
                      f"use --restage {p['slug']} to replace with source copy")
            continue
        target.write_text(text, encoding='utf-8')
        written.append((target, len(text)))
    return written



# ---------------------------------------------------------------------------
# Hand-written pages: shared nav/footer and the generated project cards
# ---------------------------------------------------------------------------

PAGES = [('index.html', 'home'), ('projects/index.html', 'projects'), ('about/index.html', 'about'),
         ('404.html', 'not-found')]


def project_card(p, preview=False):
    img = ''
    if p['img']:
        src, alt = p['img']
        img = f'<div class="project-img"><img src="{e(src)}" alt="{e(alt)}" loading="lazy"></div>'
    metric = ''
    if p['metric']:
        num, cap, (kind, url, label) = p['metric']
        ext = ' target="_blank" rel="noopener"' if url.startswith('http') else ''
        metric = (f'<div class="metric"><b>{e(num)}</b><span>{e(cap)} '
                  f'<a class="evidence" href="{e(url)}"{ext}><b>{e(kind)}</b> {e(label)} &#8599;</a></span></div>')
    links = ''.join(f'<a href="{e(u)}" target="_blank" rel="noopener">{e(t)} &#8599;</a>' for t, u in p['links'])
    tags = ''.join(f'<span>{e(t)}</span>' for t in p['tags'])
    anchor = '' if preview else f' id="project-{e(p["slug"])}"'
    rendered = f"""      <article class="card project"{anchor} data-tags="{' '.join(p['cats'])}" data-reveal>
        {img}
        <div class="project-body">
          <span class="badge">{e(p['status'])}</span>
          <h3>{e(p['title'])}</h3>
          <p>{e(p['desc'])}</p>
          {metric}
          <div class="tags">{tags}</div>
          <div class="links">{links}</div>
        </div>
      </article>"""
    return '\n'.join(line.rstrip() for line in rendered.splitlines())


def sub_block(src, name, content):
    start, end = f'<!--{name}:START-->', f'<!--{name}:END-->'
    if start not in src:
        return src
    return re.sub(re.escape(start) + r'.*?' + re.escape(end),
                  lambda m: start + '\n' + content + '\n      ' + end, src, flags=re.S)


def render_spotlight():
    detail = SD.SPOTLIGHT
    project = next(p for p in SD.PROJECTS if p['slug'] == detail['slug'])
    num, caption, (kind, evidence_url, _) = project['metric']
    flows = ''.join(
        '<div class="flow-lane"><p class="badge">' + e(label) + '</p><ol class="flow-steps">'
        + ''.join(f'<li><span>{e(step)}</span><strong>{e(tool)}</strong><small>{e(note)}</small></li>'
                  for step, tool, note in steps) + '</ol></div>'
        for label, steps in detail['flows'])
    return f'''  <section id="project-spotlight" aria-labelledby="spotlight-title">
    <div class="wrap spotlight">
      <div class="spotlight-copy">
        <h2 id="spotlight-title">{e(project['title'])}</h2>
        <p>{e(detail['summary'])}</p>
        <div class="spotlight-outcome"><strong>{e(num)}</strong><span>{e(caption)}</span></div>
        <a class="more-link" href="{e(evidence_url)}" target="_blank" rel="noopener">{e(kind)} · see the evidence ↗</a>
      </div>
      <figure class="flow-diagram">
        {flows}
        <figcaption>{e(detail['note'])} <a href="{e(detail['source'])}" target="_blank" rel="noopener">Source architecture ↗</a></figcaption>
      </figure>
    </div>
  </section>'''


def render_launcher():
    projects = {p['slug']: p for p in SD.PROJECTS}
    entries = [
        ('flightpulse', 'FlightPulse', 'Flight analytics', 'plane'),
        ('guardrail', 'Guardrail', 'Safe rollouts', 'shield'),
        ('dataplatform', 'Dataplatform', 'Orchestration', 'pipeline'),
        ('clinical-document-intelligence', 'Clinical AI', 'Governed RAG', 'clinical'),
    ]
    tiles, previews = [], []
    for slug, title, subtitle, glyph in entries:
        tiles.append(f'''<a class="app" href="/projects/#project-{slug}" data-preview="preview-{slug}">
          <span class="app-icon app-{glyph}">{icon(glyph)}</span><strong>{title}</strong><small>{subtitle}</small></a>''')
        previews.append(f'''<dialog class="project-preview" id="preview-{slug}" aria-label="{e(title)} project preview">
          <div class="preview-window"><div class="window-bar"><span>{e(title)}</span>
          <button type="button" data-close-preview aria-label="Close {e(title)} preview">Close <kbd>Esc</kbd></button></div>
          {project_card(projects[slug], preview=True)}
          <a class="preview-more" href="/projects/#project-{slug}">Open in Projects &#8599;</a></div></dialog>''')
    return ('<div class="launcher"><div class="launcher-heading"><h2>Selected projects</h2>'
            '<a href="/projects/">All projects &#8599;</a></div><div class="app-grid">'
            + ''.join(tiles) + '</div></div>' + ''.join(previews))


def sync_head(src, hand=False):
    src = re.sub(r'<link[^>]+https://fonts\.(?:googleapis|gstatic)\.com[^>]*>\n?', '', src)
    src = re.sub(r'<meta name="theme-color" content="[^"]+">', '<meta name="theme-color" content="#f3f4f8">', src)
    src = re.sub(r'<script src="/theme\.js[^"]*"></script>\n?', '', src)
    src = re.sub(r'<link rel="preload"[^>]+/assets/fonts/[^>]+>\n?', '', src)
    src = re.sub(r'<link rel="icon"[^>]*>\n?', '', src)
    src = re.sub(r'/site\.css\?v=[^"]+', lambda m: f'/site.css?v={ASSET_V}', src)
    fonts = FONT_PRELOAD + ('\n' + HAND_PRELOAD if hand else '')
    return src.replace('</head>', f'{FAVICON}\n{fonts}\n<script src="/theme.js?v={ASSET_V}"></script>\n</head>')


def sync_pages():
    featured = '<div class="projects">\n' + '\n'.join(project_card(p) for p in SD.PROJECTS if p['featured']) + '\n      </div>'
    everything = '<div class="projects">\n' + '\n'.join(project_card(p) for p in SD.PROJECTS) + '\n      </div>'
    filters = ''.join(f'<button type="button" data-filter="{k}" aria-pressed="{"true" if k == "all" else "false"}">{l}</button>'
                      for k, l in SD.FILTERS)
    for rel, current in PAGES:
        path = ROOT / rel
        if not path.exists():
            continue
        src = path.read_text(encoding='utf-8')
        src = src.replace("<script>document.documentElement.classList.add('js')</script>\n", '')
        src = sync_head(src, hand=(rel == 'index.html'))
        src = re.sub(r'<!--SHARED:NAV-->.*?<!--/SHARED:NAV-->',
                     lambda m: '<!--SHARED:NAV-->\n' + nav_html(current) + '\n<!--/SHARED:NAV-->', src, flags=re.S)
        src = re.sub(r'<!--SHARED:FOOT-->.*?<!--/SHARED:FOOT-->',
                     lambda m: '<!--SHARED:FOOT-->\n' + FOOTER + '\n<!--/SHARED:FOOT-->', src, flags=re.S)
        src = sub_block(src, 'PROJECTS:FEATURED', featured)
        src = sub_block(src, 'PROJECTS:ALL', everything)
        src = sub_block(src, 'PROJECTS:SPOTLIGHT', render_spotlight())
        src = sub_block(src, 'PROJECTS:LAUNCHER', render_launcher())
        src = sub_block(src, 'STACK:ORBIT', render_orbit())
        src = src.replace('<!--FILTERS-->', filters) if '<!--FILTERS-->' in src else re.sub(
            r'(<div class="filters"[^>]*>).*?(</div>)', lambda m: m.group(1) + filters + m.group(2), src, count=1, flags=re.S)
        path.write_text(src, encoding='utf-8')
        print(f'  + {rel}  (shared nav/footer, project cards)')


def write_search_index(posts):
    items = list(SD.SEARCH_STATIC)
    for p in SD.PROJECTS:
        items.append(dict(t=p['title'], d=p['desc'][:110] + '…', u=p['links'][0][1], k='Project', x=' '.join(p['tags'])))
    for p in posts:
        if not p['draft']:
            items.append(dict(t=p['title'], d=p['summary'], u=f"/blog/{p['slug']}/", k='Post'))
    (ROOT / 'search-index.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
    print('  + search-index.json')


def clean_old_posts(live):
    for old in BLOG_DIR.iterdir():
        if old.is_symlink():
            raise ValueError(f'Refusing to clean symlink in generated blog: {old}')
        if not old.is_dir() or old.name in live:
            continue
        page = old / 'index.html'
        source = page.read_text(encoding='utf-8') if page.is_file() else ''
        if ('<!-- Generated by tools/build.py -->' not in source
                and '"@type": "BlogPosting"' not in source):
            raise ValueError(f'Refusing to remove unrecognized blog directory: {old}')
        shutil.rmtree(old)
        print(f'  - removed blog/{old.name}/')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drafts', action='store_true', help='Include drafts for local preview')
    parser.add_argument('--restage', metavar='SLUG', help='Explicitly replace/restage LinkedIn copy from source')
    args = parser.parse_args()
    include_drafts = args.drafts
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)

    posts = load_posts(include_drafts)
    if args.restage and not any(p['slug'] == args.restage and p['linkedin'] for p in posts):
        parser.error('--restage must name an included post with LinkedIn copy')
    print(f'Building {len(posts)} post(s)'
          + (' (drafts included)' if include_drafts else ''))

    live = {p['slug'] for p in posts}
    clean_old_posts(live)

    for p in posts:
        out_dir = BLOG_DIR / p['slug']
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'index.html').write_text(render_post(p), encoding='utf-8')
        flag = ' [draft]' if p['draft'] else ''
        print(f"  + blog/{p['slug']}/index.html  ({p['minutes']} min){flag}")

    (BLOG_DIR / 'index.html').write_text(render_blog_index(posts), encoding='utf-8')
    print('  + blog/index.html')

    FEED.write_text(render_feed(posts), encoding='utf-8')
    print('  + feed.xml')

    urls = [(f'{SITE}/', None), (f'{SITE}/projects/', None), (f'{SITE}/about/', None), (f'{SITE}/blog/', None)] + [
        (f"{SITE}/blog/{p['slug']}/", p['date'].strftime('%Y-%m-%d')) for p in posts if not p['draft']]
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + ''.join(f'  <url><loc>{u}</loc>' + (f'<lastmod>{d}</lastmod>' if d else '') + '</url>\n' for u, d in urls)
        + '</urlset>\n', encoding='utf-8')
    print('  + sitemap.xml')
    sync_pages()
    write_search_index(posts)

    if update_home(posts):
        print('  + index.html  (#blog cards refreshed)')

    for target, size in write_outbox(posts, args.restage):
        print(f'  + outbox/{target.name}  ({size} chars — staged, not posted)')

    print('\nNothing has been published. Review, then:')
    print('  git add -A && git commit -m "New post" && git push   # site')
    print('  python3 tools/linkedin.py post <slug>                # LinkedIn')


if __name__ == '__main__':
    main()
