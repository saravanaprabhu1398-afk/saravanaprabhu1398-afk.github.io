const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Mobile nav
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');

if (navToggle) {
  navToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

// ---------------------------------------------------------------------------
// Scroll chrome: progress bar + active section
// ---------------------------------------------------------------------------
const progressBar = document.getElementById('scrollProgress');
const sections = [...document.querySelectorAll('main section[id]')];
const navMap = new Map();

document.querySelectorAll('.nav-links a[href^="#"]').forEach(a => {
  navMap.set(a.getAttribute('href').slice(1), a);
});

let ticking = false;

function onScroll() {
  const y = window.scrollY;

  if (progressBar) {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progressBar.style.width = max > 0 ? `${Math.min((y / max) * 100, 100)}%` : '0';
  }

  let activeId = null;
  for (const section of sections) {
    if (section.getBoundingClientRect().top <= 120) activeId = section.id;
  }
  navMap.forEach((link, id) => link.classList.toggle('is-active', id === activeId));
}

// Single scroll dispatcher — three separate listeners each scheduled their own
// rAF, so the browser ran three callbacks per frame instead of one.
const scrollJobs = [onScroll];
window.addEventListener('scroll', () => {
  // Skip all scroll-driven work while the tab is hidden — the browser throttles
  // rendering anyway, so the callbacks are pure waste.
  if (document.hidden) return;
  if (!ticking) {
    ticking = true;
    window.requestAnimationFrame(() => {
      for (const job of scrollJobs) job();
      ticking = false;
    });
  }
}, { passive: true });

// Re-sync once the tab comes back, since scrolls while hidden were ignored
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) for (const job of scrollJobs) job();
});

onScroll();

// ---------------------------------------------------------------------------
// Accordion
// ---------------------------------------------------------------------------
document.querySelectorAll('.acc-head').forEach(head => {
  head.addEventListener('click', () => {
    const item = head.closest('.acc-item');
    const isOpen = item.classList.contains('is-open');

    item.parentElement.querySelectorAll('.acc-item').forEach(other => {
      other.classList.remove('is-open');
      other.querySelector('.acc-head').setAttribute('aria-expanded', 'false');
    });

    if (!isOpen) {
      item.classList.add('is-open');
      head.setAttribute('aria-expanded', 'true');
    }
  });
});

// ---------------------------------------------------------------------------
// Card stack — cards scale down slightly as the next one covers them
// ---------------------------------------------------------------------------
const stackCards = [...document.querySelectorAll('.stack-card')];

const stackFits = () => stackCards.every(c => c.offsetHeight < window.innerHeight * 0.92);

if (stackCards.length && !prefersReduced) {
  const updateStack = () => {
    // If any card is taller than the screen the stack cannot work; leave them alone.
    if (!stackFits()) {
      stackCards.forEach(c => { c.style.transform = ''; c.style.opacity = ''; });
      return;
    }
    stackCards.forEach((card, i) => {
      const next = stackCards[i + 1];
      if (!next) {
        card.style.transform = '';
        card.style.opacity = '';
        return;
      }

      // A sticky card never scrolls past its own stick point, so progress is
      // measured by how close the NEXT card has come to covering this one.
      const gap = next.getBoundingClientRect().top - card.getBoundingClientRect().top;
      const span = window.innerHeight * 0.75;
      const progress = 1 - Math.min(Math.max(gap / span, 0), 1);

      card.style.transform = `scale(${1 - progress * 0.07})`;
      card.style.opacity = String(1 - progress * 0.06);
    });
  };

  scrollJobs.push(updateStack);
  updateStack();
}

// ---------------------------------------------------------------------------
// Pinned pipeline — scrub the stages against scroll position in the section
// ---------------------------------------------------------------------------
const pinned = document.querySelector('.pinned');

if (pinned && !prefersReduced) {
  const stages = [...pinned.querySelectorAll('.pl-stage')];
  const fill = document.getElementById('plFill');
  const counter = document.getElementById('plCount');

  // Only take over layout once we know the scrub can run
  pinned.classList.add('scrub-ready');

  const updatePipeline = () => {
    const rect = pinned.getBoundingClientRect();
    const scrollable = pinned.offsetHeight - window.innerHeight;
    if (scrollable <= 0) return;

    const progress = Math.min(Math.max(-rect.top / scrollable, 0), 1);

    // Ease the first stage in immediately, the last just before the section ends
    const active = Math.min(Math.floor(progress * stages.length * 1.08), stages.length - 1);

    stages.forEach((s, i) => s.classList.toggle('is-on', i <= active));
    if (fill) fill.style.width = `${(active / (stages.length - 1)) * 100}%`;
    if (counter) counter.textContent = String(active + 1).padStart(2, '0');
  };

  scrollJobs.push(updatePipeline);
  window.addEventListener('resize', updatePipeline);
  updatePipeline();
}

// ---------------------------------------------------------------------------
// Line-mask text reveal — a small SplitText stand-in
// Wraps each visual line in an overflow-hidden block so it can rise into place.
// ---------------------------------------------------------------------------
// Mask each WORD rather than rebuilding whole lines. Words stay in normal
// flow, so the browser decides the line breaks exactly as it otherwise would —
// measurement can only affect stagger timing, never layout.
function splitIntoLines(el) {
  if (el.dataset.splitText) el.textContent = el.dataset.splitText;
  const text = el.textContent.trim().replace(/\s+/g, ' ');
  el.dataset.splitText = text;

  const frag = document.createDocumentFragment();
  const masks = text.split(' ').map((word, i, arr) => {
    const outer = document.createElement('span');
    outer.className = 'split-word';
    const inner = document.createElement('span');
    inner.textContent = word;
    outer.appendChild(inner);
    frag.appendChild(outer);
    if (i < arr.length - 1) frag.appendChild(document.createTextNode(' '));
    return { outer, inner };
  });

  el.textContent = '';
  el.appendChild(frag);

  // Stagger by visual line, so a line lifts as one gesture
  let lineIndex = -1;
  let lastTop = null;
  masks.forEach(({ outer, inner }) => {
    const top = outer.offsetTop;
    if (lastTop === null || Math.abs(top - lastTop) > 4) {
      lineIndex += 1;
      lastTop = top;
    }
    inner.style.transitionDelay = `${lineIndex * 90}ms`;
  });

  el.classList.add('split-ready');
}

function initSplit() {
  const splitTargets = [...document.querySelectorAll('[data-split]')];
  splitTargets.forEach(splitIntoLines);

  const splitObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      splitObserver.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.15 });

  splitTargets.forEach(el => splitObserver.observe(el));

  // Never leave split text hidden
  setTimeout(() => splitTargets.forEach(el => el.classList.add('is-visible')), 2500);

  // Re-split on resize so line grouping stays correct
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      splitTargets.forEach(el => {
        splitIntoLines(el);
        el.classList.add('is-visible');
      });
    }, 250);
  });
}

// Lines must be measured with the real webfont loaded — measuring against the
// fallback freezes the wrong break points once Archivo swaps in.
if (!prefersReduced) {
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(initSplit);
  } else {
    window.addEventListener('load', initSplit);
  }
}

// ---------------------------------------------------------------------------
// Reveal on scroll — class is added by JS, so content is visible without it
// ---------------------------------------------------------------------------
if (!prefersReduced && 'IntersectionObserver' in window) {
  const targets = document.querySelectorAll(
    '.logo-item, .intro-statement, .intro-body, .exp-row, .acc-item, .certs, ' +
    '.contact-lead, .contact-list a, .rail-label'
  );

  const seen = new Map();
  targets.forEach(el => {
    const index = seen.get(el.parentElement) || 0;
    el.classList.add('reveal');
    el.style.transitionDelay = `${Math.min(index * 60, 240)}ms`;
    seen.set(el.parentElement, index + 1);
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });

  targets.forEach(el => observer.observe(el));

  // Safety net: never leave content hidden if the observer never fires
  // (odd viewport geometry, snapshot renderers, headless capture).
  setTimeout(() => {
    targets.forEach(el => el.classList.add('is-visible'));
  }, 2500);
}

// ---------------------------------------------------------------------------
// Liquid Glass pointer response — light follows the cursor across the material
// ---------------------------------------------------------------------------
(function initGlassInteraction() {
  if (prefersReduced) return;
  if (!window.matchMedia('(hover: hover)').matches) return; // skip on touch

  const selector = [
    '.stack-card', '.logo-item', '.contact-list a',
    '.acc-item', '.nav-cta', '.btn', '.certs li', '.metric-chip'
  ].join(',');

  const els = [...document.querySelectorAll(selector)];
  els.forEach(el => el.classList.add('glass-interactive'));

  let frame = null;
  document.addEventListener('pointermove', (e) => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      const el = e.target.closest ? e.target.closest(selector) : null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`);
      el.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`);
    });
  }, { passive: true });
})();
