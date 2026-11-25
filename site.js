/* site.js: nav, reveal, project filters, live GitHub feed, ⌘K search. No dependencies. */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var USER = 'saravanaprabhu1398-afk';

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
    pal.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var focusable = pal.querySelectorAll('button, input, a[href]');
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    document.addEventListener('keydown', function (e) {
      var active = document.activeElement;
      var typing = active && (/INPUT|TEXTAREA|SELECT/.test(active.tagName) || active.isContentEditable);
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); open(); return; }
    });
    document.documentElement.classList.add('search-ready');
  }
})();
