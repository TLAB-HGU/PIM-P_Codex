#!/usr/bin/env python3
"""Check the standalone skill's metadata, local references and attribution."""
from pathlib import Path
import re
import sys
import yaml


def validate(root):
    skill = root / 'skills' / 'pimp'
    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    header = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not header:
        raise ValueError('SKILL.md needs YAML frontmatter')
    metadata = yaml.safe_load(header.group(1))
    if metadata.get('name') != 'pimp' or not isinstance(metadata.get('description'), str):
        raise ValueError('name:pimp and a description are required')
    if set(metadata) - {'name','description','license','metadata','allowed-tools'}:
        raise ValueError('unsupported frontmatter keys')
    if len(metadata['description']) > 1024 or not metadata['description'].strip():
        raise ValueError('description must be concise and nonempty')
    for markdown in [skill / 'SKILL.md', *sorted((skill / 'references').glob('*.md'))]:
        for target in re.findall(r'\]\(([^)]+)\)', markdown.read_text(encoding='utf-8')):
            if re.match(r'^[a-z]+://', target) or target.startswith('#'):
                continue
            if not (markdown.parent / target.split('#')[0]).exists():
                raise ValueError(f'{markdown.relative_to(root)}: missing reference {target}')
    if (skill / 'LICENSE').read_bytes() != (root / 'LICENSE').read_bytes():
        raise ValueError('standalone skill must preserve the full original LICENSE')
    if (skill / 'UPSTREAM.md').read_bytes() != (root / 'UPSTREAM.md').read_bytes():
        raise ValueError('standalone skill must preserve upstream attribution')
    ui = yaml.safe_load((skill / 'agents' / 'openai.yaml').read_text())
    if '$pimp' not in ui['interface']['default_prompt']:
        raise ValueError('default_prompt must mention $pimp')
    print('PASS: skill metadata, local references, UI metadata and MIT attribution')


if __name__ == '__main__':
    try:
        validate(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'FAIL: {e}', file=sys.stderr)
        sys.exit(1)
