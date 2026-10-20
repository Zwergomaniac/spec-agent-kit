// Setzt die Dark-Mode-Klasse vor dem ersten Rendern (verhindert Aufblitzen). Als Datei statt Inline-Skript,
// weil die CSP des Dashboards nur script-src 'self' erlaubt.
;(function () {
  var mode = 'system'
  try {
    mode = localStorage.getItem('sak-theme') || 'system'
  } catch (e) {}
  var dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
})()
