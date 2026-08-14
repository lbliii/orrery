# Kida component demo — badge check → render tour

Frozen publisher-direct demo for Kida stars ([#404](https://github.com/lbliii/orrery/issues/404)).
Follows the [#393](https://github.com/lbliii/orrery/issues/393) pattern: **static doc +
fixture**, not a new MCP tool. ADR 0005: agent ranks; Orrery documents frozen args.

## Prerequisite

Point a streamable-HTTP MCP client at ``/mcp`` for gaze/resolve only. Call
``check`` and ``render`` on the **publisher** endpoints returned by
``resolve_name`` (ADR 0004) — not aggregate ``/mcp`` execution until
[#390](https://github.com/lbliii/orrery/issues/390) ``call_skill``.

## Narrative

1. **Badge typo** — caller supplies a Kida template with a component call-site
   mistake (`lable` typo, string literal for an ``int`` param).
2. **Check** — ``orrery/kida-check`` ``check`` returns ``K-CMP-001`` /
   ``K-CMP-002`` in ``finding_codes`` with ``passed: false``.
3. **Fix + render** — corrected template + JSON data → ``orrery/kida-render``
   ``render`` → HTML containing ``<span class="badge">5 Messages</span>`` plus
   ``template_digest``, ``data_digest``, ``output_digest``.

Corpus args match ``stars/kida_check/corpus.py`` and
``stars/kida_render/corpus.py`` on main.

## Frozen steps

| Step | Title | Name | Tool | Expected |
|------|-------|------|------|----------|
| 1 | Badge check | ``orrery/kida-check`` | ``check`` | ``K-CMP-001``, ``K-CMP-002`` |
| 2 | Badge render | ``orrery/kida-render`` | ``render`` | html + digests |

Publisher MCP paths:

- Check: ``POST /stars/kida-check/mcp`` — tool ``check``
- Render: ``POST /stars/kida-render/mcp`` — tool ``render``

Machine-readable copy: ``discovery.KIDA_DEMO`` and
[``tests/gaze-kida-demo.v1.json``](../../tests/gaze-kida-demo.v1.json).
Human copy: ``/connect#kida-demo`` and ``/llms.txt`` (Kida component demo).

## Verify

```bash
uv run pytest tests/test_discovery.py -q -k kida
uv run ruff check .
```

See also [kida-check ops](kida-check.md) and [kida-render ops](kida-render.md).
