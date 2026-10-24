#!/usr/bin/env python3
"""Change the review marks of a .docx and save the result as a new file: resolve, reopen, reply to or delete
comments, and accept or reject tracked changes. Needs lxml (installed with python-docx):

  PY=$(python3 ensure_env.py python-docx)
  "$PY" docx_review_edit.py FILE -o OUT.docx resolve 0 2        # comment ids, as printed by docx_review.py
  "$PY" docx_review_edit.py FILE -o OUT.docx resolve --all
  "$PY" docx_review_edit.py FILE -o OUT.docx unresolve 0
  "$PY" docx_review_edit.py FILE -o OUT.docx reply 0 "Done, see section 2" --author "Nova AI"
  "$PY" docx_review_edit.py FILE -o OUT.docx delete 1           # a comment (a thread when it is the first one)
  "$PY" docx_review_edit.py FILE -o OUT.docx accept [--author NAME]
  "$PY" docx_review_edit.py FILE -o OUT.docx reject [--author NAME]
"""
import argparse
import datetime
import random
import re
import sys
import zipfile

from lxml import etree

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
    'cid': 'http://schemas.microsoft.com/office/word/2016/wordml/cid',
    'r': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
}


def q(name):
    prefix, local = name.split(':')
    return '{%s}%s' % (NS[prefix], local)


EXTENDED_PART = 'word/commentsExtended.xml'
EXTENDED_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml'
EXTENDED_REL = 'http://schemas.microsoft.com/office/2011/relationships/commentsExtended'


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

    def save(self, path):
        for name, root in self.trees.items():
            self.data[name] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
            written = set()
            for info in self.infos:
                out.writestr(info.filename, self.data[info.filename])
                written.add(info.filename)
            for name, content in self.data.items():
                if name not in written:
                    out.writestr(name, content)


def used_para_ids(package):
    found = set()
    for name in ('word/document.xml', 'word/comments.xml'):
        root = package.tree(name)
        if root is not None:
            found.update(root.xpath('//@w14:paraId', namespaces=NS))
    return found


def new_para_id(used):
    while True:
        value = '%08X' % random.randint(1, 0x7FFFFFFE)
        if value not in used:
            used.add(value)
            return value


def last_para(comment):
    paragraphs = comment.findall(q('w:p'))
    return paragraphs[-1] if paragraphs else None


class Comments:
    def __init__(self, package):
        self.package = package
        self.root = package.tree('word/comments.xml')
        if self.root is None:
            sys.exit('This document has no comments.')
        self.used = used_para_ids(package)
        for comment in self.root.findall(q('w:comment')):
            paragraph = last_para(comment)
            if paragraph is not None and paragraph.get(q('w14:paraId')) is None:
                paragraph.set(q('w14:paraId'), new_para_id(self.used))
        self.extended = self.load_extended()

    def load_extended(self):
        root = self.package.tree(EXTENDED_PART)
        if root is None:
            root = etree.Element(q('w15:commentsEx'), nsmap={'w15': NS['w15']})
            self.package.trees[EXTENDED_PART] = root
            self.package.data[EXTENDED_PART] = b''
            self.package.infos.append(zipfile.ZipInfo(EXTENDED_PART))
            content_types = self.package.tree('[Content_Types].xml')
            override = etree.SubElement(content_types, q('ct:Override'))
            override.set('PartName', '/' + EXTENDED_PART)
            override.set('ContentType', EXTENDED_TYPE)
            rels = self.package.tree('word/_rels/document.xml.rels')
            ids = [int(i[3:]) for i in rels.xpath('//r:Relationship/@Id', namespaces=NS) if re.fullmatch(r'rId\d+', i)] or [0]
            rel = etree.SubElement(rels, q('r:Relationship'))
            rel.set('Id', 'rId%d' % (max(ids) + 1))
            rel.set('Type', EXTENDED_REL)
            rel.set('Target', 'commentsExtended.xml')
        return root

    def all(self):
        return self.root.findall(q('w:comment'))

    def get(self, comment_id):
        for comment in self.all():
            if comment.get(q('w:id')) == str(comment_id):
                return comment
        sys.exit(f'There is no comment with id {comment_id}.')

    def para_id(self, comment):
        return last_para(comment).get(q('w14:paraId'))

    def entry(self, comment, create=True):
        para = self.para_id(comment)
        for item in self.extended:
            if item.get(q('w15:paraId')) == para:
                return item
        if not create:
            return None
        item = etree.SubElement(self.extended, q('w15:commentEx'))
        item.set(q('w15:paraId'), para)
        item.set(q('w15:done'), '0')
        return item

    def parent_of(self, comment):
        entry = self.entry(comment, create=False)
        parent = entry.get(q('w15:paraIdParent')) if entry is not None else None
        return next((c for c in self.all() if parent and self.para_id(c) == parent), None)

    def thread(self, comment):
        """The first comment of a thread and all its replies."""
        head = self.parent_of(comment) or comment
        head_para = self.para_id(head)
        replies = [c for c in self.all() if (self.entry(c, create=False) is not None
                                             and self.entry(c, create=False).get(q('w15:paraIdParent')) == head_para)]
        return [head] + replies

    def set_done(self, comment, done):
        for member in self.thread(comment):
            self.entry(member).set(q('w15:done'), '1' if done else '0')

    def reply(self, comment, text, author, initials):
        head = comment
        parent_para = self.para_id(head)
        new_id = str(max(int(c.get(q('w:id'))) for c in self.all()) + 1)
        item = etree.SubElement(self.root, q('w:comment'))
        item.set(q('w:id'), new_id)
        item.set(q('w:author'), author)
        item.set(q('w:date'), datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        item.set(q('w:initials'), initials)
        paragraph = etree.SubElement(item, q('w:p'))
        para = new_para_id(self.used)
        paragraph.set(q('w14:paraId'), para)
        style = etree.SubElement(etree.SubElement(paragraph, q('w:pPr')), q('w:pStyle'))
        style.set(q('w:val'), 'CommentText')
        mark = etree.SubElement(paragraph, q('w:r'))
        etree.SubElement(etree.SubElement(mark, q('w:rPr')), q('w:rStyle')).set(q('w:val'), 'CommentReference')
        etree.SubElement(mark, q('w:annotationRef'))
        run = etree.SubElement(paragraph, q('w:r'))
        etree.SubElement(run, q('w:t')).text = text
        ex = etree.SubElement(self.extended, q('w15:commentEx'))
        ex.set(q('w15:paraId'), para)
        ex.set(q('w15:paraIdParent'), parent_para)
        done = self.entry(head, create=False)
        ex.set(q('w15:done'), done.get(q('w15:done')) if done is not None else '0')
        # Anchor the reply to the same text as the comment it answers.
        document = self.package.tree('word/document.xml')
        old = str(head.get(q('w:id')))
        start = document.xpath('//w:commentRangeStart[@w:id=$i]', namespaces=NS, i=old)
        end = document.xpath('//w:commentRangeEnd[@w:id=$i]', namespaces=NS, i=old)
        ref = document.xpath('//w:r[w:commentReference/@w:id=$i]', namespaces=NS, i=old)
        if start:
            marker = etree.Element(q('w:commentRangeStart'))
            marker.set(q('w:id'), new_id)
            start[0].addnext(marker)
        if end:
            marker = etree.Element(q('w:commentRangeEnd'))
            marker.set(q('w:id'), new_id)
            end[0].addnext(marker)
        if ref:
            run = etree.Element(q('w:r'))
            etree.SubElement(etree.SubElement(run, q('w:rPr')), q('w:rStyle')).set(q('w:val'), 'CommentReference')
            etree.SubElement(run, q('w:commentReference')).set(q('w:id'), new_id)
            ref[0].addnext(run)
        return new_id

    def delete(self, comment):
        members = self.thread(comment) if self.parent_of(comment) is None else [comment]
        document = self.package.tree('word/document.xml')
        for member in members:
            ident = member.get(q('w:id'))
            para = self.para_id(member)
            for element in document.xpath('//w:commentRangeStart[@w:id=$i] | //w:commentRangeEnd[@w:id=$i]', namespaces=NS, i=ident):
                element.getparent().remove(element)
            for run in document.xpath('//w:r[w:commentReference/@w:id=$i]', namespaces=NS, i=ident):
                run.getparent().remove(run)
            entry = self.entry(member, create=False)
            if entry is not None:
                self.extended.remove(entry)
            for name in ('word/commentsIds.xml',):
                ids = self.package.tree(name)
                for item in ids.xpath('//cid:commentId[@w16cid:paraId=$p]', namespaces={**NS, 'w16cid': NS['cid']}, p=para) if ids is not None else []:
                    ids.remove(item)
            self.root.remove(member)
        return len(members)


# ---- tracked changes ----

CHANGE_TAGS = ('ins', 'del', 'moveFrom', 'moveTo', 'rPrChange', 'pPrChange', 'sectPrChange', 'tblPrChange', 'trPrChange', 'tcPrChange',
               'tblGridChange', 'numberingChange', 'moveFromRangeStart', 'moveFromRangeEnd', 'moveToRangeStart', 'moveToRangeEnd')
CHANGE_PARTS = re.compile(r'word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml')


def local(element):
    return etree.QName(element).localname


def attached(element, root):
    while element is not None:
        if element is root:
            return True
        element = element.getparent()
    return False


def unwrap(element):
    parent = element.getparent()
    index = parent.index(element)
    for child in list(element):
        parent.insert(index, child)
        index += 1
    parent.remove(element)


def merge_with_next(paragraph):
    following = paragraph.getnext()
    if following is not None and following.tag == q('w:p'):
        for child in list(following):
            if child.tag != q('w:pPr'):
                paragraph.append(child)
        following.getparent().remove(following)


def deleted_text_to_text(element):
    for node in element.iter(q('w:delText')):
        node.tag = q('w:t')


def restore_properties(change, parent_tag):
    """Reject a format change: put the old properties (inside the change record) back."""
    parent = change.getparent()
    old = change.find(q(parent_tag))
    if old is None:
        parent.remove(change)
        return
    keep = [child for child in parent if child is not change and local(child) in ('rPr', 'sectPr')] if parent_tag == 'w:pPr' else []
    for child in list(parent):
        if child not in keep:
            parent.remove(child)
    for child in list(old):
        parent.append(child)


def resolve_changes(package, accept, author):
    counts = {}
    left = {}
    for name in list(package.data):
        if not CHANGE_PARTS.fullmatch(name):
            continue
        root = package.tree(name)
        while True:
            target = None
            for element in root.iter():
                if not isinstance(element.tag, str) or local(element) not in CHANGE_TAGS:
                    continue
                if element.tag.startswith('{' + NS['w'] + '}') and (author is None or element.get(q('w:author')) == author):
                    target = element
                    break
            if target is None:
                break
            kind = local(target)
            parent = target.getparent()
            marker = parent.tag in (q('w:rPr'), q('w:trPr')) and kind in ('ins', 'del')
            counts[kind] = counts.get(kind, 0) + 1
            if marker and parent.tag == q('w:trPr'):
                row = parent.getparent()
                remove_row = (kind == 'ins') != accept
                parent.remove(target)
                if remove_row:
                    row.getparent().remove(row)
            elif marker:
                paragraph = parent.getparent().getparent()
                parent.remove(target)
                merge = (kind == 'del') if accept else (kind == 'ins')
                if merge:
                    merge_with_next(paragraph)
            elif kind in ('moveFromRangeStart', 'moveFromRangeEnd', 'moveToRangeStart', 'moveToRangeEnd'):
                parent.remove(target)
            elif kind in ('ins', 'moveTo'):
                if accept:
                    unwrap(target)
                else:
                    parent.remove(target)
            elif kind in ('del', 'moveFrom'):
                if accept:
                    parent.remove(target)
                else:
                    deleted_text_to_text(target)
                    unwrap(target)
            elif kind == 'rPrChange':
                if accept:
                    parent.remove(target)
                else:
                    restore_properties(target, 'w:rPr')
            elif kind == 'pPrChange':
                if accept:
                    parent.remove(target)
                else:
                    restore_properties(target, 'w:pPr')
            else:
                # Table, section and numbering format changes: the record is dropped, the current formatting stays.
                left[kind] = left.get(kind, 0) + 1
                parent.remove(target)
    return counts, left


def main():
    parser = argparse.ArgumentParser(description='Resolve comments or accept/reject tracked changes in a .docx.')
    parser.add_argument('file')
    parser.add_argument('-o', '--output', required=True, help='new file to write (never the original)')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('resolve', 'unresolve', 'delete'):
        sub = commands.add_parser(name)
        sub.add_argument('ids', nargs='*')
        if name != 'delete':
            sub.add_argument('--all', action='store_true')
    reply = commands.add_parser('reply')
    reply.add_argument('id')
    reply.add_argument('text')
    reply.add_argument('--author', default='Nova AI')
    reply.add_argument('--initials', default='NA')
    for name in ('accept', 'reject'):
        commands.add_parser(name).add_argument('--author', help='only the changes of this author')
    args = parser.parse_args()
    if args.output == args.file:
        sys.exit('Write to a new file, not over the original.')
    try:
        package = Package(args.file)
    except (zipfile.BadZipFile, OSError) as error:
        sys.exit(f'Cannot open {args.file} as a .docx document: {error}')

    if args.command in ('accept', 'reject'):
        counts, left = resolve_changes(package, args.command == 'accept', args.author)
        summary = ', '.join(f'{n} {kind}' for kind, n in counts.items()) or 'no tracked changes'
        print(f'{args.command}ed: {summary}')
        if left:
            print('Format changes of tables/sections were not restored, only their records dropped: ' + ', '.join(left))
    else:
        comments = Comments(package)
        if args.command in ('resolve', 'unresolve'):
            targets = comments.all() if args.all else [comments.get(i) for i in args.ids]
            if not targets:
                sys.exit('Give comment ids or --all.')
            for comment in targets:
                comments.set_done(comment, args.command == 'resolve')
            print(f'{args.command}d {len(targets)} comment thread member(s) of ids: ' + ', '.join(c.get(q("w:id")) for c in targets))
        elif args.command == 'reply':
            print('Added reply #' + comments.reply(comments.get(args.id), args.text, args.author, args.initials))
        elif args.command == 'delete':
            total = sum(comments.delete(comments.get(i)) for i in args.ids)
            print(f'Deleted {total} comment(s).')
    package.save(args.output)
    print('Saved ' + args.output)


if __name__ == '__main__':
    main()
