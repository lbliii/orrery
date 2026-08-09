"""Small, dependency-free HTML-to-PDF service.

This renderer deliberately supports a narrow document subset: it extracts the
visible text from supplied HTML and lays it out in a simple, valid PDF. It is
not a browser renderer, but it produces an artifact that can be checked without
relying on an external conversion service.
"""

from __future__ import annotations

import base64
import hashlib
import textwrap
from html.parser import HTMLParser

_PAGE_WIDTH = 612
_PAGE_HEIGHT = 792
_LEFT_MARGIN = 54
_TOP_MARGIN = 738
_LINE_HEIGHT = 16
_MAX_LINES_PER_PAGE = 42
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "tr",
    }
)
_HIDDEN_TAGS = frozenset({"head", "script", "style", "template", "title"})


class _VisibleTextParser(HTMLParser):
    """Extract displayable text without evaluating markup or script content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.lower()
        if normalized in _HIDDEN_TAGS:
            self._hidden_depth += 1
        elif not self._hidden_depth and normalized in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _HIDDEN_TAGS and self._hidden_depth:
            self._hidden_depth -= 1
        elif not self._hidden_depth and normalized in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "\n".join(
            " ".join(line.split()) for line in "".join(self._parts).splitlines() if line.split()
        )


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return parser.text() or " "


def _pdf_literal(text: str) -> str:
    """Encode text for a PDF literal string using the built-in Helvetica font."""
    latin1 = text.encode("latin-1", "replace").decode("latin-1")
    return latin1.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrapped_lines(text: str) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        lines.extend(textwrap.wrap(paragraph, width=82, break_long_words=True) or [""])
    return lines or [""]


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", f"{_LEFT_MARGIN} {_TOP_MARGIN} Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append(f"0 -{_LINE_HEIGHT} Td")
        commands.append(f"({_pdf_literal(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def _build_pdf(text: str) -> tuple[bytes, int]:
    lines = _wrapped_lines(text)
    pages = [
        lines[index : index + _MAX_LINES_PER_PAGE]
        for index in range(0, len(lines), _MAX_LINES_PER_PAGE)
    ]
    page_count = len(pages)
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    page_object_numbers = [4 + index * 2 for index in range(page_count)]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, page_lines in enumerate(pages):
        page_number = page_object_numbers[index]
        content_number = page_number + 1
        stream = _page_stream(page_lines)
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>"
        )
        objects.append(page.encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, object_body in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{object_number} 0 obj\n".encode())
        result.extend(object_body)
        result.extend(b"\nendobj\n")
    xref_offset = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    result.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    result.extend(f"{trailer}startxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(result), page_count


def convert(html: str) -> dict[str, object]:
    """Render simple HTML to a PDF artifact and return verifiable metadata."""
    if not isinstance(html, str):
        raise TypeError("html must be a string")
    pdf, page_count = _build_pdf(_visible_text(html))
    return {
        "artifact_base64": base64.b64encode(pdf).decode("ascii"),
        "sha256": hashlib.sha256(pdf).hexdigest(),
        "byte_length": len(pdf),
        "page_count": page_count,
        "content_type": "application/pdf",
    }


def health() -> dict[str, str]:
    """Report readiness for the conversion Star."""
    return {"status": "ok", "skill": "html-to-pdf"}
