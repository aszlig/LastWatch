#!/usr/bin/env python
from distutils.core import setup, Command


setup(
    name='LastWatch',
    version='0.3.1',
    description='Inotify scrobbler for last.fm',
    author='aszlig',
    author_email='"^[0-9]+$"@redmoonstudios.de',
    url='https://redmoonstudios.org/~aszlig/lastfm/',
    scripts=['bin/lastwatch'],
)
