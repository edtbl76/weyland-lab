import re
from dagster import asset

# Fixed-size character chunking parameters for code files.
_CODE_CHUNK_SIZE = 1500
_CODE_CHUNK_OVERLAP = 200


def _markdown_chunks(content: str) -> list[dict]:
    """Split markdown into H2-delimited sections (preamble kept as a leading chunk)."""
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    out: list[dict] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        if section.startswith("## "):
            first_newline = section.find("\n")
            if first_newline == -1:
                continue  # heading only, no body
            heading = section[3:first_newline].strip()
            body = section[first_newline:].strip()
            if not body:
                continue  # empty section
            out.append({
                "chunk_index": len(out),
                "chunk_title": heading,
                "content": section,
            })
        else:
            out.append({
                "chunk_index": len(out),
                "chunk_title": None,
                "content": section,
            })
    return out


def _code_chunks(content: str) -> list[dict]:
    """Fixed-size character chunks with overlap; chunk_title is always None."""
    out: list[dict] = []
    step = _CODE_CHUNK_SIZE - _CODE_CHUNK_OVERLAP  # 1300
    start = 0
    length = len(content)
    while start < length:
        piece = content[start:start + _CODE_CHUNK_SIZE]
        if piece.strip():
            out.append({
                "chunk_index": len(out),
                "chunk_title": None,
                "content": piece,
            })
        start += step
    return out


@asset(description="Chunk each CHANGED file: markdown by H2, code by fixed-size overlap. Each chunk carries source_path.")
def chunks(source_document: list[dict], hash_check: dict) -> list[dict]:
    result: list[dict] = []
    for doc in source_document:
        source_path = doc["source_path"]
        check = hash_check.get(source_path)
        if not check or not check["changed"]:
            continue  # unchanged (or absent) — skip

        if doc["kind"] == "markdown":
            doc_chunks = _markdown_chunks(doc["content"])
        else:
            doc_chunks = _code_chunks(doc["content"])

        for chunk in doc_chunks:
            chunk["source_path"] = source_path
            chunk["source_name"] = doc["source_name"]
            chunk["kind"] = doc["kind"]
            result.append(chunk)

    return result
