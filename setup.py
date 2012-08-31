#!/usr/bin/env python
import sys
import subprocess
from distutils.core import setup, Command


class Test(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call([sys.executable, 'tests.py'])
        raise SystemExit(errno)


setup(
    name='LastWatch',
    version='0.4.0',
    description='Inotify scrobbler for last.fm',
    author='aszlig',
    author_email='"^[0-9]+$"@redmoonstudios.de',
    url='https://redmoonstudios.org/~aszlig/lastfm/',
    py_modules = ['lastwatch'],
    scripts=['bin/lastwatch'],
    requires=['pyinotify', 'pylast', 'mutagen'],
    cmdclass={'test': Test},
)
