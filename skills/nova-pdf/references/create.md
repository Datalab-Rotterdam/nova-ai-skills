# Create a PDF with reportlab

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" reportlab)
"$PY" make.py        # your script, written to the scratch folder
```

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("scratch-path/report.pdf", pagesize=A4, title="Quarterly report",
                        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
story = [
    Paragraph("Quarterly report", styles["Title"]),
    Paragraph("Revenue grew <b>12%</b> in Q3.", styles["BodyText"]),   # simple HTML-like tags: b, i, u, br, font
    Spacer(1, 0.5*cm),
]
table = Table([["Region", "Sales"], ["EU", "100"], ["US", "80"]], hAlign="LEFT")
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305496")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
]))
story += [table, PageBreak(), Image("scratch-path/chart.png", width=14*cm, height=8*cm)]
doc.build(story)
```

## Notes
- Escape `&`, `<` and `>` in text that goes into `Paragraph` (`&amp;`, `&lt;`, `&gt;`).
- The built-in fonts have no accents beyond Latin-1 and no CJK/emoji: register a TTF
  (`pdfmetrics.registerFont(TTFont("Name", "file.ttf"))`) for other scripts.
- Charts: draw a PNG with matplotlib (install it with ensure_env.py) and add it as an `Image`.
- To get a PDF from a Word/PowerPoint/Excel file, convert instead of rebuilding: `soffice --headless
  --convert-to pdf FILE` (LibreOffice), on macOS also `cupsfilter` for plain text.
