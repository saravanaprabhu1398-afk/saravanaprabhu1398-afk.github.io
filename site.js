/* site.js: navigation, project previews/filters, live GitHub feed and search. */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var USER = 'saravanaprabhu1398-afk';

  function containTab(dialog, event) {
    if (event.key !== 'Tab') return;
    var focusable = dialog.querySelectorAll('button, input, a[href]');
    var first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  // ---- Windows: project previews, the contact window and the Stack folder.
  // Links with data-preview stay ordinary links when their window is not on the page.
  var hashWindow = function () {
    var d = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    return d && d.matches && d.matches('dialog.project-preview') ? d : null;
  };
  var openWindow = function (dialog, from) {
    if (dialog.open) return;
    document.querySelectorAll('dialog.project-preview[open]').forEach(function (d) { d.close(); });
    dialog._opener = from || document.activeElement;
    dialog.showModal();
    document.body.classList.add('preview-open');
    dialog.querySelector('[data-close-preview]').focus();
  };
  document.querySelectorAll('dialog.project-preview').forEach(function (dialog) {
    if (typeof dialog.showModal !== 'function') return;
    dialog.querySelector('[data-close-preview]').addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('keydown', function (event) { containTab(dialog, event); });
    dialog.addEventListener('close', function () {
      document.body.classList.remove('preview-open');
      if (hashWindow() === dialog) history.replaceState(null, '', location.pathname + location.search);
      var o = dialog._opener;
      // The browser usually restores focus itself; only step in if focus was left nowhere useful,
      // so a late close event never pulls focus back from wherever the visitor has moved on to.
      var here = document.activeElement;
      if (o && o.isConnected && o !== document.body && (!here || here === document.body || dialog.contains(here))) o.focus();
    });
  });
  document.querySelectorAll('[data-preview]').forEach(function (link) {
    var dialog = document.getElementById(link.dataset.preview);
    if (!dialog || typeof dialog.showModal !== 'function') return;
    link.setAttribute('aria-haspopup', 'dialog');
    link.setAttribute('aria-controls', dialog.id);
    link.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      openWindow(dialog, link);
    });
  });
  // /#contact (from any page, the nav or a shared link) opens that window on arrival.
  var fromHash = function () { var d = hashWindow(); if (d && typeof d.showModal === 'function') openWindow(d, null); };
  window.addEventListener('hashchange', fromHash);
  fromHash();

  // ---- Home: faint particles drifting behind the hero (static when motion is reduced).
  var stage = document.querySelector('.desktop');
  var cv = stage && document.createElement('canvas');
  if (cv && cv.getContext && window.innerWidth > 640) {
    cv.className = 'drift'; cv.setAttribute('aria-hidden', 'true');
    document.body.insertBefore(cv, document.body.firstChild);
    document.documentElement.classList.add('has-drift');
    var ctx = cv.getContext('2d'), dots = [], tint = '', W = 0, H = 0;
    var readTint = function () { tint = getComputedStyle(document.documentElement).getPropertyValue('--soft').trim() || '#8090a8'; };
    var size = function () {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth; H = window.innerHeight;
      cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var want = Math.round(W * H / 20000);
      while (dots.length < want) dots.push({ x: Math.random() * W, y: Math.random() * H, r: 0.7 + Math.random() * 1.3,
        vx: (Math.random() - 0.5) * 0.24, vy: (Math.random() - 0.5) * 0.24, a: 0.18 + Math.random() * 0.32 });
      dots.length = want;
    };
    var draw = function () {
      ctx.clearRect(0, 0, W, H); ctx.fillStyle = tint;
      dots.forEach(function (d) {
        if (!reduced) {
          d.x += d.vx; d.y += d.vy;
          if (d.x < -4) d.x = W + 4; else if (d.x > W + 4) d.x = -4;
          if (d.y < -4) d.y = H + 4; else if (d.y > H + 4) d.y = -4;
        }
        ctx.globalAlpha = d.a; ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 6.2832); ctx.fill();
      });
      ctx.globalAlpha = 1;
      if (!reduced) requestAnimationFrame(draw);
    };
    readTint(); size();
    window.addEventListener('resize', function () { size(); if (reduced) draw(); }, { passive: true });
    new MutationObserver(function () { readTint(); if (reduced) draw(); })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    draw();
  }

  // ---- Home: the "latest post" notification slides in once per visit, clear of the dock.
  var toast = document.getElementById('toast');
  var seen = false;
  try { seen = sessionStorage.getItem('toast-dismissed') === '1'; } catch (err) { /* storage blocked: show it */ }
  if (toast && !seen && window.matchMedia('(min-width: 1100px)').matches) {
    setTimeout(function () {
      toast.hidden = false;
      var dk = document.querySelector('.dock');
      if (dk) {
        var a = toast.getBoundingClientRect(), b = dk.getBoundingClientRect();
        if (a.left < b.right && a.top < b.bottom) toast.style.bottom = (window.innerHeight - b.top + 12) + 'px';
      }
      requestAnimationFrame(function () { requestAnimationFrame(function () { toast.classList.add('in'); }); });
    }, 2400);
    toast.querySelector('.toast-close').addEventListener('click', function () {
      toast.classList.remove('in');
      setTimeout(function () { toast.hidden = true; }, reduced ? 0 : 600);
      try { sessionStorage.setItem('toast-dismissed', '1'); } catch (err) { /* nothing to remember */ }
    });
  }

  // ---- Dock: step aside while reading downwards, return on scroll up and at the page end.
  var dock = document.querySelector('.dock');
  if (dock) {
    var lastY = window.scrollY, ticking = false;
    var updateDock = function () {
      var y = window.scrollY;
      var atEnd = window.innerHeight + y >= document.documentElement.scrollHeight - 40;
      if (atEnd || y < 160 || y < lastY - 4) dock.classList.remove('dock-away');
      else if (y > lastY + 4) dock.classList.add('dock-away');
      lastY = y;
      ticking = false;
    };
    window.addEventListener('scroll', function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(updateDock); }
    }, { passive: true });
  }

  // ---- Mobile menu
  var menuBtn = document.getElementById('menuBtn');
  var navLinks = document.getElementById('navLinks');
  if (menuBtn && navLinks) {
    var closeMenu = function () { navLinks.classList.remove('open'); menuBtn.setAttribute('aria-expanded', 'false'); };
    menuBtn.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    navLinks.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && navLinks.classList.contains('open')) { closeMenu(); menuBtn.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.nav')) closeMenu();
    });
    document.documentElement.classList.add('nav-ready');
  }

  // ---- Reveal on scroll
  var items = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window && !reduced) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('in'); });
  }

  // ---- Project filters
  var fbar = document.getElementById('filters');
  if (fbar) {
    fbar.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      fbar.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      var tag = b.getAttribute('data-filter');
      document.querySelectorAll('.project[data-tags]').forEach(function (p) {
        p.hidden = !(tag === 'all' || p.getAttribute('data-tags').split(' ').indexOf(tag) > -1);
      });
    });
    document.documentElement.classList.add('filters-ready');
    // Dock stack logos link here as /projects/?filter=<category>.
    var wanted = new URLSearchParams(location.search).get('filter');
    var preset = wanted && fbar.querySelector('button[data-filter="' + wanted.replace(/[^a-z]/g, '') + '"]');
    if (preset) preset.click();
  }

  // ---- Live GitHub feed (home). Hidden if the API is unreachable.
  var feedList = document.getElementById('feedList');
  if (feedList) {
    var KEY = 'gh-repos-v2';
    var cached = null;
    try { var c = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (c && Date.now() - c.t < 600000) cached = c.repos; } catch (e) {}
    var get = cached ? Promise.resolve(cached) :
      fetch('https://api.github.com/users/' + USER + '/repos?per_page=100&sort=pushed')
        .then(function (r) { if (!r.ok) throw new Error('gh'); return r.json(); })
        .then(function (repos) { try { sessionStorage.setItem(KEY, JSON.stringify({ t: Date.now(), repos: repos })); } catch (e) {} return repos; });
    get.then(function (repos) {
      var own = repos.filter(function (x) { return !x.fork && x.language && x.name !== USER + '.github.io'; });
      if (!own.length) return;
      var ago = function (iso) {
        var d = Math.max(0, Math.floor((Date.now() - new Date(iso)) / 86400000));
        if (d === 0) return 'today'; if (d === 1) return 'yesterday'; if (d < 30) return d + ' days ago';
        var m = Math.floor(d / 30); return m === 1 ? '1 month ago' : m + ' months ago';
      };
      if (feedList) {
        own.slice(0, 4).forEach(function (x) {
          var a = document.createElement('a'); a.className = 'card feed-item'; a.href = x.html_url; a.target = '_blank'; a.rel = 'noopener';
          var k = document.createElement('span'); k.className = 'kind'; k.textContent = 'Repo';
          var mid = document.createElement('div'); var s = document.createElement('strong'); s.textContent = x.name.replace(/[-_]/g, ' ');
          var d = document.createElement('span'); d.className = 'd'; d.textContent = x.description || x.language;
          mid.append(s, d);
          var w = document.createElement('span'); w.className = 'when'; w.textContent = ago(x.pushed_at);
          a.append(k, mid, w); feedList.append(a);
        });
        feedList.hidden = false;
        var note = document.getElementById('liveNote');
        if (note) { note.textContent = 'Live from GitHub · last push ' + ago(own[0].pushed_at); note.hidden = false; }
      }
    }).catch(function () {});
  }

  // ---- ⌘K search palette
  var pal = document.getElementById('palette');
  if (pal && typeof pal.showModal === 'function') {
    var input = pal.querySelector('input'), list = pal.querySelector('ul'), index = null, sel = 0, shown = [];
    var status = document.getElementById('searchStatus'), opener = null, loading = null, loadError = false;
    var load = function () {
      if (index) return Promise.resolve(index);
      if (loading) return loading;
      loading = fetch('/search-index.json').then(function (r) {
        if (!r.ok) throw new Error('Search request failed: ' + r.status);
        return r.json();
      }).then(function (j) {
        if (!Array.isArray(j) || !j.every(function (x) {
          return x && ['t', 'd', 'k', 'u'].every(function (key) { return typeof x[key] === 'string'; });
        })) throw new Error('Invalid search index');
        index = j;
        return j;
      }).finally(function () { loading = null; });
      return loading;
    };
    var render = function () {
      if (!index) {
        list.textContent = '';
        status.textContent = loadError ? 'Search is unavailable. Close and reopen to retry.' : 'Loading search…';
        return;
      }
      var q = input.value.trim().toLowerCase();
      shown = (index || []).filter(function (x) { return !q || (x.t + ' ' + x.d + ' ' + x.k + ' ' + (x.x || '')).toLowerCase().indexOf(q) > -1; }).slice(0, 8);
      sel = 0; list.textContent = '';
      status.textContent = shown.length ? shown.length + ' results. Use arrow keys or Tab to explore.' : 'No results. Try a project, skill, or résumé.';
      if (!shown.length) { var e = document.createElement('li'); e.className = 'empty'; e.textContent = 'Nothing found.'; list.append(e); return; }
      shown.forEach(function (x, i) {
        var li = document.createElement('li'), a = document.createElement('a'); a.href = x.u; if (i === 0) a.className = 'sel';
        if (/^https?:/.test(x.u)) { a.target = '_blank'; a.rel = 'noopener'; }
        var k = document.createElement('span'); k.className = 'k'; k.textContent = x.k;
        var m = document.createElement('div'), s = document.createElement('strong'), sm = document.createElement('small');
        s.textContent = x.t; sm.textContent = x.d; m.append(s, sm); a.append(k, m); li.append(a); list.append(li);
      });
    };
    var open = function () {
      if (pal.open) { input.focus(); return; }
      opener = document.activeElement;
      loadError = false;
      input.value = '';
      pal.showModal();
      document.body.classList.add('search-open');
      render();
      input.focus();
      load().then(render).catch(function (error) {
        console.error('Site search:', error);
        loadError = true;
        render();
      });
    };
    var close = function () { pal.close(); };
    document.querySelectorAll('[data-open-search]').forEach(function (b) { b.addEventListener('click', open); });
    pal.querySelector('.palette-close').addEventListener('click', close);
    pal.addEventListener('close', function () {
      document.body.classList.remove('search-open');
      if (opener && opener.isConnected) opener.focus();
    });
    pal.addEventListener('click', function (e) { if (e.target === pal || e.target.closest('a')) close(); });
    input.addEventListener('input', render);
    var select = function (links) {
      links.forEach(function (l, i) { l.classList.toggle('sel', i === sel); });
      if (links[sel]) {
        links[sel].scrollIntoView({ block: 'nearest' });
        status.textContent = (sel + 1) + ' of ' + shown.length + ': ' + shown[sel].t;
      }
    };
    list.addEventListener('focusin', function (e) {
      var links = Array.from(list.querySelectorAll('a'));
      sel = links.indexOf(e.target);
      select(links);
    });
    input.addEventListener('keydown', function (e) {
      var links = list.querySelectorAll('a');
      if (!links.length || e.isComposing) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = (sel + 1) % links.length; }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = (sel - 1 + links.length) % links.length; }
      else if (e.key === 'Enter') { e.preventDefault(); links[sel].click(); return; }
      else return;
      select(links);
    });
    pal.addEventListener('keydown', function (e) { containTab(pal, e); });
    document.addEventListener('keydown', function (e) {
      var active = document.activeElement;
      if (document.querySelector('.project-preview[open]')) return;
      var typing = active && (/INPUT|TEXTAREA|SELECT/.test(active.tagName) || active.isContentEditable);
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); open(); return; }
    });
    document.documentElement.classList.add('search-ready');
  }
})();
