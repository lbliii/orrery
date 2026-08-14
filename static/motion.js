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

  function tokenMs(name, fallback) {
    const raw = getComputedStyle(root).getPropertyValue(name).trim();
    const ms = parseFloat(raw);
    return Number.isFinite(ms) ? ms : fallback;
  }

  function settleMs() {
    return tokenMs("--settle", 280);
  }

  function flashMs() {
    return tokenMs("--flash", 180);
  }

  /** Resolve: settle the server-matched digest after a real GET. */
  function initMatchedDigest() {
    const digest = document.querySelector("[data-resolve-matched] [data-digest]");
    if (digest?.dataset.final) settleDigest(digest, digest.dataset.final, settleMs());
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
    window.setTimeout(() => {
      receipt.classList.add("is-sealed");
      if (typeof navigator.vibrate === "function") {
        navigator.vibrate(12);
      }
    }, 360);
  }

  /** Copy MCP URL from star manifest (issue #25). Copied beat uses --flash. */
  function initCopyMcp() {
    document.querySelectorAll("[data-copy-mcp]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const url = btn.getAttribute("data-mcp-url");
        if (!url) return;
        try {
          await navigator.clipboard.writeText(url);
          const prev = btn.textContent;
          btn.textContent = "Copied";
          btn.classList.add("is-copied");
          if (!prefersReduce() && typeof navigator.vibrate === "function") {
            navigator.vibrate(12);
          }
          window.setTimeout(() => {
            btn.textContent = prev;
            btn.classList.remove("is-copied");
          }, flashMs());
        } catch {
          btn.textContent = "Copy failed";
        }
      });
    });
  }

  /** Arrive: new feed rows get a one-shot class; do not re-animate the list. */
  function initFeedArrive() {
    const activity = document.querySelector(".activity");
    if (!activity) return;

    const oneShot = (el) => {
      if (!(el instanceof Element) || !el.classList.contains("activity-item")) {
        return;
      }
      if (prefersReduce()) {
        el.classList.remove("is-arriving");
        return;
      }
      el.classList.add("is-arriving");
      el.addEventListener(
        "animationend",
        () => el.classList.remove("is-arriving"),
        { once: true },
      );
    };

    activity.querySelectorAll(".activity-item").forEach((el) => {
      el.classList.remove("is-arriving");
    });

    const mo = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const n of m.addedNodes) {
          if (n.nodeType !== 1) continue;
          if (n.classList?.contains("activity-item")) oneShot(n);
          n.querySelectorAll?.(".activity-item").forEach(oneShot);
        }
      }
    });
    mo.observe(activity, { childList: true, subtree: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initMatchedDigest();
    initConstellation();
    initStarReceipt();
    initCopyMcp();
    initFeedArrive();
  });
})();
