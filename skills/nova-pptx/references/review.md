# Comments, speaker notes, metadata and diff (PowerPoint)

`<skill root>` is this skill's folder. Reading needs only Python 3. Changing needs the environment:
`PY=$(python3 "<skill root>/scripts/ensure_env.py" python-pptx)` (that installs lxml too).
Never write over the attached file: every change command takes `-o NEW.pptx`.

## Read
```
python3 "<skill root>/scripts/pptx_comments.py" FILE
python3 "<skill root>/scripts/pptx_text.py" FILE            # slide text, tables, charts and speaker notes
python3 "<skill root>/scripts/office_meta.py" FILE
python3 "<skill root>/scripts/pptx_diff.py" OLD.pptx NEW.pptx
```
- `pptx_comments.py`: comments per slide, classic and modern (threaded): author, date, open/resolved, replies.
- `pptx_diff.py`: slides compared by position: text and notes changes word by word, slides added or removed.
  A slide that moved shows as changes in every slide between; say so if the slide counts match but text shifts.

## Resolve, reopen, delete or add comments
```
"$PY" "<skill root>/scripts/pptx_comments_edit.py" FILE -o NEW.pptx resolve ID...        # modern comments, ids from pptx_comments.py
"$PY" "<skill root>/scripts/pptx_comments_edit.py" FILE -o NEW.pptx resolve --all
"$PY" "<skill root>/scripts/pptx_comments_edit.py" FILE -o NEW.pptx reopen ID...
"$PY" "<skill root>/scripts/pptx_comments_edit.py" FILE -o NEW.pptx delete ID...         # modern or classic ("legacy:0.1")
"$PY" "<skill root>/scripts/pptx_comments_edit.py" FILE -o NEW.pptx add --slide 3 "Text" --author "Nova AI"
```
Classic comments have no resolved state, so they can only be deleted. `add` writes a classic comment and is refused for
decks that already use modern comments (then put the text in the speaker notes or tell the user). Resolve or
delete only what the user asked for.

## Speaker notes (python-pptx)
```python
from pptx import Presentation
prs = Presentation("ATTACHED.pptx")
slide = prs.slides[1]
print(slide.has_notes_slide and slide.notes_slide.notes_text_frame.text)
slide.notes_slide.notes_text_frame.text = "New notes"            # creates the notes page if the slide has none
slide.notes_slide.notes_text_frame.text = ""                     # clear
prs.save("scratch-path/ATTACHED-notes.pptx")
```

## Metadata and hidden things
```python
core = prs.core_properties           # title, subject, author, keywords, comments, category, last_modified_by, revision
core.title = "Q3 review"; core.author = "Finance"; core.last_modified_by = "Finance"; core.comments = ""
slide._element.set("show", "0")      # hide a slide ("1" or remove the attribute to show it again)
```
`office_meta.py` lists hidden slides, embedded objects, external links and macros; report them before a deck is shared.
