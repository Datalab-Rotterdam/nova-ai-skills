#!/usr/bin/env python3
"""Show what differs between two .xlsx workbooks: sheets added or removed, and cells that changed,
were added or removed. Standard library only.

usage: xlsx_diff.py OLD.xlsx NEW.xlsx [--formulas] [--sheet NAME] [--max 200]
"""
import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlsx_dump  # noqa: E402

M = xlsx_dump.M


def read_workbook(path, formulas):
    """{sheet name: {cell reference: text}}"""
    with zipfile.ZipFile(path) as archive:
        strings = xlsx_dump.shared_strings(archive)
        dates = xlsx_dump.date_styles(archive)
        book = {}
        for name, part in xlsx_dump.sheet_files(archive):
            cells = {}
            root = xlsx_dump.read_xml(archive, part)
            for cell in root.iter(M + 'c') if root is not None else []:
                value = xlsx_dump.cell_value(cell, strings, dates, formulas)
                if value != '':
                    cells[cell.get('r')] = value
            book[name] = cells
        return book


def sort_key(ref):
    letters = ''.join(c for c in ref if c.isalpha())
    return (int(''.join(c for c in ref if c.isdigit()) or 0), len(letters), letters)


def main():
    parser = argparse.ArgumentParser(description='Diff two .xlsx workbooks.')
    parser.add_argument('old')
    parser.add_argument('new')
    parser.add_argument('--formulas', action='store_true', help='compare formulas as well as values')
    parser.add_argument('--sheet')
    parser.add_argument('--max', type=int, default=200, help='most changes to list (default 200)')
    args = parser.parse_args()
    try:
        old, new = read_workbook(args.old, args.formulas), read_workbook(args.new, args.formulas)
    except (zipfile.BadZipFile, OSError, AttributeError) as error:
        sys.exit(f'Cannot read the workbooks: {error}')
    removed_sheets = [s for s in old if s not in new]
    added_sheets = [s for s in new if s not in old]
    print('Sheets removed: ' + (', '.join(removed_sheets) or 'none') + ' | added: ' + (', '.join(added_sheets) or 'none'))
    shown = changed = 0
    for sheet in (s for s in old if s in new and (not args.sheet or s == args.sheet)):
        before, after = old[sheet], new[sheet]
        lines = []
        for ref in sorted(set(before) | set(after), key=sort_key):
            if before.get(ref) == after.get(ref):
                continue
            if ref not in before:
                lines.append(f'  {ref}: added {after[ref]!r}')
            elif ref not in after:
                lines.append(f'  {ref}: removed {before[ref]!r}')
            else:
                lines.append(f'  {ref}: {before[ref]!r} -> {after[ref]!r}')
        if lines:
            print(f'=== {sheet}: {len(lines)} cell(s) differ ===')
            changed += len(lines)
            for line in lines[: max(0, args.max - shown)]:
                print(line)
            shown += min(len(lines), max(0, args.max - shown))
    if not changed and not removed_sheets and not added_sheets:
        print('identical cell values' + ('' if args.formulas else ' (use --formulas to compare formulas too)'))
    elif changed > shown:
        print(f'... {changed - shown} more; raise --max')


if __name__ == '__main__':
    main()
