#!/usr/bin/env python3
"""Print the metadata of an Office file (.docx, .xlsx, .pptx) and what it hides: author, dates, revision,
application, custom properties, comments, tracked changes, hidden sheets and slides, macros, external
links. Standard library only.

usage: office_meta.py FILE
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

CORE = {
    'title': 'Title', 'subject': 'Subject', 'creator': 'Author', 'keywords': 'Keywords', 'description': 'Description (comments)',
    'lastModifiedBy': 'Last modified by', 'revision': 'Revision', 'created': 'Created', 'modified': 'Modified',
    'category': 'Category', 'contentStatus': 'Status', 'language': 'Language', 'lastPrinted': 'Last printed',
}
APP = {
    'Application': 'Application', 'AppVersion': 'Version', 'Company': 'Company', 'Manager': 'Manager', 'Template': 'Template',
    'TotalTime': 'Editing time (min)', 'Pages': 'Pages', 'Words': 'Words', 'Characters': 'Characters', 'Slides': 'Slides',
    'Notes': 'Notes', 'HiddenSlides': 'Hidden slides (count)', 'Paragraphs': 'Paragraphs',
}


def local(tag):
    return tag.rsplit('}', 1)[-1]


def read_xml(archive, name):
    try:
        return ET.fromstring(archive.read(name))
    except (KeyError, ET.ParseError):
        return None


def describe_tracked(archive, names):
    counts = {}
    for name in names:
        if re.fullmatch(r'word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml', name):
            text = archive.read(name).decode('utf8', 'replace')
            for kind in ('ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange'):
                counts[kind] = counts.get(kind, 0) + len(re.findall(rf'<w:{kind}[ >]', text))
    parts = [f'{n} {kind}' for kind, n in counts.items() if n]
    return ', '.join(parts)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        archive = zipfile.ZipFile(sys.argv[1])
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {sys.argv[1]} as an Office file: {error}')
    with archive:
        names = archive.namelist()
        for part, labels, heading in (('docProps/core.xml', CORE, 'Document properties'), ('docProps/app.xml', APP, 'Application')):
            root = read_xml(archive, part)
            rows = [(labels[local(e.tag)], (e.text or '').strip()) for e in root if local(e.tag) in labels and (e.text or '').strip()] if root is not None else []
            if rows:
                print(f'== {heading} ==')
                for label, value in rows:
                    print(f'{label}: {value}')
        custom = read_xml(archive, 'docProps/custom.xml')
        if custom is not None and len(custom):
            print('== Custom properties ==')
            for prop in custom:
                value = next((v.text for v in prop if v.text is not None), '')
                print(f'{prop.get("name")}: {value}')

        found = []
        comments = [n for n in names if re.fullmatch(r'(word/comments\.xml|xl/comments.*\.xml|xl/threadedComments/.*\.xml|ppt/comments/.*\.xml|ppt/commentAuthors\.xml)', n)]
        if comments:
            found.append('comments/notes in ' + ', '.join(comments))
        tracked = describe_tracked(archive, names)
        if tracked:
            found.append('tracked changes: ' + tracked)
        workbook = read_xml(archive, 'xl/workbook.xml')
        if workbook is not None:
            hidden = [s.get('name') for s in workbook.iter() if local(s.tag) == 'sheet' and s.get('state') in ('hidden', 'veryHidden')]
            if hidden:
                found.append('hidden sheets: ' + ', '.join(hidden))
            defined = [d.get('name') for d in workbook.iter() if local(d.tag) == 'definedName' and not (d.get('name') or '').startswith('_xlnm')]
            if defined:
                found.append('named ranges: ' + ', '.join(defined[:20]))
        hidden_slides = [n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)
                         and re.search(r'<p:sld [^>]*show="0"', archive.read(n).decode('utf8', 'replace'))]
        if hidden_slides:
            found.append('hidden slides: ' + ', '.join(hidden_slides))
        for flag, pattern in (('macros (VBA)', r'vbaProject\.bin$'), ('external links', r'externalLinks/'), ('embedded objects', r'/embeddings/'),
                              ('images', r'/media/'), ('custom XML', r'^customXml/')):
            matching = [n for n in names if re.search(pattern, n)]
            if matching:
                found.append(f'{flag} ({len(matching)})')
        rels = [n for n in names if n.endswith('.rels')]
        external = sum(archive.read(n).decode('utf8', 'replace').count('TargetMode="External"') for n in rels)
        if external:
            found.append(f'external references ({external}: links, linked files)')
        print('== Contains ==')
        print('\n'.join(found) if found else 'nothing notable')


if __name__ == '__main__':
    main()
