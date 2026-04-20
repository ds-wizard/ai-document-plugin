from ai_document_plugin_service.ai.assignment.tree_chunker import TreeChunker


def _count_nodes(nodes: list[dict]) -> int:
    total = 0
    for node in nodes:
        total += 1 + _count_nodes(node.get("children", []))
    return total


def test_chunker_keeps_single_chunk_when_budget_is_large() -> None:
    data = {
        "tag": "root",
        "title": "Root",
        "children": [
            {"tag": "question", "title": "Q1", "text": "A"},
            {"tag": "question", "title": "Q2", "text": "B"},
        ],
    }

    chunker = TreeChunker(data, max_tokens=10_000)
    chunks = chunker.chunk()

    assert len(chunks) == 1
    assert _count_nodes(chunks[0]) >= 3  # root + 2 children


def test_chunker_splits_into_multiple_chunks_when_budget_small() -> None:
    data = {
        "tag": "root",
        "title": "Root",
        "children": [
            {"tag": "question", "title": "Q1", "text": "x " * 500},
            {"tag": "question", "title": "Q2", "text": "y " * 500},
            {"tag": "question", "title": "Q3", "text": "z " * 500},
        ],
    }

    chunker = TreeChunker(data, max_tokens=50)
    chunks = chunker.chunk()

    assert len(chunks) == 3
    for i in range(3):
        assert chunks[i][0]['title'] == "Root"
        assert len(chunks[i][0]['children']) == 1
    assert chunks[0][0]["children"][0]['title'] == "Q1"
    assert chunks[1][0]["children"][0]['title'] == "Q2"
    assert chunks[2][0]["children"][0]['title'] == "Q3"


def test_chunker_does_not_duplicate_shared_ancestor_inside_chunk() -> None:
    data = {
        "tag": "root",
        "title": "Root",
        "children": [
            {
                "tag": "section",
                "title": "S1",
                "children": [
                    {"tag": "question", "title": "Q1", "text": "A"},
                    {"tag": "question", "title": "Q2", "text": "B"},
                ],
            }
        ],
    }

    chunker = TreeChunker(data, max_tokens=10_000)
    chunks = chunker.chunk()

    assert len(chunks) == 1
    root_nodes = chunks[0]
    assert len(root_nodes) == 1
    root = root_nodes[0]
    assert len(root["children"]) == 1
    assert root["children"][0]["title"] == "S1"
    assert len(root["children"][0]["children"]) == 2


def test_chunker_accepts_list_input() -> None:
    data = [
        {"tag": "question", "title": "Q1", "text": "A"},
        {"tag": "question", "title": "Q2", "text": "B"},
    ]

    chunker = TreeChunker(data, max_tokens=10_000)
    chunks = chunker.chunk()

    assert len(chunks) == 1
    assert len(chunks[0]) == 2
