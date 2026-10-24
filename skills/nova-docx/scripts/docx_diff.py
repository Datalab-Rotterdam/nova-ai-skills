#!/usr/bin/env python3
"""Show what differs between two .docx files: text (paragraph by paragraph, changes word by word) and,
with --review, comments and tracked changes. Standard library only.

usage: docx_diff.py OLD.docx NEW.docx [--context 1] [--review]
"""
import argparse
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docx_review  # noqa: E402
import docx_text  # noqa: E402
import textdiff  # noqa: E402


def text_lines(path):
    with zipfile.ZipFile(path) as archive:
        return docx_text.body_lines(ET.fromstring(archive.read('word/document.xml')))


def review_lines(path):
    with zipfile.ZipFile(path) as archive:
        comments = docx_review.load_comments(archive)
        docx_review.anchored_text(archive, comments)
    state = lambda c: 'resolved' if c['done'] else 'open'  # noqa: E731
    return [f'comment by {c["author"]} [{state(c)}] on "{c["anchor"].strip()[:60]}": {c["text"]}' for c in comments.values()]


def main():
    parser = argparse.ArgumentParser(description='Diff two .docx files.')
    parser.add_argument('old')
    parser.add_argument('new')
    parser.add_argument('--context', type=int, default=1)
    parser.add_argument('--review', action='store_true', help='also compare comments')
    args = parser.parse_args()
    try:
        old, new = text_lines(args.old), text_lines(args.new)
    except (zipfile.BadZipFile, OSError, KeyError) as error:
        sys.exit(f'Cannot read the documents: {error}')
    lines, blocks = textdiff.diff_lines(old, new, args.context)
    print(f'=== Text: {blocks} changed block(s) ({len(old)} -> {len(new)} lines) ===')
    print('\n'.join(lines) if lines else 'identical')
    print('Legend: - removed, + added, ~ changed ([-old-]{+new+})')
    if args.review:
        lines, blocks = textdiff.diff_lines(review_lines(args.old), review_lines(args.new), 0)
        print(f'\n=== Comments: {blocks} changed block(s) ===')
        print('\n'.join(lines) if lines else 'identical')


if __name__ == '__main__':
    main()
