# Edit a PDF with pypdf (and reportlab)

```
PY=$(python3 "<skill root>/scripts/ensure_env.py" pypdf reportlab)
```
Work on copies; save to a new file. Page numbers below are 0-based in code.

```python
from pypdf import PdfReader, PdfWriter

# Merge
writer = PdfWriter()
for path in ["a.pdf", "b.pdf"]:
    writer.append(path)                                  # whole file; or writer.append(path, pages=(0, 3))
writer.write("scratch-path/merged.pdf")

# Split / extract pages / delete pages / reorder
reader = PdfReader("ATTACHED.pdf")
out = PdfWriter()
for index in [2, 0, 1]:                                  # the pages you keep, in the order you want
    out.add_page(reader.pages[index])
out.add_metadata({"/Title": "New title"})
out.write("scratch-path/reordered.pdf")

# Rotate
page = reader.pages[0]; page.rotate(90)                  # clockwise, multiples of 90
```

## Fill a form (AcroForm)
```python
reader = PdfReader("form.pdf")
print({name: field.get("/V") for name, field in (reader.get_fields() or {}).items()})   # field names first
writer = PdfWriter(clone_from=reader)
writer.update_page_form_field_values(writer.pages[0], {"Name": "Ada Lovelace", "Date": "2025-01-31"}, auto_regenerate=False)
writer.set_need_appearances_writer(True)                 # viewers draw the values
writer.write("scratch-path/form-filled.pdf")
```
A PDF without form fields cannot be filled; stamp text on it instead (below).

## Stamp text, a watermark or page numbers on top of pages
```python
import io
from reportlab.pdfgen import canvas
reader = PdfReader("ATTACHED.pdf"); writer = PdfWriter()
for number, page in enumerate(reader.pages, 1):
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    buffer = io.BytesIO()
    overlay = canvas.Canvas(buffer, pagesize=(width, height))
    overlay.setFont("Helvetica", 9); overlay.drawRightString(width - 36, 24, f"Page {number}")
    overlay.save(); buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])
    writer.add_page(page)
writer.write("scratch-path/numbered.pdf")
```

## Know the limits
- The words inside an existing PDF cannot be edited reliably. Stamping covers text but does not remove it
  (not a redaction: black boxes over text leave the text in the file). For real changes, rebuild the document
  (`references/create.md`) or ask for the Word original.
- Password protected: `reader.decrypt("password")` with a password from the user; never try to guess one.
- Encrypt your output only when asked: `writer.encrypt("user-password")`.
- Check the result: `pdf_text.py` the new file and compare with the original.
