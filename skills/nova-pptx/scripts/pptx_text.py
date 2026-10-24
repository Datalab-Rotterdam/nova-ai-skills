#!/usr/bin/env python3
"""Print the text of a .pptx presentation, slide by slide, with speaker notes. Standard library only.

usage: pptx_text.py FILE
"""
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'


def read_xml(archive, name):
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def relationships(archive, part):
    """Relationship Id -> (type, absolute target) of a part."""
    folder, name = posixpath.split(part)
    root = read_xml(archive, posixpath.join(folder, '_rels', name + '.rels'))
    result = {}
    for rel in root.findall(REL + 'Relationship') if root is not None else []:
        target = rel.get('Target', '')
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(folder, target))
        result[rel.get('Id')] = (rel.get('Type', ''), path)
    return result


def paragraphs(shape_root):
    lines = []
    for paragraph in shape_root.iter(A + 'p'):
        text = ''.join(t.text or '' for t in paragraph.iter(A + 't'))
        if text.strip():
            properties = paragraph.find(A + 'pPr')
            level = int(properties.get('lvl', '0')) if properties is not None else 0
            lines.append('  ' * level + text.strip())
    return lines


def slide_lines(archive, part):
    root = read_xml(archive, part)
    lines = []
    tree = root.find(P + 'cSld')
    for shape in tree.iter() if tree is not None else []:
        if shape.tag == P + 'sp':
            lines.extend(paragraphs(shape))
        elif shape.tag == A + 'tbl':
            for row in shape.findall(A + 'tr'):
                cells = [' '.join(paragraphs(cell)) for cell in row.findall(A + 'tc')]
                lines.append('| ' + ' | '.join(cell.replace('|', '/') for cell in cells) + ' |')
    return lines


def chart_lines(archive, part):
    """Title, categories and series values of a chart."""
    root = read_xml(archive, part)
    if root is None:
        return []
    lines = []
    title = ' '.join(t.text or '' for t in root.iter(A + 't'))
    lines.append(f'Chart: {title.strip()}' if title.strip() else 'Chart:')
    for series in root.iter(C + 'ser'):
        name = ' '.join(v.text or '' for v in series.findall(f'{C}tx//{C}v'))
        categories = [v.text or '' for v in series.findall(f'{C}cat//{C}pt/{C}v')]
        values = [v.text or '' for v in series.findall(f'{C}val//{C}pt/{C}v')]
        if categories:
            lines.append('  categories: ' + ', '.join(categories))
        lines.append(f'  {name or "series"}: ' + ', '.join(values))
    return lines


def slide_order(archive):
    presentation = read_xml(archive, 'ppt/presentation.xml')
    rels = relationships(archive, 'ppt/presentation.xml')
    order = []
    ids = presentation.find(P + 'sldIdLst') if presentation is not None else None
    for item in ids if ids is not None else []:
        target = rels.get(item.get(R + 'id'))
        if target:
            order.append(target[1])
    if order:
        return order
    names = [n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)]
    return sorted(names, key=lambda n: int(re.search(r'(\d+)\.xml$', n).group(1)))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        archive = zipfile.ZipFile(sys.argv[1])
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {sys.argv[1]} as a .pptx presentation: {error}')
    with archive:
        slides = slide_order(archive)
        if not slides:
            sys.exit('No slides found: this is not a .pptx presentation.')
        for number, part in enumerate(slides, 1):
            print(f'--- Slide {number} ---')
            print('\n'.join(slide_lines(archive, part)))
            for kind, target in relationships(archive, part).values():
                if kind.endswith('/chart'):
                    print('\n'.join(chart_lines(archive, target)))
                if kind.endswith('/notesSlide'):
                    notes = read_xml(archive, target)
                    text = [line for line in paragraphs(notes) if not line.strip().isdigit()] if notes is not None else []
                    if text:
                        print('Notes: ' + ' '.join(text))
            print()


if __name__ == '__main__':
    main()
