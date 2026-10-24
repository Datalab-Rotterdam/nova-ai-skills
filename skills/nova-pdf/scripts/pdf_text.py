#!/usr/bin/env python3
"""Print the text of a PDF, page by page.

Uses the first of these that is installed: poppler's `pdftotext`, then the Python packages pypdf,
PyPDF2, pdfplumber, PyMuPDF. With none of them it falls back to a rough reader (standard library
only) that handles simple PDFs and says so.

usage: pdf_text.py FILE [--pages 1-5]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zlib


def parse_pages(spec):
    """'3' -> (3, 3); '2-5' -> (2, 5); '4-' -> (4, None); None -> (1, None)."""
    if not spec:
        return 1, None
    match = re.fullmatch(r'(\d+)(?:(-)(\d*))?', spec.strip())
    if not match:
        sys.exit('--pages looks like 3, 2-5 or 4-')
    first = int(match.group(1))
    if not match.group(2):
        return first, first
    return first, int(match.group(3)) if match.group(3) else None


def with_pdftotext(path, first, last):
    command = shutil.which('pdftotext')
    if not command:
        return None
    args = [command, '-layout', '-f', str(first)] + (['-l', str(last)] if last else []) + [path, '-']
    result = subprocess.run(args, capture_output=True, text=True, errors='replace')
    if result.returncode != 0:
        return None
    pages = result.stdout.split('\f')
    if pages and not pages[-1].strip():
        pages.pop()
    return [(first + i, text) for i, text in enumerate(pages)]


def with_package(path, first, last):
    for name in ('pypdf', 'PyPDF2'):
        try:
            module = __import__(name)
        except ImportError:
            continue
        reader = module.PdfReader(path)
        if getattr(reader, 'is_encrypted', False):
            try:
                reader.decrypt('')
            except Exception:
                sys.exit('This PDF is password protected.')
        end = min(last or len(reader.pages), len(reader.pages))
        return [(n, reader.pages[n - 1].extract_text() or '') for n in range(first, end + 1)]
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            end = min(last or len(pdf.pages), len(pdf.pages))
            return [(n, pdf.pages[n - 1].extract_text() or '') for n in range(first, end + 1)]
    except ImportError:
        pass
    try:
        import fitz
        with fitz.open(path) as document:
            end = min(last or document.page_count, document.page_count)
            return [(n, document[n - 1].get_text()) for n in range(first, end + 1)]
    except ImportError:
        return None


def unescape(raw):
    def replace(match):
        code = match.group(1)
        simple = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', '(': '(', ')': ')', '\\': '\\'}
        if code in simple:
            return simple[code]
        if code.isdigit():
            return chr(int(code, 8) & 0xFF)
        return code
    return re.sub(r'\\([0-7]{1,3}|.)', replace, raw, flags=re.S)


def rough_text(path):
    """Text from simple PDFs: uncompressed or Flate streams with plain text operators. No fonts maps, no OCR."""
    data = open(path, 'rb').read()
    pages = []
    for match in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        stream = match.group(1)
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            pass
        if b'BT' not in stream:
            continue
        text = stream.decode('latin-1')
        lines = []
        for block in re.findall(r'BT(.*?)ET', text, re.S):
            line = []
            for token in re.finditer(r'\[((?:\\.|[^\]])*)\]\s*TJ|\(((?:\\.|[^)\\])*)\)\s*(?:Tj|\'|")|(T\*|Td|TD)', block, re.S):
                if token.group(1) is not None:
                    line.append(''.join(unescape(s) for s in re.findall(r'\(((?:\\.|[^)\\])*)\)', token.group(1))))
                elif token.group(2) is not None:
                    line.append(unescape(token.group(2)))
                else:
                    line.append('\n')
            lines.append(''.join(line))
        content = '\n'.join(lines).strip()
        if content:
            pages.append(content)
    return pages


def nova_env_python():
    """Python of Nova's own environment (made by ensure_env.py) when it has a PDF reader and is not the one running."""
    home = os.environ.get('NOVA_AI_HOME') or os.path.join(os.path.expanduser('~'), '.nova-ai')
    env_dir = os.path.join(home, 'python-env')
    python = os.path.join(env_dir, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(env_dir, 'bin', 'python')
    if not os.path.exists(python) or os.path.abspath(sys.prefix) == os.path.abspath(env_dir):
        return None
    probe = subprocess.run([python, '-c', 'import pypdf'], capture_output=True)
    return python if probe.returncode == 0 else None


def require_pypdf():
    """pypdf, or re-run the current command with the python of Nova's environment, or stop with how to get it."""
    try:
        import pypdf
        return pypdf
    except ImportError:
        python = nova_env_python()
        if python:
            sys.exit(subprocess.run([python, os.path.abspath(sys.argv[0]), *sys.argv[1:]]).returncode)
        sys.exit('This needs the Python package pypdf. Install it into Nova\'s environment (ask the user first):\n'
                 '  PY=$(python3 "<skill root>/scripts/ensure_env.py" pypdf)  and run the command again with "$PY" instead of python3.')


def extract_pages(path, first=1, last=None):
    """[(page number, text)] of a PDF: pdftotext, pypdf & co., or a rough reader. Re-runs itself in Nova's environment
    when pypdf is only installed there."""
    pages = with_pdftotext(path, first, last) or with_package(path, first, last)
    if pages is not None:
        return pages
    python = nova_env_python()
    if python:
        sys.exit(subprocess.run([python, os.path.abspath(sys.argv[0]), *sys.argv[1:]]).returncode)
    rough = rough_text(path)
    if not rough:
        sys.exit('No text found. Either this PDF is a scan (needs OCR: ocrmypdf, or tesseract) or its text is encoded '
                 'in a way the built-in reader cannot decode. Install a reader and run this again: '
                 '`pip install --user pypdf` or poppler (`brew install poppler`, `apt install poppler-utils`). '
                 'Ask the user before installing.')
    print('(Rough reading without a PDF library: page breaks are approximate and some text may be missing. '
          'For exact text install pypdf or poppler.)\n', file=sys.stderr)
    pages = [(i + 1, text) for i, text in enumerate(rough)]
    return [(n, text) for n, text in pages if n >= first and (last is None or n <= last)]


def main():
    parser = argparse.ArgumentParser(description='Print the text of a PDF.')
    parser.add_argument('file')
    parser.add_argument('--pages', help='3, 2-5 or 4-  (default: all)')
    args = parser.parse_args()
    first, last = parse_pages(args.pages)
    try:
        open(args.file, 'rb').close()
    except OSError as error:
        sys.exit(f'Cannot open {args.file}: {error}')

    pages = extract_pages(args.file, first, last)
    if not pages:
        sys.exit('No pages in that range: the document is shorter.')
    if not any(text.strip() for _, text in pages):
        sys.exit('These pages have no text: the PDF is probably a scan. OCR it with ocrmypdf or tesseract if available.')
    for number, text in pages:
        print(f'--- Page {number} ---')
        print(text.strip())
        print()


if __name__ == '__main__':
    main()
