/* Orrery mock motion — interaction-first, not load theater */

(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const root = document.documentElement;

  function syncMotionPref() {
    root.dataset.motion = reduce.matches ? "reduce" : "full";
  }
  syncMotionPref();
  reduce.addEventListener("change", syncMotionPref);

  function prefersReduce() {
    return reduce.matches;
  }

  function settleDigest(el, finalText, ms) {
    if (!el || prefersReduce()) {
      if (el) el.textContent = finalText;
      return;
    }
    const chars = "0123456789abcdef";
    const prefix = finalText.startsWith("sha256:") ? "sha256:" : "";
    const body = finalText.slice(prefix.length);
    const start = performance.now();
    function frame(now) {
      const t = Math.min(1, (now - start) / ms);
      if (t < 0.75) {
        let out = prefix;
        for (let i = 0; i < body.length; i++) {
          out += body[i] === "…" || body[i] === "." ? body[i] : chars[(Math.random() * 16) | 0];
        }
        el.textContent = out;
        requestAnimationFrame(frame);
      } else {
        el.textContent = finalText;
        el.classList.add("value-settled");
      }
    }
    requestAnimationFrame(frame);
  }

  /** Resolve: page is ready immediately; Lookup does the Value Change beat. */
  function initResolve() {
    const table = document.querySelector("[data-resolve-table]");
    if (!table) return;

    const rows = [...table.querySelectorAll("tbody tr")];
    rows.forEach((row) => {
      row.classList.add("row-live");
      const digest = row.querySelector("[data-digest]");
      const price = row.querySelector("[data-price]");
      if (digest?.dataset.final) digest.textContent = digest.dataset.final;
      if (price?.dataset.final) price.textContent = price.dataset.final;
    });

    const form = document.querySelector("[data-resolve-form]");
    const input = form?.querySelector("input[name='q']");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = (input?.value || "").trim().toLowerCase();
      const match =
        rows.find((r) => (r.dataset.name || "").includes(q.replace(/^orrery\//, ""))) ||
        rows.find((r) => (r.dataset.name || "").includes(q)) ||
        rows[0];

      rows.forEach((r) => r.classList.remove("row-resolved"));
      match.classList.add("row-resolved");

      const digest = match.querySelector("[data-digest]");
      if (digest?.dataset.final) settleDigest(digest, digest.dataset.final, 280);

      const href = match.dataset.href || "star.html";
      window.setTimeout(
        () => {
          window.location.href = href;
        },
        prefersReduce() ? 40 : 320,
      );
    });
  }

  /** Constellation: quick staggered reveal only when the chart enters view. */
  function initConstellation() {
    const stage = document.querySelector("[data-constellation]");
    if (!stage) return;

    if (prefersReduce()) {
      stage.classList.add("is-revealed", "is-static");
      return;
    }

    const reveal = () => stage.classList.add("is-revealed");

    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            reveal();
            io.disconnect();
          }
        },
        { threshold: 0.25 },
      );
      io.observe(stage);
    } else {
      requestAnimationFrame(reveal);
    }
  }

  /** Star: seal receipt once, fast. */
  function initStarReceipt() {
    const receipt = document.querySelector("[data-receipt]");
    if (!receipt) return;
    if (prefersReduce()) {
      receipt.classList.add("is-sealed");
      return;
    }
    requestAnimationFrame(() => receipt.classList.add("is-sealing"));
    window.setTimeout(() => receipt.classList.add("is-sealed"), 360);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initResolve();
    initConstellation();
    initStarReceipt();
  });
})();
