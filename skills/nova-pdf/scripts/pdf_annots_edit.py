#!/usr/bin/env python3
"""Add, answer, resolve or delete comments (annotations) of a PDF and save a new file. Needs pypdf.

  PY=$(python3 ensure_env.py pypdf)
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf note --page 2 "Check this figure" [--x 72 --y 700] [--author "Nova AI"]
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf reply P2.1 "Fixed in v2" [--author "Nova AI"]
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf resolve P2.1 [P3.2 ...]     # sets the review state "Completed"
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf reopen P2.1
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf delete P2.1 [P3.2 ...]      # a comment and its replies
  "$PY" pdf_annots_edit.py FILE -o OUT.pdf delete --author "Ada"       # every comment by an author

Ids (P<page>.<number>) are the ones pdf_review.py prints. Highlights, stamps and drawings are not created here;
see references/edit.md for pypdf.annotations.
"""
import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_text  # noqa: E402

pypdf = pdf_text.require_pypdf()
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, TextStringObject  # noqa: E402

SKIP = {'/Link', '/Popup', '/Widget'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("D:%Y%m%d%H%M%SZ")


def locate(writer, annotation_id):
    """(page index, position in /Annots, annotation dictionary, its indirect reference) for an id like P2.1."""
    match = re.fullmatch(r'P(\d+)\.(\d+)', annotation_id)
    if not match:
        sys.exit(f'{annotation_id} is not an annotation id (P<page>.<number>, as printed by pdf_review.py).')
    page_index, position = int(match.group(1)) - 1, int(match.group(2)) - 1
    annots = writer.pages[page_index].get('/Annots') if 0 <= page_index < len(writer.pages) else None
    if annots is None or not 0 <= position < len(annots):
        sys.exit(f'There is no annotation {annotation_id}.')
    return page_index, position, annots[position].get_object(), annots[position]


def new_annotation(writer, page_index, rect, contents, author, subject=None, extra=None):
    annot = DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'),
        NameObject('/Subtype'): NameObject('/Text'),
        NameObject('/Rect'): ArrayObject([FloatObject(v) for v in rect]),
        NameObject('/Contents'): TextStringObject(contents),
        NameObject('/T'): TextStringObject(author),
        NameObject('/M'): TextStringObject(now()),
        NameObject('/Name'): NameObject('/Comment'),
        NameObject('/F'): pypdf.generic.NumberObject(4),
    })
    if subject:
        annot[NameObject('/Subj')] = TextStringObject(subject)
    annot.update(extra or {})
    page = writer.pages[page_index]
    ref = writer._add_object(annot)
    if '/Annots' not in page:
        page[NameObject('/Annots')] = ArrayObject()
    page['/Annots'].append(ref)
    return ref


def replies_of(writer, parent_ref):
    found = []
    for page_index, page in enumerate(writer.pages):
        for position, ref in enumerate(page.get('/Annots') or []):
            irt = ref.get_object().get('/IRT')
            if irt is not None and getattr(irt, 'idnum', None) == parent_ref.idnum:
                found.append((page_index, ref))
    return found


def delete(writer, ref_and_page):
    page_index, ref = ref_and_page
    annots = writer.pages[page_index]['/Annots']
    for i, item in enumerate(annots):
        if item.idnum == ref.idnum:
            del annots[i]
            break


def main():
    parser = argparse.ArgumentParser(description='Add, answer, resolve or delete PDF comments.')
    parser.add_argument('file')
    parser.add_argument('-o', '--output', required=True, help='new file to write (never the original)')
    commands = parser.add_subparsers(dest='command', required=True)
    note = commands.add_parser('note')
    note.add_argument('text')
    note.add_argument('--page', type=int, required=True)
    note.add_argument('--x', type=float, default=72)
    note.add_argument('--y', type=float, default=700)
    note.add_argument('--author', default='Nova AI')
    reply = commands.add_parser('reply')
    reply.add_argument('id')
    reply.add_argument('text')
    reply.add_argument('--author', default='Nova AI')
    for name in ('resolve', 'reopen'):
        sub = commands.add_parser(name)
        sub.add_argument('ids', nargs='+')
        sub.add_argument('--author', default='Nova AI')
    delete_cmd = commands.add_parser('delete')
    delete_cmd.add_argument('ids', nargs='*')
    delete_cmd.add_argument('--author')
    args = parser.parse_args()
    if args.output == args.file:
        sys.exit('Write to a new file, not over the original.')

    try:
        reader = pypdf.PdfReader(args.file)
        if reader.is_encrypted:
            reader.decrypt('')
        writer = pypdf.PdfWriter(clone_from=reader)
    except Exception as error:  # noqa: BLE001
        sys.exit(f'Cannot open {args.file} as a PDF: {error}')

    if args.command == 'note':
        if not 1 <= args.page <= len(writer.pages):
            sys.exit(f'The PDF has {len(writer.pages)} pages.')
        new_annotation(writer, args.page - 1, (args.x, args.y, args.x + 20, args.y + 20), args.text, args.author)
        print(f'Added a comment on page {args.page}.')
    elif args.command == 'reply':
        page_index, _, parent, parent_ref = locate(writer, args.id)
        x1, y1, x2, y2 = (float(v) for v in parent['/Rect'])
        new_annotation(writer, page_index, (x1, y1 - 24, x1 + 20, y1 - 4), args.text, args.author,
                       extra={NameObject('/IRT'): parent_ref, NameObject('/RT'): NameObject('/R')})
        print(f'Replied to {args.id}.')
    elif args.command in ('resolve', 'reopen'):
        state = 'Completed' if args.command == 'resolve' else 'None'
        for annotation_id in args.ids:
            page_index, _, parent, parent_ref = locate(writer, annotation_id)
            x1, y1, x2, y2 = (float(v) for v in parent['/Rect'])
            new_annotation(writer, page_index, (x1, y1 - 24, x1 + 20, y1 - 4), '', args.author, subject=state,
                           extra={NameObject('/IRT'): parent_ref, NameObject('/RT'): NameObject('/R'),
                                  NameObject('/StateModel'): TextStringObject('Review'), NameObject('/State'): TextStringObject(state)})
        print(f'{"Resolved" if args.command == "resolve" else "Reopened"} {len(args.ids)} comment(s).')
    else:
        targets = []
        for annotation_id in args.ids:
            page_index, _, _, ref = locate(writer, annotation_id)
            targets.append((page_index, ref))
        if args.author:
            for page_index, page in enumerate(writer.pages):
                for ref in page.get('/Annots') or []:
                    annot = ref.get_object()
                    if str(annot.get('/Subtype')) not in SKIP and str(annot.get('/T', '')) == args.author:
                        targets.append((page_index, ref))
        if not targets:
            sys.exit('Give annotation ids or --author.')
        count = 0
        for page_index, ref in targets:
            for reply_page, reply_ref in replies_of(writer, ref):
                delete(writer, (reply_page, reply_ref))
                count += 1
            delete(writer, (page_index, ref))
            count += 1
        print(f'Deleted {count} annotation(s) including replies.')
    writer.write(args.output)
    print('Saved ' + args.output)


if __name__ == '__main__':
    main()
