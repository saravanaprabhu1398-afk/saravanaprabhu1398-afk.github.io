/* site.js: nav, typing line, reveal, project filters, live GitHub feed, ⌘K search. No dependencies. */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var USER = 'saravanaprabhu1398-afk';

  // ---- Mobile menu
  var menuBtn = document.getElementById('menuBtn');
  var navLinks = document.getElementById('navLinks');
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    navLinks.addEventListener('click', function (e) {
      if (e.target.closest('a')) { navLinks.classList.remove('open'); menuBtn.setAttribute('aria-expanded', 'false'); }
    });
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

  // ---- Typed line
  var typed = document.getElementById('typed');
  if (typed && !reduced) {
    var words = (typed.getAttribute('data-words') || '').split('|').filter(Boolean);
    var wi = 0, ci = 0, del = false;
    (function tick() {
      var w = words[wi];
      ci += del ? -1 : 1;
      typed.textContent = w.slice(0, ci);
      var delay = del ? 35 : 70;
      if (!del && ci === w.length) { del = true; delay = 1600; }
      else if (del && ci === 0) { del = false; wi = (wi + 1) % words.length; delay = 300; }
      setTimeout(tick, delay);
    })();
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
  }

  // ---- Live GitHub feed (home). Hidden if the API is unreachable.
  var feedList = document.getElementById('feedList');
  var liveCount = document.getElementById('liveCount');
  if (feedList || liveCount) {
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
      if (liveCount) liveCount.textContent = own.length;
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
        if (note) { note.textContent = 'Live from GitHub · ' + own.length + ' public projects · last push ' + ago(own[0].pushed_at); note.hidden = false; }
      }
    }).catch(function () {});
  }

  // ---- ⌘K search palette
  var pal = document.getElementById('palette');
  if (pal) {
    var input = pal.querySelector('input'), list = pal.querySelector('ul'), index = null, sel = 0, shown = [];
    var load = function () {
      if (index) return Promise.resolve(index);
      return fetch('/search-index.json').then(function (r) { return r.json(); }).then(function (j) { index = j; return j; }).catch(function () { index = []; return index; });
    };
    var render = function () {
      var q = input.value.trim().toLowerCase();
      shown = (index || []).filter(function (x) { return !q || (x.t + ' ' + x.d + ' ' + x.k + ' ' + (x.x || '')).toLowerCase().indexOf(q) > -1; }).slice(0, 8);
      sel = 0; list.textContent = '';
      if (!shown.length) { var e = document.createElement('li'); e.className = 'empty'; e.textContent = 'Nothing found.'; list.append(e); return; }
      shown.forEach(function (x, i) {
        var li = document.createElement('li'), a = document.createElement('a'); a.href = x.u; if (i === 0) a.className = 'sel';
        if (/^https?:/.test(x.u)) { a.target = '_blank'; a.rel = 'noopener'; }
        var k = document.createElement('span'); k.className = 'k'; k.textContent = x.k;
        var m = document.createElement('div'), s = document.createElement('strong'), sm = document.createElement('small');
        s.textContent = x.t; sm.textContent = x.d; m.append(s, sm); a.append(k, m); li.append(a); list.append(li);
      });
    };
    var open = function () { load().then(function () { pal.classList.add('open'); input.value = ''; render(); input.focus(); }); };
    var close = function () { pal.classList.remove('open'); };
    document.querySelectorAll('[data-open-search]').forEach(function (b) { b.addEventListener('click', open); });
    pal.addEventListener('click', function (e) { if (e.target === pal) close(); });
    input.addEventListener('input', render);
    document.addEventListener('keydown', function (e) {
      var typing = /INPUT|TEXTAREA/.test((document.activeElement || {}).tagName || '');
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); open(); return; }
      if (!pal.classList.contains('open')) return;
      var links = list.querySelectorAll('a');
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowDown' && links.length) { e.preventDefault(); sel = (sel + 1) % links.length; }
      else if (e.key === 'ArrowUp' && links.length) { e.preventDefault(); sel = (sel - 1 + links.length) % links.length; }
      else if (e.key === 'Enter' && links[sel]) { links[sel].click(); return; }
      else return;
      links.forEach(function (l, i) { l.classList.toggle('sel', i === sel); });
      if (links[sel]) links[sel].scrollIntoView({ block: 'nearest' });
    });
  }
})();
