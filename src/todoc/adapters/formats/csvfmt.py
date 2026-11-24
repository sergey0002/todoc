"""CSV adapter: explicit dialect, header/width checks, row locations."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field


@dataclass
class CsvDoc:
    headers: list[str]
    rows: list[dict[str, str]]
    errors: list[str] = field(default_factory=list)
    dialect: str = "comma"


def _detect_dialect(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
        if dialect.delimiter == ";":
            return "semicolon"
        if dialect.delimiter == "\t":
            return "tab"
    except csv.Error:
        pass
    return "comma"


_DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}


def parse_csv(text: str, max_rows: int = 1000000) -> CsvDoc:
    errors: list[str] = []
    if text.startswith("\ufeff"):
        text = text[1:]
    dialect_name = _detect_dialect(text[:4096])
    delimiter = _DELIMITERS[dialect_name]
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        raw_rows = list(reader)
    except csv.Error as exc:
        return CsvDoc(headers=[], rows=[], errors=[f"csv.parse_error: {exc}"], dialect=dialect_name)
    if not raw_rows:
        return CsvDoc(headers=[], rows=[], errors=["csv.empty"], dialect=dialect_name)
    headers = [h.strip() for h in raw_rows[0]]
    if not headers or all(h == "" for h in headers):
        errors.append("csv.missing_header")
    seen: set[str] = set()
    for h in headers:
        if h in seen:
            errors.append(f"csv.duplicate_header: {h}")
        seen.add(h)
    rows: list[dict[str, str]] = []
    for lineno, raw in enumerate(raw_rows[1:], start=2):
        if len(raw) != len(headers):
            errors.append(f"csv.wrong_width: row {lineno} has {len(raw)} fields, expected {len(headers)}")
            continue
        if len(rows) >= max_rows:
            errors.append("csv.too_many_rows")
            break
        rows.append(dict(zip(headers, raw)))
    return CsvDoc(headers=headers, rows=rows, errors=errors, dialect=dialect_name)
