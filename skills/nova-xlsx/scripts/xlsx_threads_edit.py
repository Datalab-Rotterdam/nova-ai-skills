#!/usr/bin/env python3
"""Resolve or reopen threaded comments of an .xlsx and save a new file. Needs lxml (installed with openpyxl is
not enough: use the environment helper, which installs it):

  PY=$(python3 ensure_env.py openpyxl lxml)
  "$PY" xlsx_threads_edit.py FILE -o OUT.xlsx resolve THREAD_ID...     # ids as printed by xlsx_comments.py
  "$PY" xlsx_threads_edit.py FILE -o OUT.xlsx resolve --all
  "$PY" xlsx_threads_edit.py FILE -o OUT.xlsx reopen THREAD_ID...

Only the resolved flag changes, nothing else in the file. Classic notes have no resolved state: edit them
with openpyxl (see references/review.md).
"""
import argparse
import sys
import zipfile

from lxml import etree

TC = 'http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments'


def main():
    parser = argparse.ArgumentParser(description='Resolve or reopen threaded comments.')
    parser.add_argument('file')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('command', choices=['resolve', 'reopen'])
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    if args.output == args.file:
        sys.exit('Write to a new file, not over the original.')
    if not args.ids and not args.all:
        sys.exit('Give thread ids or --all.')
    done = '1' if args.command == 'resolve' else '0'
    changed = []
    with zipfile.ZipFile(args.file) as source, zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as out:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.startswith('xl/threadedComments/') and info.filename.endswith('.xml'):
                root = etree.fromstring(data)
                for item in root.findall('{%s}threadedComment' % TC):
                    if item.get('parentId') is None and (args.all or item.get('id') in args.ids):
                        item.set('done', done)
                        changed.append(item.get('id'))
                data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            out.writestr(info.filename, data)
    if not changed:
        sys.exit('No matching thread: ids come from xlsx_comments.py (the number after "thread").')
    print(f'{"Resolved" if args.command == "resolve" else "Reopened"} {len(changed)} thread(s). Saved {args.output}')


if __name__ == '__main__':
    main()
