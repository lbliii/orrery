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

  /** Landing orb: sightline in user space; rest pose when motion is reduced. */
  function initOrb() {
    const stage = document.querySelector(".orb-stage");
    const svg = stage?.querySelector(".orb-svg");
    const sight = svg?.querySelector(".orb-sight");
    if (!stage || !svg || !sight) return;

    const sun = { x: 200, y: 200 };
    const limb = 15;
    const past = 12;
    const tau = settleMs() / 3000;
    let motionOn = !prefersReduce();
    let current = null;
    let last = performance.now();

    function pointed() {
      return svg.querySelector(
        motionOn ? ".orb-body-pointed.orb-body-motion" : ".orb-body-pointed.orb-body-rest",
      );
    }

    function userPoint(el) {
      const p = svg.createSVGPoint();
      p.x = Number(el.getAttribute("cx") || 0);
      p.y = Number(el.getAttribute("cy") || 0);
      const screen = p.matrixTransform(el.getScreenCTM());
      return screen.matrixTransform(svg.getScreenCTM().inverse());
    }

    function localPoint(el) {
      const group = el.parentNode;
      const p = svg.createSVGPoint();
      p.x = Number(el.getAttribute("cx") || 0);
      p.y = Number(el.getAttribute("cy") || 0);
      const screen = p.matrixTransform(el.getScreenCTM());
      return screen.matrixTransform(group.getScreenCTM().inverse());
    }

    function sightTarget(el) {
      const body = userPoint(el);
      const dx = body.x - sun.x;
      const dy = body.y - sun.y;
      const len = Math.hypot(dx, dy) || 1;
      const nx = dx / len;
      const ny = dy / len;
      return {
        x1: sun.x + nx * limb,
        y1: sun.y + ny * limb,
        x2: body.x + nx * past,
        y2: body.y + ny * past,
      };
    }

    function applySight(s) {
      sight.setAttribute("x1", s.x1.toFixed(2));
      sight.setAttribute("y1", s.y1.toFixed(2));
      sight.setAttribute("x2", s.x2.toFixed(2));
      sight.setAttribute("y2", s.y2.toFixed(2));
    }

    function dimSky() {
      svg.querySelectorAll(".orb-body-sky").forEach((el) => {
        if (el.classList.contains("orb-body-motion") !== motionOn) return;
        if (!el.dataset.r) el.dataset.r = el.getAttribute("r");
        const far = localPoint(el).y < 200;
        const base = Number(el.dataset.r);
        el.setAttribute("opacity", far ? "0.7" : "1");
        el.setAttribute("r", String(far ? base * 0.85 : base));
      });
    }

    function setMotion(on) {
      motionOn = on;
      stage.classList.toggle("is-motion", on);
      stage.classList.toggle("is-rest", !on);
      if (on) svg.unpauseAnimations();
      else svg.pauseAnimations();
      current = null;
    }

    function tick(now) {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const el = pointed();
      if (!el) return;
      const target = sightTarget(el);
      if (!current || !motionOn) {
        current = target;
      } else {
        const a = 1 - Math.exp(-dt / tau);
        current = {
          x1: current.x1 + (target.x1 - current.x1) * a,
          y1: current.y1 + (target.y1 - current.y1) * a,
          x2: current.x2 + (target.x2 - current.x2) * a,
          y2: current.y2 + (target.y2 - current.y2) * a,
        };
      }
      applySight(current);
      dimSky();
      requestAnimationFrame(tick);
    }

    setMotion(motionOn);
    requestAnimationFrame((t) => {
      last = t;
      tick(t);
    });
    reduce.addEventListener("change", () => setMotion(!reduce.matches));
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
    initOrb();
    initFeedArrive();
  });
})();
