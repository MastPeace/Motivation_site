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
      sourcePrefix: "Source:"
    },
    ru: {
      brand: "Мотивация дня",
      switch: "EN",
      themePrefix: "",
      footnote: "Новая цитата каждый день — по мотивам новостей.",
      sourcePrefix: "Источник:"
    }
  };

  var themeLabels = {}; // theme name -> {en, ru}
  var state = { lang: "en", entry: null };

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

  var SOURCE_NAMES = { "en.wikiquote.org": "Wikiquote", "www.brainyquote.com": "BrainyQuote" };

  function renderSource(entry) {
    var a = el("quote-source");
    if (!entry.source) { a.style.display = "none"; return; }
    var host = "";
    try { host = new URL(entry.source).hostname; } catch (e) { a.style.display = "none"; return; }
    a.href = entry.source;
    a.style.display = "";
    a.textContent = i18n[state.lang].sourcePrefix + " " + (SOURCE_NAMES[host] || host.replace(/^www\./, ""));
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
    img.onerror = function () { img.style.display = "none"; };  // broken photo: hide, keep the quote
    img.style.display = "";
    img.src = entry.image || "";
    img.alt = "";
    renderSource(entry);
    renderTheme(entry.theme);
  }

  function onLangToggle() {
    state.lang = state.lang === "en" ? "ru" : "en";
    try { localStorage.setItem("dl-lang", state.lang); } catch (e) {}
    applyLanguage();
  }

  function init() {
    // saved choice wins; otherwise follow the browser language. Ignore unknown values.
    var saved = null;
    try { saved = localStorage.getItem("dl-lang"); } catch (e) {}
    if (!i18n[saved]) saved = /^ru/i.test(navigator.language || "") ? "ru" : "en";
    state.lang = saved;
    el("lang-toggle").addEventListener("click", onLangToggle);

    Promise.all([
      fetch(THEMES_URL, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(function () { return { themes: [] }; }),
      fetch(DAILY_URL, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(function () { return null; })
    ]).then(function (res) {
      var themes = res[0] && res[0].themes ? res[0].themes : [];
      themes.forEach(function (t) { themeLabels[t.name] = { en: t.label_en, ru: t.label_ru }; });
      var entry = res[1];
      if (!entry) {
        applyLanguage();
        el("quote-text").textContent = state.lang === "ru" ? "😔 Не удалось загрузить цитату дня." : "😔 Could not load today's quote.";
        el("quote-text").style.fontStyle = "normal";
        return;
      }
      renderEntry(entry);
      applyLanguage();
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();