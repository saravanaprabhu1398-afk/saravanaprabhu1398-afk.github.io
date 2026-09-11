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

import html
import json
import re
import sys
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
ASSET_V = "18"
BLOG_CSS_V = "3"
DEFAULT_OG = ("https://raw.githubusercontent.com/saravanaprabhu1398-afk/"
              "FlightPulse/main/docs/screenshots/02_delay_by_airport.png")

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

    def row(vals, tag):
        out_cells = []
        for k, v in enumerate(vals):
            align = aligns[k] if k < len(aligns) else 'left'
            style = f' style="text-align:{align}"' if align != 'left' else ''
            out_cells.append(f'<{tag}{style}>{inline(v)}</{tag}>')
        return '<tr>' + ''.join(out_cells) + '</tr>'

    parts = ['<div class="table-scroll"><table><thead>', row(header, 'th'),
             '</thead><tbody>']
    parts += [row(r, 'td') for r in body]
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
# Templates — the site's own markup, so post pages inherit style.css verbatim
# ---------------------------------------------------------------------------

def e(s):
    return html.escape(str(s), quote=True)


NAV = f'''<header class="site-nav" id="siteNav">
  <div class="nav-inner">
    <a href="/" class="nav-mark">PRABHU<span>&#174;</span></a>
    <nav class="nav-links" id="navLinks">
      <a href="/#work">Work</a>
      <a href="/#experience">Experience</a>
      <a href="/#skills">Skills</a>
      <a href="/blog/">Writing</a>
      <a href="/#contact">Contact</a>
      <a href="/assets/Prabhu_Saravanan_Resume.pdf" class="nav-resume-mobile" download>R&#233;sum&#233;</a>
    </nav>
    <a class="nav-cta" href="/#contact">Get in touch <span aria-hidden="true">&#8599;</span></a>
    <button class="nav-toggle" id="navToggle" aria-label="Toggle navigation" aria-expanded="false">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>'''

FOOTER = '''<footer class="site-footer">
  <span>Prabhu Saravanan &#8212; Abu Dhabi, UAE</span>
  <span>Built by hand</span>
</footer>'''


def shell(title, description, canonical, image, body, extra_head=''):
    return f'''<!DOCTYPE html>
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
<meta name="theme-color" content="#080807">

<link rel="alternate" type="application/rss+xml" title="{e(AUTHOR)} &#8212; Writing" href="/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23080807'/%3E%3Ctext x='16' y='22' font-family='Helvetica,Arial,sans-serif' font-size='15' font-weight='600' fill='%23E8E8E3' text-anchor='middle'%3EPS%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css?v={ASSET_V}">
<link rel="stylesheet" href="/blog.css?v={BLOG_CSS_V}">
{extra_head}</head>
<body>

<a href="#top" class="skip-link">Skip to content</a>
<div class="scroll-progress" id="scrollProgress" aria-hidden="true"></div>
<div class="grain" aria-hidden="true"></div>

{NAV}

<main id="top">
{body}
</main>

{FOOTER}

<script src="/script.js?v={ASSET_V}"></script>
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

    body = f'''  <article class="band band-light article">
    <div class="rail">
      <div class="rail-label"><span class="dot"></span>Writing</div>
      <div class="rail-body">

        <div class="post-meta article-meta">
          {draft_flag}<em>{e(post['topic'])}</em>
          <span class="sep" aria-hidden="true">&#183;</span>
          <time datetime="{post['date'].strftime('%Y-%m-%d')}">{date_label}</time>
          <span class="sep" aria-hidden="true">&#183;</span>
          <span>{post['minutes']} MIN READ</span>
        </div>

        <h1 class="article-title" data-split>{e(post['title'])}</h1>
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

    body = f'''  <section class="band band-light" id="writing">
    <div class="rail">
      <div class="rail-label"><span class="dot"></span>Writing</div>
      <div class="rail-body">
        <h1 class="band-heading" data-split>Field Notes</h1>
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
        HOME_START + '\n' + block + '\n        ' + HOME_END,
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


def write_outbox(posts):
    """Stage the LinkedIn copy. Writing a file publishes nothing."""
    written = []
    for p in posts:
        if not p['linkedin']:
            continue
        text = p['linkedin'].replace('{url}', p['url'])
        target = OUTBOX / f"{p['slug']}.txt"
        if target.exists() and target.read_text(encoding='utf-8') == text:
            continue
        target.write_text(text, encoding='utf-8')
        written.append((target, len(text)))
    return written


def main():
    include_drafts = '--drafts' in sys.argv
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)

    posts = load_posts(include_drafts)
    print(f'Building {len(posts)} post(s)'
          + (' (drafts included)' if include_drafts else ''))

    live = {p['slug'] for p in posts}
    for old in BLOG_DIR.iterdir():
        if old.is_dir() and old.name not in live:
            for f in old.rglob('*'):
                f.unlink()
            old.rmdir()
            print(f'  - removed blog/{old.name}/')

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

    if update_home(posts):
        print('  + index.html  (#blog cards refreshed)')

    for target, size in write_outbox(posts):
        print(f'  + outbox/{target.name}  ({size} chars — staged, not posted)')

    print('\nNothing has been published. Review, then:')
    print('  git add -A && git commit -m "New post" && git push   # site')
    print('  python3 tools/linkedin.py post <slug>                # LinkedIn')


if __name__ == '__main__':
    main()
