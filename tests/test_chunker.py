from memex_backend.chunker import chunk_document


def test_markdown_sections_keep_headings():
    chunks = chunk_document("notes.md", "# One\nalpha\n## Child\nbeta\n# Two\ngamma", 20, 2)
    assert [(chunk.heading, chunk.text) for chunk in chunks] == [
        ("One", "alpha"),
        ("One > Child", "beta"),
        ("Two", "gamma"),
    ]


def test_long_section_splits_with_overlap():
    chunks = chunk_document("notes.md", "# Topic\none two three four five six seven", 4, 1)
    assert [chunk.text for chunk in chunks] == ["one two three four", "four five six seven"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert all(chunk.heading == "Topic" for chunk in chunks)


def test_text_paragraphs_and_empty_input():
    chunks = chunk_document("notes.txt", "first paragraph\n\nsecond paragraph", 10, 1)
    assert [chunk.text for chunk in chunks] == ["first paragraph", "second paragraph"]
    assert all(chunk.heading is None for chunk in chunks)
    assert chunk_document("notes.md", " \n", 10, 1) == []
