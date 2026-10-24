# Comments, tracked changes, metadata and diff (Word)

`<skill root>` is this skill's folder. Reading needs only Python 3; changing needs the environment:
`PY=$(python3 "<skill root>/scripts/ensure_env.py" python-docx)` (python-docx 1.2 or newer; that installs lxml too).
Never write over the attached file: every change command takes `-o NEW.docx`.

## Read
```
python3 "<skill root>/scripts/docx_review.py" FILE [--comments] [--changes]
python3 "<skill root>/scripts/office_meta.py" FILE
python3 "<skill root>/scripts/docx_diff.py" OLD.docx NEW.docx [--review]
```
- `docx_review.py`: every comment with id, author, date, open/resolved, the text it is attached to and its replies;
  every tracked change (inserted, deleted, moved, format changed) with author and date.
- `office_meta.py`: title, author, last modified by, created/modified, revision, application, company, custom
  properties, and what the file hides (comments, tracked changes, macros, external links, embedded objects).
- `docx_diff.py`: paragraph-level diff, changes shown word by word (`[-old-]{+new+}`). The text of a file with
  tracked changes is read as if all changes were accepted; to compare what the author proposed, use `reject`
  (below) on a copy and diff that against the original.

## Resolve, reply, delete comments; accept or reject tracked changes
```
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx resolve 0 2        # ids from docx_review.py
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx resolve --all
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx unresolve 0
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx reply 0 "Done, see section 2" --author "Nova AI"
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx delete 1            # a thread when it is the first comment
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx accept [--author NAME]
"$PY" "<skill root>/scripts/docx_review_edit.py" FILE -o NEW.docx reject [--author NAME]
```
Resolving marks the whole thread resolved (as Word does). After any change, run `docx_review.py` on the new file
and report what changed. Accept/reject restores insertions, deletions, moves and run/paragraph formatting;
table, section and numbering format changes only lose their record (the current formatting stays). Only resolve or
accept what the user asked for: those decisions are theirs.

## Add a comment (python-docx 1.2+)
```python
from docx import Document
doc = Document("ATTACHED.docx")
paragraph = next(p for p in doc.paragraphs if "30 days" in p.text)
doc.add_comment(runs=paragraph.runs, text="Can we shorten this?", author="Nova AI", initials="NA")  # runs = what it points at
doc.save("scratch-path/ATTACHED-commented.docx")
```
To point at part of a paragraph, give only the runs that hold that text; if the words are inside a longer run,
split the run first (copy the run element with `copy.deepcopy(run._r)`, cut the text of each copy).

## Suggest an edit as a tracked change
python-docx cannot do this itself; this helper wraps the old text in a deletion and the new text in an insertion
(the text must sit inside one run; formatting is kept):
```python
import copy, datetime, itertools
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
_ids = itertools.count(9000)

def tracked_replace(paragraph, old, new, author="Nova AI"):
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for run in paragraph.runs:
        at = run.text.find(old)
        if at < 0:
            continue
        def piece(text, deleted=False):
            clone = copy.deepcopy(run._r)
            for child in clone.findall(qn("w:t")) + clone.findall(qn("w:delText")):
                clone.remove(child)
            node = OxmlElement("w:delText" if deleted else "w:t")
            node.text = text
            node.set(qn("xml:space"), "preserve")
            clone.append(node)
            return clone
        def wrap(tag, child):
            element = OxmlElement(tag)
            for name, value in (("w:id", str(next(_ids))), ("w:author", author), ("w:date", date)):
                element.set(qn(name), value)
            element.append(child)
            return element
        parts = [piece(run.text[:at])] if at else []
        parts += [wrap("w:del", piece(old, True))] + ([wrap("w:ins", piece(new))] if new else [])
        if run.text[at + len(old):]:
            parts.append(piece(run.text[at + len(old):]))
        for part in parts:
            run._r.addprevious(part)
        run._r.getparent().remove(run._r)
        return True
    return False
```
Check with `docx_review.py` that the change shows up. Word shows it as a suggestion the user can accept or reject.

## Metadata
```python
props = doc.core_properties            # title, subject, author, keywords, comments, category, last_modified_by, revision
props.title = "Contract v2"; props.author = "Legal team"; props.last_modified_by = "Legal team"; props.comments = ""
import datetime; props.modified = datetime.datetime.now(datetime.timezone.utc)
```
To remove personal data before sharing: clear author, last_modified_by and comments as above, and report what is
still in the file with `office_meta.py` (comments, tracked changes and their authors are not removed by this).
