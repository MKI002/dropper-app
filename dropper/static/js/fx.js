/* Dropper motion helpers: count-up numbers and list reordering that slides instead of jumping.
   Both stay still for people who ask their system for reduced motion. */
(function () {
  "use strict";

  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------------------------------------------------------------- count-up
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  function countTo(el, to, format) {
    to = Number(to) || 0;
    const from = typeof el._val === "number" ? el._val : 0;
    el._val = to;
    if (el._raf) cancelAnimationFrame(el._raf);
    if (reduced() || from === to) { el.textContent = format(to); return; }
    const start = performance.now(), duration = 700;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      el.textContent = format(from + (to - from) * easeOut(t));
      if (t < 1) el._raf = requestAnimationFrame(step);
    };
    el._raf = requestAnimationFrame(step);
  }

  // ---------------------------------------------------------------- reorder (FLIP)
  /** Runs change() (which re-renders synchronously) and slides elements matching selector,
      identified by data-key, from their old to their new place. */
  function flip(selector, change) {
    const before = new Map(Array.from(document.querySelectorAll(selector), (el) => [el.dataset.key, el.getBoundingClientRect().top]));
    change();
    if (reduced()) return;
    document.querySelectorAll(selector).forEach((el) => {
      const top = before.get(el.dataset.key);
      const dy = top === undefined ? 0 : top - el.getBoundingClientRect().top;
      if (dy) el.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 380, easing: "cubic-bezier(.3, 1.3, .6, 1)" });
    });
  }

  window.FX = { countTo, flip, reduced };
})();
