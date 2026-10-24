---
name: nova-pptx
description: Read, create and edit PowerPoint decks (.pptx): slides, charts, speaker notes, comments, metadata, diffs. Use for any presentation the user attached.
---

# PowerPoint presentations (.pptx)

An attached file reaches you as a path (`<attachment type="file" path="…" absolutePath="…">`).
Never guess its content; open it. `Skill root` in the `load_skill` result is this folder. Use `python3`
(or `python` / `py -3` where that is the name).

## Read (nothing to install)
```
python3 "<skill root>/scripts/pptx_text.py" FILE
```
Prints each slide's text (in presentation order, indented by level), tables and speaker notes.
Layout, colors and images are not shown.

## Create or edit (needs python-pptx)
Read `references/create.md` to make a new deck, `references/edit.md` to change an attached one
(use `load_skill` with `resource`). Both start with the same step, which installs the packages into Nova's own
environment without touching the system Python (tell the user what you install; it needs the internet once):
```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-pptx)
```

## Review: comments, notes, metadata, diff
```
python3 "<skill root>/scripts/pptx_comments.py" FILE         # comments per slide (classic and modern), with replies
python3 "<skill root>/scripts/office_meta.py" FILE           # author, dates, hidden slides, links, macros
python3 "<skill root>/scripts/pptx_diff.py" OLD NEW          # slide text and notes that differ
```
To resolve, delete or add comments, edit speaker notes or metadata, read `references/review.md`.

## Rules
- Never overwrite the attached original. Save results as a new file in the scratch folder (or where the user asks)
  and say where it is.
- After writing, read the result back with `pptx_text.py` to check it, and say what you changed.
- `.ppt` / `.key` / `.odp`: convert first (`soffice --headless --convert-to pptx FILE`, LibreOffice).
  To check how slides look: `soffice --headless --convert-to pdf FILE`, then look at the PDF.
