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
          if (path === '/about/') {
            const portrait = await page.locator('.portrait img').boundingBox();
            assert.ok(portrait.height <= portrait.width * 1.3, 'Portrait must not retain its HTML height at a smaller width');
          }
        });
        if (path === '/') {
          await check(`Desktop launchers and primary actions at ${width}px`, async () => {
            assert.equal(await page.locator('.hero-cta a').count(), 2);
            assert.equal(await page.locator('.dock-app[data-preview^="preview-"]').count(), 4, 'Dock carries the four project apps');
            assert.equal(await page.locator('.dock-app[data-preview="stack-folder"]').count(), 1);
            assert.equal(await page.locator('.dock a').count(), 8);
            assert.equal(await page.locator('#stack-folder .folder-grid a[href^="/projects/?filter="]').count(), 6, 'Every stack logo opens filtered projects');
            assert.equal(await page.locator('.dock-links a[href^="/"]').count(), 0, 'Dock must not repeat page navigation');
            assert.equal(await page.locator('#liveCount, .chip-float, #typed, .launcher').count(), 0);
            assert.equal(await page.locator('.hero-cta a').first().getAttribute('href'), '#contact');
            assert.equal(await page.locator('.hero-cta a').first().getAttribute('data-preview'), 'contact');
            assert.equal(await page.locator('.hero-cta a').nth(1).getAttribute('href'), '/about/#resumes');
            assert.equal(await page.locator('main h1 .profile-photo').count(), 1, 'Portrait sits inside the statement');
            assert.equal(await page.locator('main > section').count(), 1, 'Home is a single screen');
            if (width <= 390) {
              assert.ok(await page.locator('.hero-cta').evaluate(el => el.getBoundingClientRect().bottom < 580),
                'Contact and resume must appear within the first 580px on mobile');
              assert.equal(await page.locator('.profile-photo').evaluate(el => el.getBoundingClientRect().width), 60);
            }
            if (width >= 1024) {
              assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1), 'Home fits one screen on desktop');
              assert.ok(await page.locator('.hero-cta').evaluate(el =>
                el.getBoundingClientRect().bottom < document.querySelector('.dock').getBoundingClientRect().top),
              'The hero call to action must sit above the fixed dock on the first screen');
            }
            await page.goto(base + '/');
            await check('App previews open by keyboard, contain focus and restore their launcher', async () => {
              const apps = page.locator('.dock-app[data-preview^="preview-"]');
              for (let i = 0; i < await apps.count(); i++) {
                await apps.nth(i).focus();
                await page.keyboard.press('Enter');
                const dialog = page.locator('.project-preview[open]');
                assert.equal(await dialog.evaluate(el => el.matches(':modal')), true);
                assert.equal(await dialog.locator('.project h3').count(), 1);
                assert.equal(await dialog.locator('.evidence').count(), 1);
                await page.keyboard.press('Control+k');
                assert.equal(await page.locator('#palette').isVisible(), false);
                for (let j = 0; j < 7; j++) {
                  await page.keyboard.press('Tab');
                  assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true);
                }
                await page.keyboard.press('Escape');
                assert.equal(await page.locator('.project-preview[open]').count(), 0);
                await apps.nth(i).evaluate(el => new Promise((ok, fail) => {
                  const t0 = Date.now();
                  (function poll() { if (el === document.activeElement) ok(); else if (Date.now() - t0 > 2000) fail(new Error('Launcher did not regain focus; focus is on ' + (document.activeElement.outerHTML || '').slice(0, 120) + ' open=' + document.querySelectorAll('dialog[open]').length)); else requestAnimationFrame(poll); })();
                }));
              }
            });
            await check('Project window supports close, backdrop dismissal and full-page navigation', async () => {
              const app = page.locator('.dock-app[data-preview^="preview-"]').first();
              await app.click();
              await page.locator('.project-preview[open] [data-close-preview]').click();
              await app.evaluate(el => new Promise((ok, fail) => { const t0 = Date.now(); (function poll() { if (el === document.activeElement) ok(); else if (Date.now() - t0 > 2000) fail(new Error('Launcher did not regain focus; focus is on ' + (document.activeElement.outerHTML || '').slice(0, 120) + ' open=' + document.querySelectorAll('dialog[open]').length)); else requestAnimationFrame(poll); })(); }));
              await app.click();
              await page.locator('.project-preview[open]').click({ position: { x: 1, y: 1 } });
              await app.evaluate(el => new Promise((ok, fail) => { const t0 = Date.now(); (function poll() { if (el === document.activeElement) ok(); else if (Date.now() - t0 > 2000) fail(new Error('Launcher did not regain focus; focus is on ' + (document.activeElement.outerHTML || '').slice(0, 120) + ' open=' + document.querySelectorAll('dialog[open]').length)); else requestAnimationFrame(poll); })(); }));
              await app.click();
              await page.locator('.project-preview[open] .preview-more').click();
              await page.waitForURL('**/projects/#project-flightpulse');
              assert.equal(await page.locator('#project-flightpulse').isVisible(), true);
            });
            await check('Appearance persists across pages and reload, with correct accessible state', async () => {
              await page.goto(base + '/');
              assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
              await page.locator('.theme-toggle').click();
              assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
              assert.equal(await page.locator('.theme-toggle').getAttribute('aria-pressed'), 'true');
              const contrast = await page.locator('.btn.primary').first().evaluate(el => {
                const style = getComputedStyle(el);
                const luminance = value => {
                  const rgb = value.match(/\d+/g).slice(0, 3).map(Number).map(v => {
                    const s = v / 255;
                    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
                  });
                  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
                };
                const fg = luminance(style.color), bg = luminance(style.backgroundColor);
                return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
              });
              assert.ok(contrast >= 4.5, 'Primary CTA must retain contrast immediately after changing theme');
              await page.goto(base + '/blog/');
              await page.reload();
              assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
              assert.equal(await page.locator('.theme-toggle').getAttribute('aria-label'), 'Use light appearance');
              await page.locator('.theme-toggle').click();
              assert.equal(await page.evaluate(() => localStorage.getItem('portfolio-theme')), 'light');
            });
            await check('Appearance remains usable when preference storage is blocked', async () => {
              const blocked = await context();
              await blocked.addInitScript(() => {
                Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Blocked', 'SecurityError'); } });
              });
              const p = await blocked.newPage();
              const warnings = [];
              p.on('console', message => { if (message.type() === 'warning') warnings.push(message.text()); });
              await p.goto(base + '/');
              await p.locator('.theme-toggle').click();
              assert.equal(await p.locator('html').getAttribute('data-theme'), 'dark');
              assert.ok(warnings.some(message => message.includes('could not be saved')));
              await blocked.close();
            });
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
    await check('The menu bar keeps three pages; contact and résumés live in windows', async () => {
      await page.goto(base + '/about/');
      assert.deepEqual(await page.locator('#navLinks a').allTextContents(), ['Projects', 'Writing', 'About']);
      assert.equal(await page.locator('#navLinks a[href*="#contact"]').count(), 0);
    });
    await check('Contact opens as a window from the CTA and a shared link', async () => {
      await page.goto(base + '/');
      const cta = page.locator('.hero-cta a').first();
      await cta.click();
      assert.equal(await page.locator('#contact').evaluate(el => el.matches(':modal')), true);
      await page.keyboard.press('Escape');
      await cta.evaluate(el => new Promise((ok, fail) => { const t0 = Date.now(); (function poll() { if (el === document.activeElement) ok(); else if (Date.now() - t0 > 2000) fail(new Error('CTA did not regain focus')); else requestAnimationFrame(poll); })(); }));
      await page.goto(base + '/about/');
      await page.goto(base + '/#contact');
      assert.equal(await page.locator('#contact').evaluate(el => el.open), true, '/#contact opens the window on arrival');
      await page.locator('#contact [data-close-preview]').click();
      await page.waitForFunction(() => location.hash === '', null, { timeout: 2000 }); // closing clears the hash so the link works again
    });
    await check('CV opens as a window from the nav on every page and from the hero link', async () => {
      for (const path of ['/', '/projects/', '/blog/publishing-pipeline/']) {
        await page.goto(base + path);
        await page.locator('.cv-btn').click();
        const cv = page.locator('#cv');
        assert.equal(await cv.evaluate(el => el.matches(':modal')), true);
        assert.equal(await cv.locator('a[download][href$=".pdf"]').count(), 3);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#cv[open]').count(), 0);
      }
      await page.goto(base + '/');
      await page.locator('.hero-cta .scribble-link').click();
      assert.equal(await page.locator('#cv').evaluate(el => el.open), true);
      await page.keyboard.press('Escape');
    });
    await check('Moved home sections live on Projects', async () => {
      await page.goto(base + '/projects/');
      assert.equal(await page.locator('#project-spotlight').count(), 1);
      assert.equal(await page.locator('#case-studies').count(), 1);
      assert.equal(await page.locator('.flow-lane').count(), 2);
      assert.equal(await page.locator('.flow-steps li').count(), 6);
    });
    await check('The Stack folder opens in place and a logo opens filtered Projects', async () => {
      await page.goto(base + '/');
      await page.locator('.dock-app[data-preview="stack-folder"]').click();
      assert.equal(await page.locator('#stack-folder').evaluate(el => el.matches(':modal')), true);
      await page.locator('#stack-folder a[href="/projects/?filter=streaming"]').click();
      await page.waitForURL('**/projects/?filter=streaming');
      assert.equal(await page.locator('[data-filter="streaming"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('.project:visible').count(), 3);
      await page.goto(base + '/projects/?filter=nonsense');
      assert.equal(await page.locator('[data-filter="all"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('.project:visible').count(), 10);
    });
    await check('Project filtering preserves matching cards and restores all', async () => {
      await page.locator('[data-filter="streaming"]').click();
      assert.equal(await page.locator('.project:visible').count(), 3);
      await page.locator('[data-filter="all"]').click();
      assert.equal(await page.locator('.project:visible').count(), 10);
      assert.equal(await page.locator('.evidence b').first().evaluate(el => getComputedStyle(el).fontSize), '11px');
    });

    await page.route('**/search-index.json', route => route.fulfill({ json: search }));
    await page.goto(base + '/');
    await check('Selecting a same-page result navigates and dismisses search', async () => {
      await page.locator('[data-open-search]').click();
      await page.waitForFunction(() => document.querySelectorAll('#palette li a').length === 3);
      await page.locator('#palette li a').nth(1).click();
      await page.waitForURL('**/#contact');
      assert.equal(await page.locator('#palette').isVisible(), false);
      await page.waitForFunction(() => document.getElementById('contact').open);
      await page.locator('#contact [data-close-preview]').click();
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
        await p.goto(base + '/');
        assert.equal(await p.locator('.dock-app[data-preview^="preview-"]').count(), 4);
        if (mode !== 'missing-observer') {
          await p.locator('.dock-app[data-preview^="preview-"]').first().click();
          await p.waitForURL('**/projects/#project-flightpulse');
        }
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
