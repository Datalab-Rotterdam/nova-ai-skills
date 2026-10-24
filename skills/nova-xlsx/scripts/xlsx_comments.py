#!/usr/bin/env python3
"""Print the notes and comments of an .xlsx workbook, per sheet and cell: classic notes (yellow boxes) and
threaded comments (with replies, who, when, resolved or open). Standard library only.

usage: xlsx_comments.py FILE [--sheet NAME]
"""
import argparse
import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET

import xlsx_dump

M = xlsx_dump.M
R = xlsx_dump.R
REL = xlsx_dump.REL
TC = '{http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments}'


def text_of(element):
    return ''.join(t.text or '' for t in element.iter(M + 't')).strip()


def part_rels(archive, part):
    folder, name = posixpath.split(part)
    root = xlsx_dump.read_xml(archive, posixpath.join(folder, '_rels', name + '.rels'))
    found = []
    for rel in root.findall(REL + 'Relationship') if root is not None else []:
        target = rel.get('Target', '')
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(folder, target))
        found.append((rel.get('Type', ''), path))
    return found


def persons(archive):
    names = {}
    for name in archive.namelist():
        if name.startswith('xl/persons/') and name.endswith('.xml'):
            root = xlsx_dump.read_xml(archive, name)
            for person in root if root is not None else []:
                names[person.get('id')] = person.get('displayName', '')
    return names


def sheet_comments(archive, path, people):
    notes, threads = [], {}
    for kind, target in part_rels(archive, path):
        if kind.endswith('/comments'):
            root = xlsx_dump.read_xml(archive, target)
            authors = [a.text or '' for a in root.iter(M + 'author')] if root is not None else []
            for comment in root.iter(M + 'comment') if root is not None else []:
                author = authors[int(comment.get('authorId', '0'))] if authors else ''
                notes.append({'ref': comment.get('ref'), 'author': author, 'text': text_of(comment)})
        elif kind.endswith('/threadedComment'):
            root = xlsx_dump.read_xml(archive, target)
            for item in root if root is not None else []:
                if not item.tag.endswith('threadedComment'):
                    continue
                text = item.find(TC + 'text')
                threads[item.get('id')] = {
                    'ref': item.get('ref'), 'author': people.get(item.get('personId'), item.get('personId', '')),
                    'date': item.get('dT', ''), 'done': item.get('done') == '1', 'parent': item.get('parentId'),
                    'text': (text.text or '') if text is not None else '', 'id': item.get('id'),
                }
    # Excel keeps a placeholder note ("tc={id}") for each thread: the thread itself is shown below.
    notes = [n for n in notes if not n['author'].startswith('tc=') and not n['text'].startswith('[Threaded comment]')]
    return notes, threads


def main():
    parser = argparse.ArgumentParser(description='Notes and comments of an .xlsx workbook.')
    parser.add_argument('file')
    parser.add_argument('--sheet')
    args = parser.parse_args()
    try:
        archive = zipfile.ZipFile(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as an .xlsx workbook: {error}')
    with archive:
        people = persons(archive)
        total = 0
        for name, path in xlsx_dump.sheet_files(archive):
            if args.sheet and name != args.sheet:
                continue
            notes, threads = sheet_comments(archive, path, people)
            if not notes and not threads:
                continue
            print(f'=== Sheet: {name} ===')
            for note in notes:
                total += 1
                print(f'{note["ref"]} [note] {note["author"]}: {note["text"]}'.replace('\n', '\n    '))
            for thread in (t for t in threads.values() if not t['parent']):
                total += 1
                state = 'resolved' if thread['done'] else 'open'
                print(f'{thread["ref"]} [thread {thread["id"]}, {state}] {thread["author"]} {thread["date"]}: {thread["text"]}'.replace('\n', '\n    '))
                for reply in (t for t in threads.values() if t['parent'] == thread['id']):
                    print(f'    -> {reply["author"]} {reply["date"]}: {reply["text"]}'.replace('\n', '\n       '))
        print(f'({total} note(s)/thread(s))' if total else 'No notes or comments.')


if __name__ == '__main__':
    main()
