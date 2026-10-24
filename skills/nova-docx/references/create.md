# Create a Word document with python-docx

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-docx)
"$PY" make.py        # your script, written to the scratch folder
```

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()                                   # the default template has Heading 1-9, List Bullet, Table Grid, …
doc.add_heading("Quarterly report", level=0)       # level 0 = Title
doc.add_paragraph("Revenue grew 12% in Q3.")
p = doc.add_paragraph()
p.add_run("Bold ").bold = True
p.add_run("and italic").italic = True
p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
doc.add_paragraph("First point", style="List Bullet")
doc.add_paragraph("Step one", style="List Number")

table = doc.add_table(rows=1, cols=2, style="Table Grid")
table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Region", "Sales"
for region, sales in [("EU", "100"), ("US", "80")]:
    cells = table.add_row().cells
    cells[0].text, cells[1].text = region, sales

doc.add_picture("scratch-path/chart.png", width=Inches(5))
doc.add_page_break()
doc.sections[0].header.paragraphs[0].text = "Company - Confidential"
doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(11)
doc.save("scratch-path/report.docx")
```

## Notes
- Use real styles (Heading 1, List Bullet, Table Grid) instead of manual bold/size: Word's navigation pane and
  table of contents depend on them. A table of contents field needs Word to update it (F9); say so if you add one.
- Charts: draw a PNG with matplotlib (install it the same way) and `add_picture`.
- Page setup: `section = doc.sections[0]; section.orientation, section.page_width, section.page_height`.
- Result as PDF: `soffice --headless --convert-to pdf report.docx` if LibreOffice is installed.
