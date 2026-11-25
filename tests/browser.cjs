/* Run against a local http.server; see README for the optional Playwright setup. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const base = process.env.SITE_URL || 'http://127.0.0.1:8000';
const search = [
  { t: 'Case studies', d: 'Production work', k: 'Page', u: '/#case-studies' },
  { t: 'Contact', d: 'Get in touch', k: 'Page', u: '/#contact' },
  { t: 'Projects', d: 'Selected work', k: 'Page', u: '/projects/' },
];

async function main() {
  const browser = await chromium.launch();
  let checks = 0;
  const errors = [];
  async function context(options = {}) {
    const ctx = await browser.newContext(options);
    await ctx.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== new URL(base).origin) {
        if (url.hostname === 'api.github.com') {
          return route.fulfill({ json: [{ name: 'Example', language: 'Python', fork: false,
            html_url: 'https://github.com/example/example', pushed_at: new Date().toISOString() }] });
        }
        return route.abort();
      }
      return route.continue();
    });
    ctx.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    return ctx;
  }
  async function check(name, action) {
    await action();
    checks++;
    console.log('PASS ' + name);
  }
  try {
    const ctx = await context();
    const page = await ctx.newPage();
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of ['/', '/projects/', '/about/', '/blog/', '/blog/publishing-pipeline/', '/404.html']) {
        await check(`${path} fits ${width}px without horizontal overflow`, async () => {
          await page.goto(base + path);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          const overflowing = await page.locator('main h1, .project, .hero-cta, .nav-bar, .tile, .flow-diagram, .flow-steps li').evaluateAll(els =>
            els.filter(el => el.getBoundingClientRect().right > innerWidth + 1 || el.getBoundingClientRect().left < -1)
              .map(el => el.className || el.tagName));
          assert.deepEqual(overflowing, []);
        });
        if (path === '/') {
          await check(`Hero hierarchy and early project evidence at ${width}px`, async () => {
            assert.equal(await page.locator('.hero-cta a').count(), 2);
            assert.equal(await page.locator('.hero-socials a').count(), 2);
            assert.equal(await page.locator('.tiles .tile').count(), 4);
            assert.equal(await page.locator('#liveCount, .chip-float, #typed').count(), 0);
            assert.equal(await page.locator('.hero-cta a').first().getAttribute('href'), '#contact');
            assert.equal(await page.locator('.hero-cta a').nth(1).getAttribute('href'), '/about/#resumes');
            const rows = await page.locator('.hero-cta a').evaluateAll(els =>
              els.map(el => Math.round(el.getBoundingClientRect().top)));
            assert.equal(rows[0], rows[1], 'Primary actions should stay together');
            assert.equal(await page.locator('main > section').nth(1).getAttribute('id'), 'project-spotlight');
            assert.equal(await page.locator('.flow-lane').count(), 2);
            assert.equal(await page.locator('.flow-steps li').count(), 6);
            if (width <= 390) {
              assert.ok(await page.locator('.hero-cta').evaluate(el => el.getBoundingClientRect().bottom < 580),
                'Contact and resume must appear within the first 580px on mobile');
              assert.equal(await page.locator('.hero .portrait').evaluate(el => el.getBoundingClientRect().width), 64);
            }
          });
        }
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + '/projects/');
    await check('Mobile menu opens and Escape restores its button', async () => {
      await page.locator('#menuBtn').click();
      assert.equal(await page.locator('#navLinks').isVisible(), true);
      await page.locator('#navLinks a').first().focus();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#navLinks').isVisible(), false);
      assert.equal(await page.locator('#menuBtn').evaluate(el => el === document.activeElement), true);
    });
    await check('Project filtering preserves matching cards and restores all', async () => {
      await page.locator('[data-filter="streaming"]').click();
      assert.equal(await page.locator('.project:visible').count(), 3);
      await page.locator('[data-filter="all"]').click();
      assert.equal(await page.locator('.project:visible').count(), 10);
      assert.equal(await page.locator('.evidence b').first().evaluate(el => getComputedStyle(el).fontSize), '10.5px');
    });

    await page.route('**/search-index.json', route => route.fulfill({ json: search }));
    await page.goto(base + '/');
    await check('Selecting a same-page result navigates and dismisses search', async () => {
      await page.locator('[data-open-search]').click();
      await page.waitForFunction(() => document.querySelectorAll('#palette li a').length === 3);
      await page.locator('#palette li a').nth(1).click();
      await page.waitForURL('**/#contact');
      assert.equal(await page.locator('#palette').isVisible(), false);
    });
    await check('Search is modal, loops focus, and restores opener on Escape', async () => {
      await page.locator('[data-open-search]').click();
      await page.waitForFunction(() => document.querySelectorAll('#palette li a').length === 3);
      assert.equal(await page.locator('#palette').evaluate(el => el.matches(':modal')), true);
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('#palette').evaluate(el => el.contains(document.activeElement)), true);
      }
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#palette').isVisible(), false);
      assert.equal(await page.locator('[data-open-search]').evaluate(el => el === document.activeElement), true);
    });
    await check('Tab then Enter activates only the focused search result', async () => {
      await page.locator('[data-open-search]').click();
      await page.evaluate(() => {
        window.resultClicks = [];
        document.querySelector('#palette ul').addEventListener('click', event => {
          const link = event.target.closest('a');
          if (link) { window.resultClicks.push(link.getAttribute('href')); event.preventDefault(); }
        });
      });
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('#palette li a').nth(1).evaluate(el => el === document.activeElement), true);
      await page.keyboard.press('Enter');
      assert.deepEqual(await page.evaluate(() => window.resultClicks), ['/#contact']);
      assert.equal(await page.locator('#palette').isVisible(), false);
    });
    await check('Input arrow selection activates exactly once and closes dialog', async () => {
      await page.locator('[data-open-search]').click();
      await page.evaluate(() => { window.resultClicks = []; });
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Enter');
      assert.deepEqual(await page.evaluate(() => window.resultClicks), ['/#contact']);
      assert.equal(await page.locator('#palette').isVisible(), false);
    });
    await check('Search handles no matches and closes from its visible button', async () => {
      await page.locator('[data-open-search]').click();
      await page.locator('#palette input').fill('no-such-result');
      assert.match(await page.locator('#searchStatus').textContent(), /No results/);
      await page.locator('.palette-close').click();
      assert.equal(await page.locator('[data-open-search]').evaluate(el => el === document.activeElement), true);
    });
    await check('Search recovers after an HTTP failure', async () => {
      const retry = await ctx.newPage();
      let attempts = 0;
      await retry.route('**/search-index.json', route => ++attempts === 1 ?
        route.fulfill({ status: 503, body: 'Unavailable' }) : route.fulfill({ json: search }));
      await retry.goto(base + '/');
      await retry.locator('[data-open-search]').click();
      await retry.waitForFunction(() => document.querySelector('#searchStatus').textContent.includes('unavailable'));
      await retry.locator('.palette-close').click();
      await retry.locator('[data-open-search]').click();
      await retry.waitForFunction(() => document.querySelectorAll('#palette li a').length === 3);
      assert.equal(attempts, 2);
      await retry.close();
    });
    await check('Invalid search data shows an explicit error without crashing', async () => {
      const invalid = await ctx.newPage();
      await invalid.route('**/search-index.json', route => route.fulfill({ json: { invalid: true } }));
      await invalid.goto(base + '/');
      await invalid.locator('[data-open-search]').click();
      await invalid.waitForFunction(() => document.querySelector('#searchStatus').textContent.includes('unavailable'));
      await invalid.locator('.palette-close').click();
      assert.equal(await invalid.locator('#palette').isVisible(), false);
      await invalid.close();
    });
    for (const mode of ['disabled-js', 'blocked-script', 'missing-observer']) {
      await check(`Content and mobile navigation survive ${mode}`, async () => {
        const fallback = await context({ javaScriptEnabled: mode !== 'disabled-js', viewport: { width: 390, height: 844 } });
        if (mode === 'blocked-script') await fallback.route('**/site.js?*', route => route.abort());
        if (mode === 'missing-observer') await fallback.addInitScript(() => { delete window.IntersectionObserver; });
        const p = await fallback.newPage();
        await p.goto(base + '/projects/');
        assert.equal(await p.locator('.project').first().evaluate(el => getComputedStyle(el).opacity), '1');
        if (mode !== 'missing-observer') {
          assert.equal(await p.locator('#navLinks a').first().isVisible(), true);
          assert.equal(await p.locator('[data-open-search]').isVisible(), false);
        }
        assert.equal(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await fallback.close();
      });
    }
    await check('Print exposes unscrolled experience and disables reveal animation', async () => {
      await page.goto(base + '/about/');
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('[data-reveal]').last().evaluate(el => getComputedStyle(el).opacity), '1');
      assert.equal(await page.locator('[data-reveal]').last().evaluate(el => getComputedStyle(el).animationName), 'none');
      await page.emulateMedia({ media: 'screen', reducedMotion: 'reduce' });
      await page.reload();
      assert.equal(await page.locator('[data-reveal]').first().evaluate(el => getComputedStyle(el).animationName), 'none');
    });
    assert.deepEqual(errors, []);
    console.log(`${checks} browser checks passed; no uncaught page errors.`);
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
