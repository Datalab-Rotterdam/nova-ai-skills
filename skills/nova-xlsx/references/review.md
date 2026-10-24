# Notes, comments, metadata and diff (Excel)

`<skill root>` is this skill's folder. Reading needs only Python 3. Changing needs the environment:
`PY=$(python3 "<skill root>/scripts/ensure_env.py" openpyxl lxml)`. Never write over the attached file.

## Read
```
python3 "<skill root>/scripts/xlsx_comments.py" FILE [--sheet NAME]
python3 "<skill root>/scripts/office_meta.py" FILE
python3 "<skill root>/scripts/xlsx_diff.py" OLD.xlsx NEW.xlsx [--formulas] [--sheet NAME]
```
- `xlsx_comments.py`: per sheet and cell, classic notes (author, text) and threaded comments (id, author, date,
  open/resolved, replies).
- `office_meta.py`: title, author, last modified by, dates, application, custom properties, hidden sheets, named
  ranges, external links, macros, embedded objects.
- `xlsx_diff.py`: sheets added/removed and every cell that was added, removed or changed (`B2: '100' -> '150'`).
  With `--formulas` it compares formulas as well as values.

## Notes (classic comments) with openpyxl
```python
from openpyxl import load_workbook
from openpyxl.comments import Comment
wb = load_workbook("ATTACHED.xlsx")
ws = wb["Sales"]
ws["B2"].comment = Comment("Check this figure with finance", "Nova AI")      # add or replace
ws["B2"].comment.width, ws["B2"].comment.height = 300, 100                   # box size in points
ws["C3"].comment = None                                                        # delete
wb.save("scratch-path/ATTACHED-commented.xlsx")
```
**openpyxl loses threaded comments**: on save they are reduced to a plain note saying "[Threaded comment]". If
`xlsx_comments.py` shows `[thread ...]` entries, do not edit that file with openpyxl; tell the user.

## Resolve or reopen threaded comments (no other change to the file)
```
"$PY" "<skill root>/scripts/xlsx_threads_edit.py" FILE -o NEW.xlsx resolve THREAD_ID    # id from xlsx_comments.py
"$PY" "<skill root>/scripts/xlsx_threads_edit.py" FILE -o NEW.xlsx resolve --all
"$PY" "<skill root>/scripts/xlsx_threads_edit.py" FILE -o NEW.xlsx reopen THREAD_ID
```
Replying to or adding a threaded comment is not supported (Excel needs matching person and legacy parts). To
answer, tell the user, or add a classic note next to the cell. Resolve only threads the user asked you to.

## Metadata and hidden things
```python
wb.properties.title = "Sales 2025"; wb.properties.creator = "Finance"; wb.properties.lastModifiedBy = "Finance"
wb.properties.keywords = "sales,2025"; wb.properties.description = ""
ws.sheet_state = "visible"          # "hidden" / "veryHidden" to hide a sheet
print(list(wb.defined_names))       # named ranges
```
Before sharing a workbook, `office_meta.py` shows what it still holds (hidden sheets, notes with authors, named
ranges, external links): report these instead of silently removing them.
