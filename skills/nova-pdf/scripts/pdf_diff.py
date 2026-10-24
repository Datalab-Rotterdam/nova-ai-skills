#!/usr/bin/env python3
"""Show what differs between two PDFs: text page by page (changes word by word), page counts, and
metadata. Works with pdftotext, pypdf & co. (see pdf_text.py).

usage: pdf_diff.py OLD.pdf NEW.pdf [--context 1]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_text  # noqa: E402
import textdiff  # noqa: E402


def lines_by_page(path):
    pages = pdf_text.extract_pages(path)
    return {number: [' '.join(line.split()) for line in text.splitlines() if line.strip()] for number, text in pages}


def main():
    parser = argparse.ArgumentParser(description='Diff two PDFs.')
    parser.add_argument('old')
    parser.add_argument('new')
    parser.add_argument('--context', type=int, default=1)
    args = parser.parse_args()
    old, new = lines_by_page(args.old), lines_by_page(args.new)
    print(f'Pages: {len(old)} -> {len(new)}')
    changed = 0
    for number in range(1, max(len(old), len(new)) + 1):
        before, after = old.get(number), new.get(number)
        if before is None or after is None:
            print(f'=== Page {number}: {"added" if before is None else "removed"} ===')
            print('\n'.join(('+ ' if before is None else '- ') + line for line in (after if before is None else before)))
            changed += 1
            continue
        lines, blocks = textdiff.diff_lines(before, after, args.context)
        if blocks:
            changed += 1
            print(f'=== Page {number} ===')
            print('\n'.join(lines))
    print('identical text' if not changed else 'Legend: - removed, + added, ~ changed ([-old-]{+new+}). Page breaks can shift when text is added.')


if __name__ == '__main__':
    main()
