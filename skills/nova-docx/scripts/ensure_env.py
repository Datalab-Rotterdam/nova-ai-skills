#!/usr/bin/env python3
"""Make sure Python packages are installed in Nova's own virtual environment and print the path of its python.

Nova keeps one environment (~/.nova-ai/python-env, or $NOVA_AI_HOME/python-env) so packages never go into
the system Python (which many systems refuse to modify). Creating it and installing packages needs the
internet the first time; later runs only check.

usage: PY=$(python3 ensure_env.py openpyxl python-docx)  &&  "$PY" my_script.py
"""
import os
import subprocess
import sys
import venv


def env_python(env_dir):
    return os.path.join(env_dir, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(env_dir, 'bin', 'python')


def works(python):
    try:
        return subprocess.run([python, '-c', 'import pip'], capture_output=True).returncode == 0
    except OSError:
        return False


def missing_packages(python, packages):
    code = ('import importlib.metadata as m, sys\n'
            'for name in sys.argv[1:]:\n'
            '    try:\n        m.version(name)\n    except m.PackageNotFoundError:\n        print(name)\n')
    result = subprocess.run([python, '-c', code, *packages], capture_output=True, text=True)
    return result.stdout.split()


def main():
    packages = sys.argv[1:]
    home = os.environ.get('NOVA_AI_HOME') or os.path.join(os.path.expanduser('~'), '.nova-ai')
    env_dir = os.path.join(home, 'python-env')
    python = env_python(env_dir)
    if not works(python):
        print(f'Creating Nova\'s Python environment in {env_dir} ...', file=sys.stderr)
        try:
            venv.EnvBuilder(with_pip=True, clear=os.path.isdir(env_dir)).create(env_dir)
        except Exception as error:  # noqa: BLE001
            sys.exit(f'Could not create a virtual environment: {error}. On Debian/Ubuntu install python3-venv.')
    missing = missing_packages(python, packages) if packages else []
    if missing:
        print('Installing ' + ', '.join(missing) + ' ...', file=sys.stderr)
        result = subprocess.run([python, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', *missing],
                                stdout=sys.stderr, stderr=sys.stderr)
        if result.returncode != 0:
            sys.exit('pip could not install ' + ', '.join(missing) + ' (no internet or a proxy?). Tell the user.')
    print(python)


if __name__ == '__main__':
    main()
