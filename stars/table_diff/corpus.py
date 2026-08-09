from chirp.skill.smoke import CorpusPrompt

CORPUS = (
    CorpusPrompt(
        id="table-diff-price-change",
        prompt="Compare these two product table snapshots by id.",
        tool="diff",
        arguments={
            "left": {"rows": [{"id": "a", "price": 10}]},
            "right": {"rows": [{"id": "a", "price": 12}]},
            "key_column": "id",
        },
        required_facts=("snapshot_digest", "changed_count", "changed_columns"),
    ),
)
