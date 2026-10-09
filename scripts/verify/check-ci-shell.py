#!/usr/bin/env python3
import pathlib
import re
import subprocess

NAMES = {'.bashrc', 'bashrc', '.bash_aliases', '.bash_completion', '.bash_login',
         '.bash_logout', '.bash_profile', 'bash_profile', 'suid_profile',
         '.zlogin', 'zlogin', '.zlogout', 'zlogout', '.zprofile', 'zprofile',
         '.zsenv', 'zsenv', '.zshrc', 'zshrc', '.profile', 'profile'}
SUFFIXES = {'.bash', '.ksh', '.zsh', '.sh', '.shlib'}
SHEBANG = re.compile(rb'^#! */[^ ]*/(env *)?[abk]*sh')


def shell_files(root):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file() or '.git' in path.parts or path.name == 'mvnw':
            continue
        if path.suffix in SUFFIXES or path.name in NAMES:
            files.append(path)
        elif '.' not in path.name and path.stat().st_mode & 0o111:
            with path.open('rb') as source:
                if SHEBANG.match(source.readline(4096)):
                    files.append(path)
    return files


def main():
    files = shell_files(pathlib.Path('scripts'))
    if not files:
        raise ValueError('No hay scripts para ShellCheck.')
    status = 0
    for path in files:
        result = subprocess.run(['shellcheck', '--format=gcc', str(path)], check=False)
        if result.returncode:
            status = result.returncode
    print(f'ci_shell_files={len(files)}')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
