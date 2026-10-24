# Edit an existing workbook with openpyxl

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" openpyxl)
```
First look with `xlsx_dump.py FILE --formulas` so you know the sheets, headers and formulas.

```python
from openpyxl import load_workbook
wb = load_workbook("ATTACHED.xlsx")            # keeps formulas, styles, widths, validations
# .xlsm: load_workbook(path, keep_vba=True) and save as .xlsm
ws = wb["Sheet1"]
ws["B2"] = 150                                  # change a value
ws.cell(row=5, column=3, value="=B5*2")         # or a formula
ws.append(["new", 1, 2])                        # add a row at the end
ws.insert_rows(3); ws.delete_rows(7)            # formulas that point at moved cells are NOT rewritten
for row in ws.iter_rows(min_row=2):             # bulk change
    if row[0].value == "old":
        row[0].value = "new"
wb.save("scratch-path/ATTACHED-edited.xlsx")    # a new name, never the original
```

## Know the limits
- Never `load_workbook(..., data_only=True)` and then save: that replaces every formula with its last value.
- openpyxl drops what it cannot read: existing charts, pivot tables, slicers, form controls and (without
  Pillow) images are lost on save. If the workbook has them, tell the user and ask before editing, or do the
  change on a copy and say what may be missing.
- Inserting or deleting rows/columns does not update formulas or named ranges; change cells in place or
  rewrite the affected formulas yourself.
- Formulas you add have no cached value until the file is opened in Excel/LibreOffice.
- Check the result: `xlsx_dump.py` the new file and compare with the original.
