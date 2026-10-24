#!/usr/bin/env python3
"""Line and word level text diff used by the *_diff.py scripts of this skill. Standard library only."""
import difflib
import re


def words(text):
    return re.findall(r'\s+|[^\s]+', text)


def inline(old, new):
    """One line showing a change inside a line: [-removed-]{+added+}."""
    out = []
    matcher = difflib.SequenceMatcher(None, words(old), words(new), autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == 'equal':
            out.append(''.join(words(old)[a1:a2]))
            continue
        if a2 > a1:
            out.append('[-' + ''.join(words(old)[a1:a2]).strip() + '-]')
        if b2 > b1:
            out.append('{+' + ''.join(words(new)[b1:b2]).strip() + '+}')
    return ''.join(out)


def diff_lines(old, new, context=1, limit=400):
    """Readable diff of two lists of lines. '-' removed, '+' added, '~' changed (shown word by word).

    Returns (lines, number of changed blocks). Output is cut at `limit` lines.
    """
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    out = []
    blocks = 0
    for group in matcher.get_grouped_opcodes(context):
        out.append(f'@@ line {group[0][1] + 1} (old) / {group[0][3] + 1} (new) @@')
        for tag, a1, a2, b1, b2 in group:
            if tag == 'equal':
                out.extend('  ' + line for line in old[a1:a2])
                continue
            blocks += 1
            if tag == 'replace' and a2 - a1 == b2 - b1:
                out.extend('~ ' + inline(old[a1 + i], new[b1 + i]) for i in range(a2 - a1))
            else:
                out.extend('- ' + line for line in old[a1:a2])
                out.extend('+ ' + line for line in new[b1:b2])
        if len(out) >= limit:
            out.append(f'... output cut at {limit} lines')
            break
    return out, blocks
