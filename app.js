/* Daily motivation site — loads data/daily.json, supports EN/RU toggle. */
(function () {
  "use strict";

  var THEMES_URL = "data/themes.json";
  var DAILY_URL = "data/daily.json";

  var i18n = {
    en: {
      brand: "Daily Motivation",
      switch: "RU",
      themePrefix: "",
      footnote: "A new quote every day — matched to the news.",
      sourceMissing: "source"
    },
    ru: {
      brand: "Мотивация дня",
      switch: "EN",
      themePrefix: "",
      footnote: "Новая цитата каждый день — по мотивам новостей.",
      sourceMissing: "источник"
    }
  };

  var themeLabels = {}; // theme name -> {en, ru}
  var state = { lang: "en" };

  function el(id) { return document.getElementById(id); }

  function applyLanguage() {
    var t = i18n[state.lang];
    var els = document.querySelectorAll("[data-i18n]");
    els.forEach(function (e) { e.textContent = t[e.getAttribute("data-i18n")] || e.textContent; });
    document.documentElement.setAttribute("lang", state.lang);
    // re-render dynamic bits
    renderTheme(state.entry ? state.entry.theme : null);
    if (state.entry) {
      var e = state.entry;
      el("quote-text").textContent = e[state.lang] || e.en;
      el("quote-author").textContent = "— " + (e.author || "");
      renderSource(e);
    }
  }

  function renderSource(entry) {
    if (entry.source) {
      var a = el("quote-source");
      a.href = entry.source;
      a.style.display = "";
      a.textContent = entry.source.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    } else {
      el("quote-source").style.display = "none";
    }
  }

  function renderTheme(theme) {
    if (theme && themeLabels[theme]) {
      el("theme-label").textContent = themeLabels[theme][state.lang] || theme;
    } else {
      el("theme-label").textContent = "";
    }
  }

  function renderEntry(entry) {
    state.entry = entry;
    el("date-label").textContent = entry.date;
    el("quote-text").textContent = entry[state.lang] || entry.en;
    el("quote-author").textContent = "— " + (entry.author || "");
    var img = el("quote-image");
    img.src = entry.image || "";
    img.alt = "";
    renderSource(entry);
    document.querySelector(".card").classList.remove("loading");
    renderTheme(entry.theme);
  }

  function onLangToggle() {
    state.lang = state.lang === "en" ? "ru" : "en";
    try { localStorage.setItem("dl-lang", state.lang); } catch (e) {}
    applyLanguage();
  }

  function init() {
    try { var saved = localStorage.getItem("dl-lang"); if (saved) state.lang = saved; } catch (e) {}
    el("lang-toggle").addEventListener("click", onLangToggle);

    Promise.all([
      fetch(THEMES_URL).then(function (r) { return r.json(); }).catch(function () { return { themes: [] }; }),
      fetch(DAILY_URL).then(function (r) { return r.json(); }).catch(function () { return null; })
    ]).then(function (res) {
      var themes = res[0] && res[0].themes ? res[0].themes : [];
      themes.forEach(function (t) { themeLabels[t.name] = { en: t.label_en, ru: t.label_ru }; });
      var entry = res[1];
      applyLanguage();
      if (!entry) {
        el("quote-text").textContent = "😔 Could not load today's quote.";
        el("quote-text").style.fontStyle = "normal";
        return;
      }
      renderEntry(entry);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();