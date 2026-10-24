# Edit an existing Word document with python-docx

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-docx)
```
First `docx_text.py FILE` so you know the structure. Then work on a copy:

```python
from docx import Document
doc = Document("ATTACHED.docx")

# Replace text and keep the formatting: change runs, not paragraph.text (that resets the formatting).
def replace_in_paragraph(paragraph, old, new):
    if old not in paragraph.text:
        return
    for run in paragraph.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return
    # The text is split over several runs: put it all in the first run, empty the others.
    full = paragraph.text.replace(old, new)
    for i, run in enumerate(paragraph.runs):
        run.text = full if i == 0 else ""

def all_paragraphs(doc):
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
    for section in doc.sections:
        yield from section.header.paragraphs
        yield from section.footer.paragraphs

for paragraph in all_paragraphs(doc):
    replace_in_paragraph(paragraph, "2023", "2024")

doc.tables[0].cell(1, 1).text = "120"                           # table cell
new = doc.add_paragraph("Added at the end", style="Normal")     # append
anchor = doc.paragraphs[3]
inserted = anchor.insert_paragraph_before("Before paragraph 4")  # insert
anchor._element.getparent().remove(anchor._element)             # delete a paragraph
doc.save("scratch-path/ATTACHED-edited.docx")                   # a new name, never the original
```

## Know the limits
- python-docx cannot do tracked changes or comments (it keeps existing ones). If the user wants suggestions,
  write them as a list or a new "Suggested edits" section, and say so.
- It keeps what it does not understand (text boxes, fields, SmartArt) but cannot edit it; text inside text
  boxes is not in `doc.paragraphs`.
- Images inside paragraphs stay; to add one use `run.add_picture(path, width=Inches(4))`.
- Check the result: `docx_text.py` the new file and compare with the original; never claim a change you did
  not see in the output.
