/* Dropper i18n: language registry, translation lookup with plurals, and locale aware formatting.
   Translations live in /static/locales/<code>.json; English is the default and the fallback. */
(function () {
  "use strict";

  const LANGS = [
    { code: "en", name: "English", intl: "en-US" },
    { code: "de", name: "Deutsch", intl: "de-DE" },
    { code: "es", name: "Español", intl: "es-ES" },
    { code: "fr", name: "Français", intl: "fr-FR" },
    { code: "it", name: "Italiano", intl: "it-IT" },
    { code: "pt", name: "Português (Brasil)", intl: "pt-BR" },
    { code: "pl", name: "Polski", intl: "pl-PL" },
    { code: "tr", name: "Türkçe", intl: "tr-TR" },
    { code: "ru", name: "Русский", intl: "ru-RU" },
    { code: "ja", name: "日本語", intl: "ja-JP" },
    { code: "ko", name: "한국어", intl: "ko-KR" },
    { code: "zh", name: "简体中文", intl: "zh-CN" },
  ];
  const BY_CODE = Object.fromEntries(LANGS.map((l) => [l.code, l]));
  const cache = {};
  let lang = "en";
  let dict = {};
  let fallback = {};
  let intl = "en-US";
  let plural = new Intl.PluralRules(intl);
  const listeners = [];

  async function fetchLocale(code) {
    if (cache[code]) return cache[code];
    const res = await fetch(`static/locales/${code}.json?v=${window.ASSET_V || ""}`);
    if (!res.ok) throw new Error(`locale ${code}: ${res.status}`);
    cache[code] = await res.json();
    return cache[code];
  }

  function normalize(code) {
    code = String(code || "").toLowerCase().split(/[-_]/)[0];
    return BY_CODE[code] ? code : "en";
  }

  async function setLang(code) {
    code = normalize(code);
    fallback = await fetchLocale("en");
    try {
      dict = code === "en" ? fallback : await fetchLocale(code);
    } catch (e) {
      console.warn(e);
      code = "en";
      dict = fallback;
    }
    lang = code;
    intl = BY_CODE[code].intl;
    plural = new Intl.PluralRules(intl);
    document.documentElement.lang = code;
    try { localStorage.setItem("pr.lang", code); } catch (e) { /* private mode */ }
    fmtCache.clear();
    apply(document);
    listeners.forEach((fn) => fn(code));
    return code;
  }

  function lookup(key) {
    const v = dict[key];
    return v === undefined || v === "" ? fallback[key] : v;
  }

  function fill(text, params) {
    return text.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined || params[k] === null ? m : String(params[k])));
  }

  /** Plain text translation. Plural entries are objects keyed by CLDR category, chosen by params.n. */
  function t(key, params) {
    params = params || {};
    let v = lookup(key);
    if (v === undefined) return key;
    if (typeof v === "object") {
      const n = Number(params.n || 0);
      v = v[plural.select(n)] ?? v.other ?? Object.values(v)[0];
      params = Object.assign({}, params, { n: num(n) });
    }
    return fill(String(v), params);
  }

  const escMap = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => escMap[c]);

  /** HTML translation: everything is escaped, then **bold** markers become <b>. */
  function th(key, params) {
    params = params || {};
    const safe = {};
    for (const k in params) safe[k] = esc(params[k]);
    if (typeof lookup(key) === "object") safe.n = esc(num(Number(params.n || 0)));
    return fill(esc(rawPlural(key, params)), safe).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  }
  function rawPlural(key, params) {
    let v = lookup(key);
    if (v === undefined) return key;
    if (typeof v === "object") v = v[plural.select(Number(params.n || 0))] ?? v.other ?? Object.values(v)[0];
    return String(v);
  }

  /** Fills [data-i18n] (text), [data-i18n-title] and [data-i18n-placeholder] inside root. */
  function apply(root) {
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", el.title); });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  }

  // ---------------------------------------------------------------- formatting
  const fmtCache = new Map();
  function fmt(kind, opts, make) {
    const key = kind + JSON.stringify(opts);
    let f = fmtCache.get(key);
    if (!f) { f = make(intl, opts); fmtCache.set(key, f); }
    return f;
  }
  const nf = (opts) => fmt("n", opts, (l, o) => new Intl.NumberFormat(l, o));
  function num(n, digits) {
    return nf({ maximumFractionDigits: digits ?? 0 }).format(Number(n) || 0);
  }
  function compact(n) {
    n = Number(n) || 0;
    return n < 10000 ? num(n) : nf({ notation: "compact", maximumFractionDigits: 1 }).format(n);
  }
  function pct(p) {
    return nf({ style: "percent", maximumFractionDigits: 0 }).format(Math.max(0, Math.min(1, Number(p) || 0)));
  }
  function unit(value, u, display) {
    try {
      return nf({ style: "unit", unit: u, unitDisplay: display || "narrow", maximumFractionDigits: 0 }).format(value);
    } catch (e) {
      return `${num(value)} ${u}`;
    }
  }
  /** Minutes as a compact duration: "3d 4h", "2h 15m", "12m" in the user's language. */
  function dur(minutes) {
    minutes = Math.max(0, Math.round(Number(minutes) || 0));
    const d = Math.floor(minutes / 1440), h = Math.floor((minutes % 1440) / 60), m = minutes % 60;
    // narrow units are Latin letters in Japanese, Korean and Chinese; the short ones read naturally there
    const style = ["ja", "ko", "zh"].includes(lang) ? "short" : "narrow";
    const u = (v, name) => unit(v, name, style);
    if (d) return h ? `${u(d, "day")} ${u(h, "hour")}` : u(d, "day");
    if (h) return m ? `${u(h, "hour")} ${u(m, "minute")}` : u(h, "hour");
    return u(m, "minute");
  }
  function hours(minutes) {
    const h = (Number(minutes) || 0) / 60;
    return nf({ maximumFractionDigits: h < 10 ? 1 : 0 }).format(h);
  }
  function toDate(v) {
    if (!v) return null;
    const d = v instanceof Date ? v : new Date(v);
    return isNaN(d) ? null : d;
  }
  function date(v, style) {
    const d = toDate(v);
    if (!d) return "–";
    const opts = style === "short" ? { day: "numeric", month: "short" }
      : style === "time" ? { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }
      : style === "day" ? { weekday: "short", day: "numeric", month: "short" }
      : style === "weekday" ? { weekday: "short" }
      : style === "month" ? { month: "short" }
      : style === "monthyear" ? { month: "long", year: "numeric" }
      : { dateStyle: "medium", timeStyle: "short" };
    return fmt("d", opts, (l, o) => new Intl.DateTimeFormat(l, o)).format(d);
  }
  const UNITS = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60], ["second", 1]];
  /** Relative time: "in 3 days", "5 minutes ago". */
  function rel(v) {
    const d = toDate(v);
    if (!d) return "–";
    const diff = (d.getTime() - Date.now()) / 1000;
    const abs = Math.abs(diff);
    const rtf = fmt("r", { numeric: "auto" }, (l, o) => new Intl.RelativeTimeFormat(l, o));
    if (abs < 45) return rtf.format(0, "second");
    for (const [u, s] of UNITS) {
      if (abs >= s || u === "second") return rtf.format(Math.round(diff / s), u);
    }
    return "";
  }

  function onChange(fn) { listeners.push(fn); }

  window.I18N = {
    LANGS, setLang, t, th, apply, onChange, esc,
    num, compact, pct, dur, hours, date, rel,
    get lang() { return lang; },
    get intl() { return intl; },
  };
})();
