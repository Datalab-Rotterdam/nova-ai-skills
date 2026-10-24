#!/usr/bin/env python3
"""Print the review marks of a .docx: comments (with replies, who, when, resolved or open, and the text
they are attached to) and tracked changes (insertions, deletions, moves, formatting changes). Standard library only.

usage: docx_review.py FILE [--comments] [--changes]     (default: both)
"""
import argparse
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
W15 = '{http://schemas.microsoft.com/office/word/2012/wordml}'


def read_xml(archive, name):
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def paragraph_text(paragraph, deleted=False):
    tag = W + ('delText' if deleted else 't')
    return ''.join(e.text or '' for e in paragraph.iter(tag))


def load_comments(archive):
    root = read_xml(archive, 'word/comments.xml')
    comments = {}
    if root is None:
        return comments
    for item in root.findall(W + 'comment'):
        paragraphs = item.findall(W + 'p')
        comments[item.get(W + 'id')] = {
            'id': item.get(W + 'id'), 'author': item.get(W + 'author', ''), 'initials': item.get(W + 'initials', ''),
            'date': item.get(W + 'date', ''), 'text': '\n'.join(paragraph_text(p) for p in paragraphs).strip(),
            'para': paragraphs[-1].get(W14 + 'paraId') if paragraphs else None, 'parent': None, 'done': False, 'anchor': '',
        }
    by_para = {c['para']: c for c in comments.values() if c['para']}
    extended = read_xml(archive, 'word/commentsExtended.xml')
    for ex in extended if extended is not None else []:
        comment = by_para.get(ex.get(W15 + 'paraId'))
        if comment:
            comment['done'] = ex.get(W15 + 'done') == '1'
            parent = by_para.get(ex.get(W15 + 'paraIdParent'))
            comment['parent'] = parent['id'] if parent else None
    return comments


def anchored_text(archive, comments):
    """The document text between each comment's range markers."""
    root = read_xml(archive, 'word/document.xml')
    active = set()
    for element in root.iter() if root is not None else []:
        if element.tag == W + 'commentRangeStart':
            active.add(element.get(W + 'id'))
        elif element.tag == W + 'commentRangeEnd':
            active.discard(element.get(W + 'id'))
        elif element.tag == W + 't' and active:
            for comment_id in active:
                if comment_id in comments:
                    comments[comment_id]['anchor'] += element.text or ''


def print_comments(comments):
    roots = [c for c in comments.values() if not c['parent']]
    print(f'=== Comments ({len(comments)}) ===')
    if not comments:
        print('none')
    for comment in roots:
        state = 'resolved' if comment['done'] else 'open'
        print(f'#{comment["id"]} {comment["author"]} {comment["date"]} [{state}]')
        if comment['anchor'].strip():
            print(f'   on: "{comment["anchor"].strip()[:200]}"')
        print('   ' + comment['text'].replace('\n', '\n   '))
        for reply in (c for c in comments.values() if c['parent'] == comment['id']):
            print(f'   -> #{reply["id"]} {reply["author"]} {reply["date"]}: {reply["text"]}'.replace('\n', '\n      '))


def print_changes(archive):
    root = read_xml(archive, 'word/document.xml')
    rows = []
    kinds = {W + 'ins': 'inserted', W + 'del': 'deleted', W + 'moveFrom': 'moved from', W + 'moveTo': 'moved to',
             W + 'rPrChange': 'format changed', W + 'pPrChange': 'paragraph format changed'}
    for number, paragraph in enumerate(root.iter(W + 'p') if root is not None else [], 1):
        for element in paragraph.iter():
            kind = kinds.get(element.tag)
            if not kind or element.get(W + 'author') is None:
                continue
            text = paragraph_text(element) or paragraph_text(element, deleted=True)
            if element.tag in (W + 'rPrChange', W + 'pPrChange'):
                text = paragraph_text(paragraph)[:60]
            rows.append((number, kind, element.get(W + 'id'), element.get(W + 'author'), element.get(W + 'date', ''), text))
    print(f'=== Tracked changes ({len(rows)}) ===')
    if not rows:
        print('none')
    for number, kind, change_id, author, date, text in rows[:300]:
        shown = f'"{text[:160]}"' if text else '(paragraph mark or empty)'
        print(f'#{change_id} paragraph {number}: {kind} {shown} by {author} {date}')
    if len(rows) > 300:
        print(f'... {len(rows) - 300} more')


def main():
    parser = argparse.ArgumentParser(description='Comments and tracked changes of a .docx.')
    parser.add_argument('file')
    parser.add_argument('--comments', action='store_true')
    parser.add_argument('--changes', action='store_true')
    args = parser.parse_args()
    both = not (args.comments or args.changes)
    try:
        archive = zipfile.ZipFile(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as a .docx document: {error}')
    with archive:
        if args.comments or both:
            comments = load_comments(archive)
            anchored_text(archive, comments)
            print_comments(comments)
        if args.changes or both:
            print_changes(archive)


if __name__ == '__main__':
    main()
