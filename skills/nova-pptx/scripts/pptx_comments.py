#!/usr/bin/env python3
"""Print the comments of a .pptx, slide by slide: classic comments and modern (threaded) comments with their
replies, who, when, and resolved or open. Speaker notes are in pptx_text.py. Standard library only.

usage: pptx_comments.py FILE
"""
import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pptx_text  # noqa: E402

P = pptx_text.P
A = pptx_text.A
MODERN = '{http://schemas.microsoft.com/office/powerpoint/2018/8/main}'


def legacy_authors(archive):
    root = pptx_text.read_xml(archive, 'ppt/commentAuthors.xml')
    return {a.get('id'): a.get('name', '') for a in root} if root is not None else {}


def modern_authors(archive):
    root = pptx_text.read_xml(archive, 'ppt/authors.xml')
    return {a.get('id'): a.get('name', '') for a in root} if root is not None else {}


def modern_text(element):
    body = element.find(MODERN + 'txBody')
    if body is None:
        return ''
    return '\n'.join(''.join(t.text or '' for t in p.iter(A + 't')) for p in body.iter(A + 'p')).strip()


def slide_comments(archive, slide_part, legacy, modern):
    found = []
    for kind, target in pptx_text.relationships(archive, slide_part).values():
        if not kind.endswith('/comments'):
            continue
        root = pptx_text.read_xml(archive, target)
        for cm in root if root is not None else []:
            if cm.tag == P + 'cm':
                text = cm.find(P + 'text')
                found.append({'id': f'legacy:{cm.get("authorId")}.{cm.get("idx")}', 'author': legacy.get(cm.get('authorId'), cm.get('authorId')),
                              'date': cm.get('dt', ''), 'status': '', 'text': (text.text or '') if text is not None else '', 'replies': []})
            elif cm.tag == MODERN + 'cm':
                replies = []
                for reply in cm.iter(MODERN + 'reply'):
                    replies.append({'author': modern.get(reply.get('authorId'), reply.get('authorId')), 'date': reply.get('created', ''), 'text': modern_text(reply)})
                found.append({'id': cm.get('id'), 'author': modern.get(cm.get('authorId'), cm.get('authorId')), 'date': cm.get('created', ''),
                              'status': cm.get('status', 'active'), 'text': modern_text(cm), 'replies': replies})
    return found


def main():
    parser = argparse.ArgumentParser(description='Comments of a .pptx.')
    parser.add_argument('file')
    args = parser.parse_args()
    try:
        archive = zipfile.ZipFile(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as a .pptx presentation: {error}')
    with archive:
        legacy, modern = legacy_authors(archive), modern_authors(archive)
        total = 0
        for number, part in enumerate(pptx_text.slide_order(archive), 1):
            comments = slide_comments(archive, part, legacy, modern)
            if not comments:
                continue
            print(f'--- Slide {number} ---')
            for comment in comments:
                total += 1
                state = f' [{comment["status"]}]' if comment['status'] else ''
                print(f'[{comment["id"]}]{state} {comment["author"]} {comment["date"]}: {comment["text"]}'.replace('\n', '\n    '))
                for reply in comment['replies']:
                    print(f'    -> {reply["author"]} {reply["date"]}: {reply["text"]}'.replace('\n', '\n       '))
        print(f'({total} comment(s))' if total else 'No comments.')


if __name__ == '__main__':
    main()
