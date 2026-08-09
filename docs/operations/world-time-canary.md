# World-time public canary
Run `python scripts/canary_world_time.py --origin https://orrery.lol` to call the public direct MCP endpoint and public key document, then verify the signed receipt and recent UTC evidence. The scheduled/manual workflow is deliberately `continue-on-error`: it reports external availability or upstream clock failures without gating pull requests or releases.
