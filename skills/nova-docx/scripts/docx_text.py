#!/usr/bin/env python3
"""Print the text of a .docx document: headings, paragraphs, tables, footnotes. Standard library only.

usage: docx_text.py FILE
"""
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def paragraph_text(paragraph):
    parts = []
    for element in paragraph.iter():
        if element.tag == W + 't':
            parts.append(element.text or '')
        elif element.tag == W + 'tab':
            parts.append('\t')
        elif element.tag in (W + 'br', W + 'cr'):
            parts.append('\n')
    return ''.join(parts)


def heading_prefix(paragraph):
    properties = paragraph.find(W + 'pPr')
    style = properties.find(W + 'pStyle') if properties is not None else None
    name = (style.get(W + 'val') if style is not None else '') or ''
    lowered = name.lower()
    if lowered == 'title':
        return '# '
    if lowered.startswith('heading') and lowered[7:].isdigit():
        return '#' * min(int(lowered[7:]), 6) + ' '
    if lowered.replace(' ', '').startswith('listbullet') or (properties is not None and properties.find(W + 'numPr') is not None):
        return '- '
    if lowered.replace(' ', '').startswith('listnumber'):
        return '1. '
    return ''


def table_lines(table):
    lines = []
    for row in table.findall(W + 'tr'):
        cells = []
        for cell in row.findall(W + 'tc'):
            text = ' '.join(paragraph_text(p).strip() for p in cell.iter(W + 'p'))
            cells.append(text.replace('|', '/'))
        lines.append('| ' + ' | '.join(cells) + ' |')
    return lines


def body_lines(root):
    body = root.find(W + 'body')
    lines = []
    for child in body if body is not None else root:
        if child.tag == W + 'p':
            text = paragraph_text(child).rstrip()
            lines.append(heading_prefix(child) + text if text else '')
        elif child.tag == W + 'tbl':
            lines.extend(table_lines(child))
            lines.append('')
    return lines


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        archive = zipfile.ZipFile(sys.argv[1])
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {sys.argv[1]} as a .docx document: {error}')
    with archive:
        try:
            document = ET.fromstring(archive.read('word/document.xml'))
        except KeyError:
            sys.exit('word/document.xml is missing: this is not a .docx document.')
        lines = body_lines(document)
        for name, title in (('word/footnotes.xml', 'Footnotes'), ('word/endnotes.xml', 'Endnotes'), ('word/comments.xml', 'Comments')):
            try:
                extra = [paragraph_text(p).strip() for p in ET.fromstring(archive.read(name)).iter(W + 'p')]
            except KeyError:
                continue
            extra = [line for line in extra if line]
            if extra:
                lines += ['', f'--- {title} ---'] + extra
    text = '\n'.join(lines)
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    print(text.strip())


if __name__ == '__main__':
    main()
