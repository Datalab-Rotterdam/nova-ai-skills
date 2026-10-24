---
name: nova-pdf
description: Read, create and edit PDFs: text, merge, split, forms, comments and annotations, metadata, diffs, new PDFs. Use for any PDF the user attached or asks for.
license: Apache-2.0, Copyright 2026 DataLab Rotterdam (LICENSE.txt)
---

# PDF files

An attached file reaches you as a path (`<attachment type="file" path="…" absolutePath="…">`).
Never guess its content; open it. `Skill root` in the `load_skill` result is this folder. Use `python3`
(or `python` / `py -3` where that is the name).

## Read
```
python3 "<skill root>/scripts/pdf_text.py" FILE [--pages 1-5]
```
Uses poppler's `pdftotext` or the Python package pypdf when present; without either it falls back to a rough
reader that can miss text. For exact text install pypdf into Nova's own environment (tell the user; it needs
the internet once) and run the script with that python:
```
PY=$(python3 "<skill root>/scripts/ensure_env.py" pypdf)
"$PY" "<skill root>/scripts/pdf_text.py" FILE
```
A scan has no text: say so, and OCR it if `ocrmypdf` or `tesseract` is installed.

## Review: comments, metadata, diff (needs pypdf)
```
python3 "<skill root>/scripts/pdf_review.py" FILE            # properties, comments with replies and state, form fields, bookmarks
python3 "<skill root>/scripts/pdf_diff.py" OLD NEW           # text that differs between two versions, page by page
```
To add, answer, resolve or delete comments, or edit metadata and bookmarks, read `references/review.md`.

## Create or edit (needs pypdf, reportlab)
Read `references/create.md` to make a new PDF, `references/edit.md` to merge, split, rotate, fill forms or
stamp an attached one (use `load_skill` with `resource`).

## Rules
- Never overwrite the attached original. Save results as a new file in the scratch folder (or where the user asks)
  and say where it is.
- PDF is not an editing format: changing the words inside an existing PDF is not reliably possible. Offer to
  rebuild the content as a new PDF or as a Word file, or to add text on top (see `references/edit.md`).
- After writing, read the result back with `pdf_text.py` to check it, and say what you changed.
