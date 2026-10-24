---
name: nova-xlsx
description: Read, create and edit Excel workbooks (.xlsx, .xlsm): data, formulas, charts, notes and comments, metadata, diffs. Use for any spreadsheet the user attached.
license: Apache-2.0, Copyright 2026 DataLab Rotterdam (LICENSE.txt)
---

# Excel workbooks (.xlsx)

An attached file reaches you as a path (`<attachment type="file" path="…" absolutePath="…">`).
Never guess its content; open it. `Skill root` in the `load_skill` result is this folder. Use `python3`
(or `python` / `py -3` where that is the name).

## Read (nothing to install)
```
python3 "<skill root>/scripts/xlsx_dump.py" FILE [--sheet NAME] [--max-rows 200] [--formulas]
```
Prints every sheet as tab-separated rows (dates converted, formulas with `--formulas`). Output is capped: start
with the sheet list and the first rows, then ask for more. Do arithmetic in code, not in your head.

## Create or edit (needs openpyxl)
Read `references/create.md` to make a new workbook, `references/edit.md` to change an attached one
(use `load_skill` with `resource`). Both start with the same step, which installs the packages into Nova's own
environment without touching the system Python (tell the user what you install; it needs the internet once):
```
PY=$(python3 "<skill root>/scripts/ensure_env.py" openpyxl)
```

## Review: notes, comments, metadata, diff
```
python3 "<skill root>/scripts/xlsx_comments.py" FILE         # notes and threaded comments per cell
python3 "<skill root>/scripts/office_meta.py" FILE           # author, dates, hidden sheets, named ranges, links
python3 "<skill root>/scripts/xlsx_diff.py" OLD NEW          # cells that differ between two versions
```
To add or edit notes, resolve threaded comments or edit metadata, read `references/review.md`
(openpyxl loses threaded comments when it saves: check first).

## Rules
- Never overwrite the attached original. Save results as a new file in the scratch folder (or where the user asks)
  and say where it is.
- After writing, read the result back with `xlsx_dump.py` to check it, and say what you changed.
- `.xls` (old Excel) and OpenDocument: convert first, `soffice --headless --convert-to xlsx FILE` (LibreOffice).
