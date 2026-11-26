---
id: doc:ref-formats
title: "Reference: formats CSV/JSON/Markdown"
doc_type: reference
lang: en
source: references/formats-csv-json-markdown.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, markdown, formats]
---

# Formats CSV/JSON/Markdown

- Markdown: CommonMark via markdown-it-py tokens (never regex). Headings from tokens; outline with title/level/line/anchor/parent. YAML front matter is a separate YAML-lite layer.
- CSV: explicit dialect (comma/semicolon/tab), `newline=''`, header/width/duplicate checks. Cells are strings by default.
- JSON: strict UTF-8, duplicate-key rejection, size/depth limits, JSON Pointer locations.
- Forced learning (MUST): before processing a format, read this reference. Without reading, processing is forbidden.