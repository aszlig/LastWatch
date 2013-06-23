Introduction
============

LastWatch is a Last.fm scrobbler that fetches song information by using the
inotify feature of the Linux kernel, version 2.6. You can use any OGG, MP3 or
FLAC player to scrobble, as long as it doesn't use mmap(). The latter will be
fixed in some future version.

Requirements
============

In order to run LastWatch, you need Python (at least 2.3) and the following
packages:

- [pylast](http://code.google.com/p/pylast/): at least version 0.5.0
- [pyinotify](http://pyinotify.sourceforge.net/): at least version 0.6.0
- [Mutagen](http://www.sacredchao.net/quodlibet/wiki/Development/Mutagen)

... and as already noted: Linux kernel v2.6 and higher (at least 2.6.13)

Using LastWatch
===============

Try invoking `./lastwatch.py --help` to get an overview about the available
options. For example if you want to watch the directory /media/music you could
just invoke:

```
./lastwatch.py /media/music
```

So far, that's all about using LastWatch. Have fun =)
