# Comments, metadata, bookmarks and diff (PDF)

`<skill root>` is this skill's folder. These scripts need pypdf. Install it into Nova's environment
(ask the user first) with `PY=$(python3 "<skill root>/scripts/ensure_env.py" pypdf)`; when pypdf is only there,
the scripts re-run themselves with that python, so `python3 script.py` works afterwards.
Never write over the attached file: every change command takes `-o NEW.pdf`.

## Read
```
python3 "<skill root>/scripts/pdf_review.py" FILE [--all]
python3 "<skill root>/scripts/pdf_diff.py" OLD.pdf NEW.pdf
```
- `pdf_review.py`: document properties (title, author, producer, dates), annotations with ids (`P2.1` = page 2,
  first annotation): type, author, date, text, replies, review state (`Completed`, `Accepted`, …); form fields and
  their values; bookmarks with pages; attachments. `--all` adds links and form widgets.
- `pdf_diff.py`: page-by-page text diff, changes word by word. Page breaks shift when text is added, so a
  paragraph that moved to the next page shows as removed and added.

## Add, answer, resolve, delete comments
```
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf note --page 2 "Check this figure" --author "Nova AI"
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf reply P2.1 "Fixed in v2"
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf resolve P2.1 P3.2      # review state "Completed"
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf reopen P2.1
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf delete P2.1             # and its replies
"$PY" "<skill root>/scripts/pdf_annots_edit.py" FILE -o NEW.pdf delete --author "Ada"
```
Run `pdf_review.py` on the new file and report the change. Resolve or delete only what the user asked for.
A highlight with a comment (pypdf):
```python
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject
writer = PdfWriter(clone_from=PdfReader("ATTACHED.pdf"))
x1, y1, x2, y2 = 72, 690, 300, 705                      # the text's box in points, origin bottom left
writer.add_annotation(page_number=0, annotation=Highlight(
    rect=(x1, y1, x2, y2), quad_points=ArrayObject([FloatObject(v) for v in (x1, y2, x2, y2, x1, y1, x2, y1)]),
    highlight_color="ffff00"))
writer.write("scratch-path/highlighted.pdf")
```

## Metadata, bookmarks
```python
reader = PdfReader("ATTACHED.pdf"); writer = PdfWriter(clone_from=reader)
writer.add_metadata({"/Title": "Contract v2", "/Author": "Legal team", "/Subject": "", "/Keywords": "contract"})
writer.add_outline_item("Chapter 1", page_number=0)                       # bookmark (0-based page)
writer.write("scratch-path/ATTACHED-meta.pdf")
```
`add_metadata` changes the document information dictionary only. A PDF may also carry XMP metadata and the
producing program's own fields; `pdf_review.py` shows both, and an empty value above does not erase XMP. For a
thorough clean-up use `exiftool -all= FILE` or `qpdf --linearize` if installed, and say that you did.
