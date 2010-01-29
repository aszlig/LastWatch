#!/usr/bin/env python
import doctest
from lastwatch import Songinfo

__test__ = {'SONGINFO': """
>>> Songinfo('/blah/foo/Moonspell/The Antidote/01. The Antidote.ogg').get_from_fname('title')
'The Antidote'
>>> Songinfo('/blah/foo/Moonspell - The Antidote.ogg').get_from_fname('artist')
'Moonspell'
>>> foo = Songinfo('/blah/foo/Moonspell - The Antidote - Blah (foo bar).ogg')
>>> foo.get_from_fname('title')
'Blah (foo bar)'
>>> foo.get_from_fname('album')
'The Antidote'
""", 'RECURSE_SONGINFO': """
>>> import os
>>> for root, dirs, files in os.walk('/home/aszlig/music'):
...     results = [os.path.join(root, f) for f in files]
...     for r in results:
...         if os.path.splitext(r)[1][1:].lower() not in ('mp3', 'ogg', 'flac'): continue
...         foo = Songinfo(r)
...         assert {'artist': foo.get_from_fname('artist')}
...         assert {'title': foo.get_from_fname('title')}
>>>
"""}

if __name__ == '__main__':
	doctest.testmod()
