/* Archive: joins data/history.json (date, id, theme) with data/quotes.json (text). */
(function () {
  "use strict";
  var T = {
    en: { brand: "Daily Motivation", title: "Archive", back: "Today", empty: "No archive yet.", sw: "RU" },
    ru: { brand: "Мотивация дня", title: "Архив", back: "Сегодня", empty: "Архив пока пуст.", sw: "EN" }
  };
  var lang = "en", data = null;

  function get(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }

  function render() {
    var t = T[lang];
    document.documentElement.lang = lang;
    document.title = t.title + " — " + t.brand;
    document.getElementById("brand-label").textContent = t.brand;
    document.getElementById("lang-toggle").textContent = t.sw;
    var list = document.getElementById("list");
    list.textContent = "";
    var h1 = document.createElement("h1");
    h1.textContent = t.title;
    list.appendChild(h1);
    var rows = data ? data.rows : [];
    if (!rows.length) {
      var p = document.createElement("p");
      p.className = "archive-empty";
      p.textContent = t.empty;
      list.appendChild(p);
      return;
    }
    rows.forEach(function (r) {
      var item = document.createElement("article");
      item.className = "archive-item";
      var meta = document.createElement("div");
      meta.className = "meta-row";
      var th = document.createElement("span");
      th.className = "archive-theme";
      var lab = data.labels[r.theme];
      th.textContent = lab ? (lab[lang] || lab.en) : r.theme;
      var d = document.createElement("span");
      d.textContent = r.date;
      meta.appendChild(th);
      meta.appendChild(d);
      var q = document.createElement("blockquote");
      q.textContent = r.quote[lang] || r.quote.en;
      var a = document.createElement("p");
      a.className = "quote-author";
      a.textContent = "— " + r.quote.author;
      item.appendChild(meta);
      item.appendChild(q);
      item.appendChild(a);
      list.appendChild(item);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var saved = null;
    try { saved = localStorage.getItem("dl-lang"); } catch (e) {}
    lang = T[saved] ? saved : (/^ru/i.test(navigator.language || "") ? "ru" : "en");
    document.getElementById("lang-toggle").addEventListener("click", function () {
      lang = lang === "en" ? "ru" : "en";
      try { localStorage.setItem("dl-lang", lang); } catch (e) {}
      render();
    });
    Promise.all([get("data/history.json"), get("data/quotes.json"), get("data/themes.json").catch(function () { return {}; })])
      .then(function (res) {
        var byId = {};
        res[1].forEach(function (q) { byId[q.id] = q; });
        var labels = {};
        (res[2].themes || []).forEach(function (t) { labels[t.name] = { en: t.label_en, ru: t.label_ru }; });
        var rows = res[0].filter(function (h) { return byId[h.id]; })
          .map(function (h) { return { date: h.date, theme: h.theme, quote: byId[h.id] }; })
          .sort(function (a, b) { return a.date < b.date ? 1 : -1; });
        data = { rows: rows, labels: labels };
        render();
      })
      .catch(function () { data = null; render(); });
  });
})();
