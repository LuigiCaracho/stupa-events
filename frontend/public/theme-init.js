/* Sets data-theme before the first paint, so a dark-theme visitor never sees a light flash. Same rule as ThemeService (key ev.theme). */
(function () {
  var dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  try {
    var stored = localStorage.getItem('ev.theme');
    if (stored === 'light' || stored === 'dark') dark = stored === 'dark';
  } catch (e) {
    /* storage blocked: follow the system */
  }
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
})();
