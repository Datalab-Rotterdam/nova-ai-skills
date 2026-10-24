# Create a presentation with python-pptx

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-pptx)
"$PY" make.py        # your script, written to the scratch folder
```

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

prs = Presentation()                       # default template, 4:3. For 16:9:
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
# default layouts: 0 title, 1 title+content, 2 section header, 5 title only, 6 blank

s = prs.slides.add_slide(prs.slide_layouts[0])
s.shapes.title.text = "Quarterly report"
s.placeholders[1].text = "Q3 2025"

s = prs.slides.add_slide(prs.slide_layouts[1])
s.shapes.title.text = "Highlights"
body = s.placeholders[1].text_frame
body.text = "Revenue grew 12%"
para = body.add_paragraph(); para.text = "EU led the growth"; para.level = 1
s.notes_slide.notes_text_frame.text = "Speaker notes go here."

s = prs.slides.add_slide(prs.slide_layouts[5])          # title only: room for a chart / table / picture
s.shapes.title.text = "Sales by region"
data = CategoryChartData(); data.categories = ["EU", "US"]; data.add_series("Q3", (140, 79))
s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.8), Inches(8), Inches(4.5), data)
table = s.shapes.add_table(3, 2, Inches(1), Inches(6.4), Inches(4), Inches(0.9)).table
table.cell(0, 0).text = "Region"
s.shapes.add_picture("scratch-path/logo.png", Inches(8.5), Inches(0.3), height=Inches(0.8))

prs.save("scratch-path/deck.pptx")
```

## Notes
- Keep slides short: a title and at most about six lines. Details belong in the speaker notes.
- Text that is too long does not shrink by itself: set `Pt(...)` sizes on runs, or split the slide.
- A layout without the placeholder you index raises an error: print `[p.placeholder_format.type for p in
  layout.placeholders]` to see what a layout has.
- Check the result with `pptx_text.py`, and for the looks convert to PDF (`soffice`, if installed).
