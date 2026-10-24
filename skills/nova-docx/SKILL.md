---
name: nova-docx
description: Read, create and edit Word documents (.docx), including comments, tracked changes, metadata and diffs. Use for any Word file the user attached or asks for.
---

# Word documents (.docx)

An attached file reaches you as a path (`<attachment type="file" path="…" absolutePath="…">`).
Never guess its content; open it. `Skill root` in the `load_skill` result is this folder. Use `python3`
(or `python` / `py -3` where that is the name).

## Read (nothing to install)
```
python3 "<skill root>/scripts/docx_text.py" FILE
```
Prints headings (`#`), bullets (`-`), paragraphs, tables (`| a | b |`), footnotes and comments.
Formatting (fonts, colors, images) is not shown; for those use python-docx (see `references/edit.md`).

## Create or edit (needs python-docx)
Read `references/create.md` to make a new document, `references/edit.md` to change an attached one
(use `load_skill` with `resource`). Both start with the same step, which installs the packages into Nova's own
environment without touching the system Python (tell the user what you install; it needs the internet once):
```
PY=$(python3 "<skill root>/scripts/ensure_env.py" python-docx)
```

## Review: comments, tracked changes, metadata, diff
```
python3 "<skill root>/scripts/docx_review.py" FILE           # comments (with replies, resolved or open) and tracked changes
python3 "<skill root>/scripts/office_meta.py" FILE           # author, dates, revision, what the file hides
python3 "<skill root>/scripts/docx_diff.py" OLD NEW          # what changed between two versions
```
To add, reply to, resolve or delete comments, accept or reject tracked changes, suggest an edit as a tracked change
or edit metadata, read `references/review.md`. Resolve or accept only what the user asked for.

## Rules
- Never overwrite the attached original. Save results as a new file in the scratch folder (or where the user asks)
  and say where it is.
- After writing, read the result back with `docx_text.py` to check it, and say what you changed.
- `.doc` / `.rtf` / `.odt`: convert first (macOS `textutil -convert docx FILE`, or
  `soffice --headless --convert-to docx FILE`). For a PDF copy: `soffice --headless --convert-to pdf FILE`.
