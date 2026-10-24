#!/usr/bin/env python3
"""Show what differs between two .pptx files, slide by slide: text (changes word by word), speaker notes,
and slides added or removed. Slides are compared by position. Standard library only.

usage: pptx_diff.py OLD.pptx NEW.pptx
"""
import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pptx_text  # noqa: E402
import textdiff  # noqa: E402


def slides(path):
    """[(text lines, notes lines)] in presentation order."""
    with zipfile.ZipFile(path) as archive:
        result = []
        for part in pptx_text.slide_order(archive):
            lines = pptx_text.slide_lines(archive, part)
            for kind, target in pptx_text.relationships(archive, part).values():
                if kind.endswith('/chart'):
                    lines += pptx_text.chart_lines(archive, target)
            notes = []
            for kind, target in pptx_text.relationships(archive, part).values():
                if kind.endswith('/notesSlide'):
                    root = pptx_text.read_xml(archive, target)
                    notes = [t for t in pptx_text.paragraphs(root) if not t.strip().isdigit()] if root is not None else []
            result.append((lines, notes))
        return result


def main():
    parser = argparse.ArgumentParser(description='Diff two .pptx files.')
    parser.add_argument('old')
    parser.add_argument('new')
    args = parser.parse_args()
    try:
        old, new = slides(args.old), slides(args.new)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot read the presentations: {error}')
    print(f'Slides: {len(old)} -> {len(new)}')
    changed = 0
    for index in range(max(len(old), len(new))):
        number = index + 1
        if index >= len(old):
            print(f'=== Slide {number}: added ===')
            print('\n'.join('+ ' + line for line in new[index][0] + ['Notes: ' + n for n in new[index][1]]))
            changed += 1
            continue
        if index >= len(new):
            print(f'=== Slide {number}: removed ===')
            print('\n'.join('- ' + line for line in old[index][0] + ['Notes: ' + n for n in old[index][1]]))
            changed += 1
            continue
        before = old[index][0] + ['Notes: ' + n for n in old[index][1]]
        after = new[index][0] + ['Notes: ' + n for n in new[index][1]]
        lines, blocks = textdiff.diff_lines(before, after, 1)
        if blocks:
            changed += 1
            print(f'=== Slide {number} ===')
            print('\n'.join(lines))
    print('identical text and notes' if not changed else 'Legend: - removed, + added, ~ changed ([-old-]{+new+})')


if __name__ == '__main__':
    main()
