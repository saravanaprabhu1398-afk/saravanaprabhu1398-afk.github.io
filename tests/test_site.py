import json
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools import build

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = []
        self.links = []
        self.feed(path.read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ['href', 'src']:
            if key in attrs:
                self.links.append(attrs[key])


class SiteTests(unittest.TestCase):
    def test_local_assets_links_and_fragments_exist(self):
        paths = [ROOT / rel for rel in ['index.html', 'projects/index.html', 'about/index.html', '404.html']]
        paths += sorted((ROOT / 'blog').rglob('*.html'))
        pages = {path: Page(path) for path in paths}
        for path, page in pages.items():
            with self.subTest(page=path.relative_to(ROOT)):
                self.assertEqual(len(page.ids), len(set(page.ids)), 'Duplicate element IDs')
                for link in page.links:
                    url = urlsplit(link)
                    if url.scheme or url.netloc:
                        continue
                    target = ((ROOT / unquote(url.path).lstrip('/')) if url.path.startswith('/')
                              else path.parent / unquote(url.path)) if url.path else path
                    if target.is_dir():
                        target /= 'index.html'
                    self.assertTrue(target.is_file(), f'{path.relative_to(ROOT)} -> {link}')
                    if url.fragment and target in pages:
                        self.assertIn(unquote(url.fragment), pages[target].ids, f'{path.relative_to(ROOT)} -> {link}')

    def test_checked_in_blog_matches_sources(self):
        posts = build.load_posts()
        self.assertEqual((ROOT / 'blog' / 'index.html').read_text(), build.render_blog_index(posts))
        for post in posts:
            self.assertEqual((ROOT / 'blog' / post['slug'] / 'index.html').read_text(), build.render_post(post))

    def test_feed_sitemap_and_search_are_valid(self):
        for name in ['feed.xml', 'sitemap.xml']:
            ET.parse(ROOT / name)
        items = json.loads((ROOT / 'search-index.json').read_text())
        self.assertTrue(items)
        for item in items:
            for key in ['t', 'd', 'u', 'k']:
                self.assertIsInstance(item[key], str)
        self.assertEqual(len([x for x in items if x['k'] == 'Project']), len(build.SD.PROJECTS))

    def test_spotlight_matches_source_and_preserves_evidence_scope(self):
        source = (ROOT / 'projects' / 'index.html').read_text()
        rendered = build.render_spotlight()
        self.assertIn(rendered, source)
        self.assertIn('Historical flights in the dashboard', rendered)
        self.assertIn('streaming checks are not implemented', rendered)
        self.assertIn('FlightPulse#opening-the-dashboard', rendered)
        self.assertEqual(rendered.count('<ol class="flow-steps">'), 2)
        self.assertEqual(rendered.count('<li>'), 6)
        self.assertNotIn('id="liveCount"', source)
        self.assertNotIn('project-spotlight', (ROOT / 'index.html').read_text(), 'Home stays a single screen')


if __name__ == '__main__':
    unittest.main()
