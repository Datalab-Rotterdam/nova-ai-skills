# Create a workbook with openpyxl

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" openpyxl)
"$PY" make.py        # your script, written to the scratch folder
```

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

wb = Workbook()
ws = wb.active
ws.title = "Sales"
ws.append(["Region", "Q1", "Q2", "Total"])
for region, q1, q2 in [("EU", 100, 120), ("US", 80, 80)]:
    row = ws.max_row + 1
    ws.append([region, q1, q2, f"=SUM(B{row}:C{row})"])        # formulas are strings starting with =

for cell in ws[1]:                                              # header style
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="305496")
    cell.alignment = Alignment(horizontal="center")
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
for col in range(1, ws.max_column + 1):                         # column widths
    ws.column_dimensions[get_column_letter(col)].width = 14
for row in ws.iter_rows(min_row=2, min_col=2, max_col=4):
    for cell in row:
        cell.number_format = "#,##0"                            # "0.0%", "yyyy-mm-dd", '€#,##0.00'

wb.save("scratch-path/sales.xlsx")
```

## Charts
```python
from openpyxl.chart import BarChart, Reference
chart = BarChart(); chart.title = "Sales per region"
chart.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=ws.max_row), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
ws.add_chart(chart, "F2")
```

## Notes
- openpyxl writes formulas but does not calculate them: the cached value stays empty until Excel (or
  LibreOffice) opens the file, and `xlsx_dump.py` then shows nothing for those cells. For values you must report,
  compute them in Python and say so; or recalculate with `soffice --headless --convert-to xlsx --outdir OUT FILE`.
- Put data in real cells, one header row, one record per row; no merged cells inside data.
- Other sheets: `wb.create_sheet("Name")`. Dates: write `datetime.date` objects. Large data: `Workbook(write_only=True)`.
- A CSV is not a workbook: use the `csv` module for CSV; this skill is for `.xlsx`.
