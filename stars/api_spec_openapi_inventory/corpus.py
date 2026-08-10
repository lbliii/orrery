from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="api-spec-openapi-inventory-baseline",
        prompt="Inventory a small OpenAPI 3.0.3 document with schemas and a discriminator.",
        tool="inventory",
        arguments={
            "entries": [
                {
                    "path": "openapi.json",
                    "content": (
                        '{"openapi":"3.0.3","info":{"title":"Demo","version":"1.0.0"},'
                        '"paths":{},"components":{"schemas":{"Pet":{"type":"object",'
                        '"properties":{"name":{"type":"string"}}}}}}'
                    ),
                }
            ]
        },
        required_facts=("inventory_digest", "source_manifest_digest", "findings", "source"),
    ),
)
