# Edit an existing presentation with python-pptx

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-pptx)
```
First `pptx_text.py FILE` so you know the slides. Then work on a copy:

```python
from pptx import Presentation
prs = Presentation("ATTACHED.pptx")

# Replace text and keep the formatting: change runs, not text_frame.text (that resets the formatting).
def replace_text(prs, old, new):
    for slide in prs.slides:
        for shape in slide.shapes:
            frames = []
            if shape.has_text_frame:
                frames.append(shape.text_frame)
            if shape.has_table:
                frames += [cell.text_frame for row in shape.table.rows for cell in row.cells]
            for frame in frames:
                for paragraph in frame.paragraphs:
                    for run in paragraph.runs:
                        run.text = run.text.replace(old, new)     # text split over runs is not found: check the output
replace_text(prs, "2024", "2025")

slide = prs.slides[2]
slide.shapes.title.text = "New title"
slide.notes_slide.notes_text_frame.text = "New notes"

# Add a slide with a layout of THIS deck (look at prs.slide_layouts names first)
layout = next(l for l in prs.slide_layouts if l.name == "Title and Content")
new = prs.slides.add_slide(layout)

# Delete slide 4 / move slide 3 to the front (python-pptx has no API; edit the slide id list)
ids = prs.slides._sldIdLst
slides = list(ids)
ids.remove(slides[3])
ids.remove(slides[2]); ids.insert(0, slides[2])

prs.save("scratch-path/ATTACHED-edited.pptx")     # a new name, never the original
```

## Know the limits
- python-pptx keeps what it does not understand (animations, SmartArt, embedded media) but cannot edit it.
  A deleted slide's part stays in the file, which is harmless.
- Charts: `shape.has_chart` then `shape.chart.replace_data(chart_data)` to change their data.
- Images: replacing one means adding a new picture at the old position and size, then removing the old shape
  (`shape._element.getparent().remove(shape._element)`).
- Check the result: `pptx_text.py` the new file and compare with the original; never claim a change you did
  not see in the output.
