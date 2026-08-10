"""Turn raw uploaded bytes into a header row plus data rows.

Neither source ships a file that is valid CSV from byte zero: ING puts a
metadata preamble above the header, PayPal ships a BOM. This module is the only
place that touches raw bytes — everything downstream works on `str`.
"""

from __future__ import annotations

from dataclasses import dataclass

from parsers.detect import match_signature

# How far down the file to look for a header before giving up.
MAX_HEADER_SCAN_LINES = 40

UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class PrecleanResult:
    """A file split into its header, its rows, and the preamble that was cut."""

    header_line: str
    data_lines: list[str]
    delimiter: str
    encoding: str
    preamble_lines: list[str]
    header_line_number: int


class NoHeaderFound(Exception):
    """Raised when no line in the scanned window looks like a known header.

    Carries the scanned lines so the import endpoint can echo them back and make
    a wrong file obvious.
    """

    def __init__(self, scanned_lines: list[str], lines_scanned: int) -> None:
        self.scanned_lines = scanned_lines
        self.lines_scanned = lines_scanned
        super().__init__(
            f"No known CSV header found in the first {lines_scanned} lines of the file"
        )


def decode(raw: bytes) -> tuple[str, str]:
    """Decode uploaded bytes, returning the text and the encoding used.

    UTF-8 first: it raises on invalid bytes, so the Latin-1 fallback actually
    fires for ING's exports. The reverse order would never reach UTF-8, because
    Latin-1 decodes any byte sequence without complaint.
    """
    if raw.startswith(UTF8_BOM):
        raw = raw[len(UTF8_BOM) :]
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def preclean(raw: bytes) -> PrecleanResult:
    """Strip the BOM and preamble, and split the file into header and rows.

    Raises `NoHeaderFound` if no line within the first `MAX_HEADER_SCAN_LINES`
    carries every column name of a known source.
    """
    text, encoding = decode(raw)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for index, line in enumerate(lines[:MAX_HEADER_SCAN_LINES]):
        signature = match_signature(line)
        if signature is None:
            continue
        return PrecleanResult(
            header_line=line,
            data_lines=[row for row in lines[index + 1 :] if row.strip()],
            delimiter=signature.delimiter,
            encoding=encoding,
            preamble_lines=lines[:index],
            header_line_number=index + 1,
        )

    scanned = lines[:MAX_HEADER_SCAN_LINES]
    raise NoHeaderFound(scanned_lines=scanned, lines_scanned=len(scanned))
