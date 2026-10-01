#!/usr/bin/env python3
"""Check the standalone skill's metadata, local references and attribution."""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import yaml


def validate(root, distribution=False):
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
    upstream = (skill / 'UPSTREAM.md').read_text(encoding='utf-8')
    if 'https://github.com/TLAB-HGU/PIM-P' not in upstream or '68e5b295b271ae55ddd85055914ac5aa4532b522' not in upstream:
        raise ValueError('standalone skill must preserve upstream attribution and baseline')
    if (root / 'UPSTREAM.md').exists() and (skill / 'UPSTREAM.md').read_bytes() != (root / 'UPSTREAM.md').read_bytes():
        raise ValueError('duplicate upstream attribution must match the standalone skill')
    ui = yaml.safe_load((skill / 'agents' / 'openai.yaml').read_text())
    if '$pimp' not in ui['interface']['default_prompt']:
        raise ValueError('default_prompt must mention $pimp')
    if distribution:
        tracked = subprocess.run(['git', 'ls-files'], cwd=root, text=True, capture_output=True, check=True).stdout.splitlines()
        allowed = {'.github/workflows/tests.yml', '.gitignore', 'LICENSE', 'README.md'}
        extra = [path for path in tracked if path not in allowed and not path.startswith('skills/pimp/')]
        if extra:
            raise ValueError(f'non-distribution files in main: {extra}')
        for target in re.findall(r'\]\(([^)]+)\)', (root / 'README.md').read_text(encoding='utf-8')):
            if not re.match(r'^[a-z]+://', target) and not target.startswith('#') and not (root / target.split('#')[0]).exists():
                raise ValueError(f'README.md: missing reference {target}')
    print('PASS: skill metadata, local references, UI metadata and MIT attribution')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', action='store_true', help='Also require the minimal main distribution tree')
    args = parser.parse_args()
    try:
        validate(Path(__file__).resolve().parents[1], args.distribution)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'FAIL: {e}', file=sys.stderr)
        sys.exit(1)
