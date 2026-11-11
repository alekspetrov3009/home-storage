/* Загрузка темы до первой отрисовки: подключается синхронно из <head>
   index.html. Вынесен в отдельный файл ради строгого CSP (script-src 'self'
   без unsafe-inline) — ключ localStorage совпадает с src/theme.ts. */
try {
  var savedTheme = localStorage.getItem("hs-theme");
  if (savedTheme === "dark" || savedTheme === "light") {
    document.documentElement.dataset.theme = savedTheme;
  }
} catch (e) {
  /* localStorage недоступен — светлая тема по умолчанию */
}
