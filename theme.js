/* Apply the saved appearance before the first paint; light is the default. */
(function () {
  'use strict';
  var root = document.documentElement;
  var theme = 'light';
  try {
    if (localStorage.getItem('portfolio-theme') === 'dark') theme = 'dark';
  } catch (error) {
    console.warn('Appearance preference could not be read:', error.name);
  }
  function apply(value) {
    root.dataset.theme = value;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = value === 'dark' ? '#171923' : '#f3f4f8';
    document.querySelectorAll('.theme-toggle').forEach(function (button) {
      button.setAttribute('aria-pressed', value === 'dark' ? 'true' : 'false');
      button.setAttribute('aria-label', value === 'dark' ? 'Use light appearance' : 'Use dark appearance');
    });
  }
  apply(theme);
  document.addEventListener('DOMContentLoaded', function () {
    apply(theme);
    document.querySelectorAll('.theme-toggle').forEach(function (button) {
      button.addEventListener('click', function () {
        theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        apply(theme);
        try {
          localStorage.setItem('portfolio-theme', theme);
        } catch (error) {
          console.warn('Appearance changed, but could not be saved:', error.name);
        }
      });
    });
    root.classList.add('theme-ready');
  });
})();
