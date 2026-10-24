#!/usr/bin/env python3
"""Resolve, reopen, delete or add comments of a .pptx and save a new file. Needs lxml (installed with
python-pptx):

  PY=$(python3 ensure_env.py python-pptx)
  "$PY" pptx_comments_edit.py FILE -o OUT.pptx resolve ID...        # ids as printed by pptx_comments.py
  "$PY" pptx_comments_edit.py FILE -o OUT.pptx resolve --all
  "$PY" pptx_comments_edit.py FILE -o OUT.pptx reopen ID...
  "$PY" pptx_comments_edit.py FILE -o OUT.pptx delete ID...
  "$PY" pptx_comments_edit.py FILE -o OUT.pptx add --slide 3 "Text of the comment" --author "Nova AI"

Resolve and reopen work on modern (threaded) comments, which have a status. Classic comments have none;
they can be deleted or added. Adding is only offered for decks without modern comments.
Speaker notes are not comments: change them with python-pptx (see references/review.md).
"""
import argparse
import datetime
import os
import posixpath
import re
import sys
import zipfile

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pptx_text  # noqa: E402

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
MODERN = 'http://schemas.microsoft.com/office/powerpoint/2018/8/main'
RELS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
REL_COMMENTS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments'
REL_AUTHORS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors'
TYPE_COMMENTS = 'application/vnd.openxmlformats-officedocument.presentationml.comments+xml'
TYPE_AUTHORS = 'application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml'


class Package:
    def __init__(self, path):
        with zipfile.ZipFile(path) as archive:
            self.infos = archive.infolist()
            self.data = {info.filename: archive.read(info.filename) for info in self.infos}
        self.trees = {}

    def tree(self, name):
        if name not in self.trees and name in self.data:
            self.trees[name] = etree.fromstring(self.data[name])
        return self.trees.get(name)

    def create(self, name, root):
        self.trees[name] = root
        self.data[name] = b''
        self.infos.append(zipfile.ZipInfo(name))

    def save(self, path):
        for name, root in self.trees.items():
            self.data[name] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in self.infos:
                out.writestr(info.filename, self.data[info.filename])


def add_override(package, part, content_type):
    root = package.tree('[Content_Types].xml')
    etree.SubElement(root, '{%s}Override' % CT, PartName='/' + part, ContentType=content_type)


def add_relationship(package, rels_part, rel_type, target):
    root = package.tree(rels_part)
    if root is None:
        root = etree.Element('{%s}Relationships' % RELS, nsmap={None: RELS})
        package.create(rels_part, root)
    ids = [int(i[3:]) for i in root.xpath('//@Id') if re.fullmatch(r'rId\d+', i)] or [0]
    new = 'rId%d' % (max(ids) + 1)
    etree.SubElement(root, '{%s}Relationship' % RELS, Id=new, Type=rel_type, Target=target)
    return new


def comment_parts(package):
    return [n for n in package.data if n.startswith('ppt/comments/') and n.endswith('.xml')]


def set_status(package, ids, everything, status):
    done = []
    for name in comment_parts(package):
        root = package.tree(name)
        for cm in root.findall('{%s}cm' % MODERN):
            if everything or cm.get('id') in ids:
                cm.set('status', status)
                done.append(cm.get('id'))
    return done


def delete(package, ids):
    done = []
    for name in comment_parts(package):
        root = package.tree(name)
        for cm in list(root):
            if cm.tag == '{%s}cm' % MODERN and cm.get('id') in ids:
                root.remove(cm)
                done.append(cm.get('id'))
            elif cm.tag == '{%s}cm' % P and f'legacy:{cm.get("authorId")}.{cm.get("idx")}' in ids:
                root.remove(cm)
                done.append(f'legacy:{cm.get("authorId")}.{cm.get("idx")}')
    return done


def add_comment(package, source, slide_number, text, author, initials):
    if package.tree('ppt/authors.xml') is not None or any(
            comment_root is not None and any(c.tag == '{%s}cm' % MODERN for c in comment_root)
            for comment_root in (package.tree(n) for n in comment_parts(package))):
        sys.exit('This presentation uses modern comments; adding one here is not supported. Put the text in the speaker notes '
                 'or tell the user to add it in PowerPoint.')
    with zipfile.ZipFile(source) as archive:
        slides = pptx_text.slide_order(archive)
    if not 1 <= slide_number <= len(slides):
        sys.exit(f'The presentation has {len(slides)} slides.')
    slide_part = slides[slide_number - 1]

    authors = package.tree('ppt/commentAuthors.xml')
    if authors is None:
        authors = etree.Element('{%s}cmAuthorLst' % P, nsmap={'p': P})
        package.create('ppt/commentAuthors.xml', authors)
        add_override(package, 'ppt/commentAuthors.xml', TYPE_AUTHORS)
        add_relationship(package, 'ppt/_rels/presentation.xml.rels', REL_AUTHORS, 'commentAuthors.xml')
    entry = next((a for a in authors if a.get('name') == author), None)
    if entry is None:
        ids = [int(a.get('id')) for a in authors] or [-1]
        entry = etree.SubElement(authors, '{%s}cmAuthor' % P, id=str(max(ids) + 1), name=author, initials=initials,
                                 lastIdx='0', clrIdx=str(len(ids) % 6))
    index = int(entry.get('lastIdx')) + 1
    entry.set('lastIdx', str(index))

    folder, name = posixpath.split(slide_part)
    rels_part = posixpath.join(folder, '_rels', name + '.rels')
    comment_part = None
    rels = package.tree(rels_part)
    for rel in rels if rels is not None else []:
        if rel.get('Type') == REL_COMMENTS:
            comment_part = posixpath.normpath(posixpath.join(folder, rel.get('Target')))
    if comment_part is None:
        number = 1
        while f'ppt/comments/comment{number}.xml' in package.data:
            number += 1
        comment_part = f'ppt/comments/comment{number}.xml'
        package.create(comment_part, etree.Element('{%s}cmLst' % P, nsmap={'p': P}))
        add_override(package, comment_part, TYPE_COMMENTS)
        add_relationship(package, rels_part, REL_COMMENTS, '../comments/' + posixpath.basename(comment_part))
    root = package.tree(comment_part)
    cm = etree.SubElement(root, '{%s}cm' % P, authorId=entry.get('id'), idx=str(index),
                          dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000'))
    etree.SubElement(cm, '{%s}pos' % P, x='10', y='10')
    etree.SubElement(cm, '{%s}text' % P).text = text
    return f'legacy:{entry.get("id")}.{index}'


def main():
    parser = argparse.ArgumentParser(description='Resolve, reopen, delete or add comments in a .pptx.')
    parser.add_argument('file')
    parser.add_argument('-o', '--output', required=True, help='new file to write (never the original)')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('resolve', 'reopen', 'delete'):
        sub = commands.add_parser(name)
        sub.add_argument('ids', nargs='*')
        if name != 'delete':
            sub.add_argument('--all', action='store_true')
    add = commands.add_parser('add')
    add.add_argument('text')
    add.add_argument('--slide', type=int, required=True)
    add.add_argument('--author', default='Nova AI')
    add.add_argument('--initials', default='NA')
    args = parser.parse_args()
    if args.output == args.file:
        sys.exit('Write to a new file, not over the original.')
    try:
        package = Package(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as a .pptx presentation: {error}')
    if args.command in ('resolve', 'reopen'):
        if not args.ids and not args.all:
            sys.exit('Give comment ids or --all.')
        done = set_status(package, args.ids, args.all, 'resolved' if args.command == 'resolve' else 'active')
        if not done:
            sys.exit('No matching modern comment (classic comments have no resolved state). Ids come from pptx_comments.py.')
        print(f'{"Resolved" if args.command == "resolve" else "Reopened"} {len(done)} comment(s).')
    elif args.command == 'delete':
        if not args.ids:
            sys.exit('Give comment ids.')
        done = delete(package, args.ids)
        if not done:
            sys.exit('No matching comment. Ids come from pptx_comments.py.')
        print(f'Deleted {len(done)} comment(s).')
    else:
        print('Added comment ' + add_comment(package, args.file, args.slide, args.text, args.author, args.initials))
    package.save(args.output)
    print('Saved ' + args.output)


if __name__ == '__main__':
    main()
