import re
from dagster import asset


@asset(description="Split source document into H2-delimited chunks. Returns empty list if content is unchanged.")
def chunks(source_document: dict, hash_check: dict) -> list[dict]:
    if not hash_check["changed"]:
        return []

    content = source_document["content"]
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    result = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        if section.startswith("## "):
            first_newline = section.find("\n")
            if first_newline == -1:
                continue  # heading only, no body — skip empty section
            heading = section[3:first_newline].strip()
            body = section[first_newline:].strip()
            if not body:
                continue  # empty section — skip per BR-02
            result.append({
                "chunk_index": len(result),
                "chunk_title": heading,
                "content": section,
            })
        else:
            # preamble — content before the first ## heading
            if section:
                result.append({
                    "chunk_index": len(result),
                    "chunk_title": None,
                    "content": section,
                })

    return result
