#!/usr/bin/env python3
"""Print the sheets of an .xlsx workbook as tab-separated text. Standard library only.

usage: xlsx_dump.py FILE [--sheet NAME] [--max-rows N] [--formulas]
"""
import argparse
import datetime
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
# Built-in number formats that are dates or times.
DATE_FORMATS = set(range(14, 23)) | {27, 30, 36} | set(range(45, 48)) | set(range(50, 59))


def read_xml(archive, name):
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def rich_text(element):
    """Text of a shared string or inline string, without phonetic hints."""
    parts = []
    for child in element:
        if child.tag == M + 't':
            parts.append(child.text or '')
        elif child.tag == M + 'r':
            text = child.find(M + 't')
            parts.append(text.text or '' if text is not None else '')
    return ''.join(parts)


def shared_strings(archive):
    root = read_xml(archive, 'xl/sharedStrings.xml')
    return [rich_text(item) for item in root.findall(M + 'si')] if root is not None else []


def date_styles(archive):
    """Indexes of cell styles that show a date or time."""
    root = read_xml(archive, 'xl/styles.xml')
    if root is None:
        return set()
    custom = {}
    formats = root.find(M + 'numFmts')
    if formats is not None:
        for item in formats.findall(M + 'numFmt'):
            custom[int(item.get('numFmtId'))] = item.get('formatCode', '')
    styles = set()
    xfs = root.find(M + 'cellXfs')
    for index, xf in enumerate(xfs.findall(M + 'xf') if xfs is not None else []):
        number_format = int(xf.get('numFmtId', '0'))
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '', custom.get(number_format, ''))
        if number_format in DATE_FORMATS or (number_format in custom and re.search(r'[ymdhs]', code, re.I)):
            styles.add(index)
    return styles


def excel_date(serial):
    value = float(serial)
    moment = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=value)
    if value == int(value):
        return moment.date().isoformat()
    return moment.replace(microsecond=0).isoformat(sep=' ')


def sheet_files(archive):
    """(name, path) of each sheet, in workbook order."""
    workbook = read_xml(archive, 'xl/workbook.xml')
    if workbook is None or workbook.find(M + 'sheets') is None:
        sys.exit('xl/workbook.xml is missing: this is not an .xlsx workbook.')
    rels = read_xml(archive, 'xl/_rels/workbook.xml.rels')
    targets = {}
    for rel in rels.findall(REL + 'Relationship') if rels is not None else []:
        target = rel.get('Target', '')
        targets[rel.get('Id')] = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
    sheets = []
    for sheet in workbook.find(M + 'sheets').findall(M + 'sheet'):
        path = targets.get(sheet.get(R + 'id'))
        if path:
            sheets.append((sheet.get('name', ''), path))
    return sheets


def column_index(reference):
    number = 0
    for char in re.match(r'[A-Z]+', reference).group(0):
        number = number * 26 + ord(char) - 64
    return number - 1


def clean(text):
    return re.sub(r'[\t\r\n]+', ' ', text)


def cell_value(cell, strings, dates, formulas):
    kind = cell.get('t')
    value = cell.find(M + 'v')
    text = value.text if value is not None and value.text is not None else ''
    if kind == 's':
        text = strings[int(text)] if text.isdigit() and int(text) < len(strings) else text
    elif kind == 'inlineStr':
        inline = cell.find(M + 'is')
        text = rich_text(inline) if inline is not None else ''
    elif kind == 'b':
        text = 'TRUE' if text == '1' else 'FALSE'
    elif kind in (None, 'n') and text and int(cell.get('s', '0')) in dates:
        try:
            text = excel_date(text)
        except (ValueError, OverflowError):
            pass
    formula = cell.find(M + 'f')
    if formulas and formula is not None and formula.text:
        text = f'{text} [={formula.text}]'
    return clean(text)


def dump_sheet(archive, name, path, strings, dates, max_rows, formulas):
    root = read_xml(archive, path)
    data = root.find(M + 'sheetData')
    rows = data.findall(M + 'row') if data is not None else []
    dimension = root.find(M + 'dimension')
    print(f'=== Sheet: {name} ({dimension.get("ref") if dimension is not None else f"{len(rows)} rows"}) ===')
    shown = 0
    for row in rows:
        cells = {}
        for cell in row.findall(M + 'c'):
            reference = cell.get('r')
            index = column_index(reference) if reference else len(cells)
            cells[index] = cell_value(cell, strings, dates, formulas)
        if not any(cells.values()):
            continue
        if shown >= max_rows:
            print(f'... more rows; use --max-rows to see them')
            break
        print(f'{row.get("r", "")}\t' + '\t'.join(cells.get(i, '') for i in range(max(cells) + 1)))
        shown += 1
    print()


def main():
    parser = argparse.ArgumentParser(description='Print an .xlsx workbook as text.')
    parser.add_argument('file')
    parser.add_argument('--sheet', help='only this sheet (name)')
    parser.add_argument('--max-rows', type=int, default=200, help='rows per sheet (default 200)')
    parser.add_argument('--formulas', action='store_true', help='show formulas next to their cached values')
    args = parser.parse_args()
    try:
        archive = zipfile.ZipFile(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as an .xlsx workbook: {error}')
    with archive:
        strings = shared_strings(archive)
        dates = date_styles(archive)
        sheets = sheet_files(archive)
        if args.sheet:
            sheets = [sheet for sheet in sheets if sheet[0] == args.sheet]
            if not sheets:
                sys.exit(f'No sheet named {args.sheet}.')
        else:
            print('Sheets: ' + ', '.join(name for name, _ in sheets) + '\n')
        for name, path in sheets:
            dump_sheet(archive, name, path, strings, dates, args.max_rows, args.formulas)


if __name__ == '__main__':
    main()
