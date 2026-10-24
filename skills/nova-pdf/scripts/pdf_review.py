#!/usr/bin/env python3
"""Print a PDF's metadata and review marks: document properties, comments and other annotations (author, date,
text, replies, review state), form fields, bookmarks and attachments. Needs pypdf.

usage: pdf_review.py FILE [--all]      (--all also lists links and form widgets as annotations)
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_text  # noqa: E402

pypdf = pdf_text.require_pypdf()

SKIP = {'/Link', '/Popup', '/Widget'}


def pdf_date(value):
    match = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", str(value or ''))
    if not match:
        return str(value or '')
    year, month, day, hour, minute, second = (g or ('01' if i in (1, 2) else '00') for i, g in enumerate(match.groups()))
    return f'{year}-{month}-{day} {hour}:{minute}:{second}'


def text_of(value):
    return str(value).replace('\r', '\n').strip() if value is not None else ''


def annotations(reader, show_all):
    items = {}
    order = []
    for page_number, page in enumerate(reader.pages, 1):
        for index, ref in enumerate(page.get('/Annots') or [], 1):
            annot = ref.get_object()
            subtype = str(annot.get('/Subtype', ''))
            if subtype in SKIP and not show_all:
                continue
            key = getattr(ref, 'idnum', None)
            item = {'id': f'P{page_number}.{index}', 'page': page_number, 'type': subtype.lstrip('/'), 'author': text_of(annot.get('/T')),
                    'date': pdf_date(annot.get('/M')), 'text': text_of(annot.get('/Contents')), 'subject': text_of(annot.get('/Subj')),
                    'state': text_of(annot.get('/State')), 'model': text_of(annot.get('/StateModel')), 'parent': None, 'key': key}
            irt = annot.get('/IRT')
            item['parent'] = getattr(irt, 'idnum', None) if irt is not None else None
            if subtype == '/Link' and annot.get('/A') is not None:
                item['text'] = text_of(annot['/A'].get('/URI')) or item['text']
            items[key if key is not None else item['id']] = item
            order.append(item)
    return items, order


def outline(reader, nodes=None, depth=0, out=None):
    out = [] if out is None else out
    for node in reader.outline if nodes is None else nodes:
        if isinstance(node, list):
            outline(reader, node, depth + 1, out)
        else:
            try:
                page = reader.get_destination_page_number(node) + 1
            except Exception:  # noqa: BLE001
                page = '?'
            out.append('  ' * depth + f'{node.title} (page {page})')
    return out


def main():
    parser = argparse.ArgumentParser(description='Metadata and annotations of a PDF.')
    parser.add_argument('file')
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    try:
        reader = pypdf.PdfReader(args.file)
    except Exception as error:  # noqa: BLE001
        sys.exit(f'Cannot open {args.file} as a PDF: {error}')
    if reader.is_encrypted:
        try:
            reader.decrypt('')
        except Exception:  # noqa: BLE001
            sys.exit('This PDF is password protected.')

    print('== Document ==')
    info = reader.metadata or {}
    for key, label in (('/Title', 'Title'), ('/Author', 'Author'), ('/Subject', 'Subject'), ('/Keywords', 'Keywords'),
                       ('/Creator', 'Creator'), ('/Producer', 'Producer')):
        if info.get(key):
            print(f'{label}: {info[key]}')
    for key, label in (('/CreationDate', 'Created'), ('/ModDate', 'Modified')):
        if info.get(key):
            print(f'{label}: {pdf_date(info[key])}')
    print(f'Pages: {len(reader.pages)}; PDF {reader.pdf_header[5:] if hasattr(reader, "pdf_header") else "?"}; encrypted: {"yes" if reader.is_encrypted else "no"}')
    try:
        xmp = reader.xmp_metadata
    except Exception:  # noqa: BLE001
        xmp = None
    if xmp is not None:
        creators = getattr(xmp, 'dc_creator', None)
        if creators:
            print('XMP authors: ' + ', '.join(creators))
        for attribute, label in (('xmp_creator_tool', 'XMP tool'), ('pdf_producer', 'XMP producer')):
            if getattr(xmp, attribute, None):
                print(f'{label}: {getattr(xmp, attribute)}')

    items, order = annotations(reader, args.all)
    print(f'\n== Annotations ({sum(1 for i in order if i["parent"] is None)}) ==')
    for item in order:
        if item['parent'] is not None:
            continue
        replies = [r for r in order if r['parent'] == item['key'] and item['key'] is not None]
        states = [r['state'] for r in replies if r['state'] and r['model'] != 'Marked']
        status = f' [{states[-1]}]' if states else ''
        who = ' '.join(x for x in (item['author'], item['date']) if x)
        print(f'{item["id"]} page {item["page"]} {item["type"]}{status} {who}: {item["text"] or item["subject"]}'.replace('\n', '\n    '))
        for reply in replies:
            label = f'state {reply["state"]}' if reply['state'] else reply['text']
            print(f'    -> {reply["id"]} {reply["author"]} {reply["date"]}: {label}'.replace('\n', '\n       '))
    if not order:
        print('none')

    fields = reader.get_fields() or {}
    if fields:
        print(f'\n== Form fields ({len(fields)}) ==')
        for name, field in list(fields.items())[:100]:
            print(f'{name} = {field.get("/V")!r}')
    marks = outline(reader)
    if marks:
        print('\n== Bookmarks ==')
        print('\n'.join(marks[:100]))
    try:
        files = list(reader.attachments)
    except Exception:  # noqa: BLE001
        files = []
    if files:
        print('\n== Attachments ==\n' + '\n'.join(files))


if __name__ == '__main__':
    main()
