#!/usr/bin/env python
# This is LastWatch, a last.fm scrobbler which uses inotify to detect
# the songs played by the audio player of your choice :-)
#
# Copyright (c) 2008 aszlig <"^[0-9]+$"@redmoonstudios.de>
#
# LastWatch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# LastWatch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with LastWatch. If not, see <http://www.gnu.org/licenses/>.

LASTWATCH_VERSION = "0.3.1"

import sys
import time
import os
import signal

from gettext import gettext as _

from textwrap import wrap

from optparse import OptionParser

from pyinotify import ThreadedNotifier, WatchManager, EventsCodes, ProcessEvent
from lastfm import client as lfmclient, marshaller, repr

from mutagen import File as MutagenFile

import re

RE_FORMAT = re.compile('(?<!%)%(?P<mod>[a-zA-Z])|([^%]+)|(?P<esc>%%)')

class Settings(object):
	DEBUG = False

class FilenameParser(object):
	match_all = r'.*'
	match_name = r'\d*(?:\D+\d*)+'
	match_num = r'\d{1,3}'

	ftable = {
		'a': (match_name, 'artist', _("Artist")),
		'A': (match_name, 'album',  _("Album")),
		't': (match_name, 'title',  _("Song title")),
		'n': (match_num,  'number', _("Track number")),
		'i': (match_all,  'ignore', _("Ignore this value")),
	}

	def __init__(self, filename):
		self.filename = os.path.abspath(filename)

	def make_node(self, farg):
		"""
		Creates a node which is a tuple consisting of (type, content)
		and adds named groups to the regular expressions for numeric
		and string data types.
		"""
		modifier = farg.group('mod')

		if farg.group('esc'):
			self.node_groups.append(('plain', '%'))
		elif not modifier:
			self.node_groups.append(('plain', farg.group()))
		elif modifier in self.ftable:
			opts = self.ftable[modifier]
			if opts[1] == 'ignore':
				append = r'\s*%s\s*' % opts[0]
			else:
				append = r'\s*(?P<%s>%s)\s*' % (opts[1], opts[0])
			self.node_groups.append(('re', append))
		else:
			raise ValueError, _("Modifier not found: %%%s") % modifier

	def merge_nodes(self):
		new_nodegroups = []
		last_type = None
		for node in self.node_groups:
			if last_type and last_type[0] == node[0]:
				last_type = (last_type[0], last_type[1] + node[1])
				continue
			elif last_type:
				new_nodegroups.append(last_type)

			last_type = node

		new_nodegroups.append(last_type)

		self.node_groups = new_nodegroups

	def match_re_plain(self, node, regex):
		"""
		Match <regex><plain>...more...
		"""
		found = self._filename.lower().find(node[1])
		if found == -1:
			errmsg  = _("Couldn't find next plain token (%(token)r) "
				    "after regex %(regex)r on %(text)r.")
			errmsg %= {'token': node[1], 'regex': regex,
				   'text': self._filename}
			raise LookupError, errmsg

		to_match, self._filename = self._filename[:found], self._filename[found+len(node[1]):]

		match = re.match(regex, to_match)
		if match:
			self.matches.append(match)
		else:
			errmsg  = _("The regex %(regex)r did not match on %(text)r.")
			errmsg %= {'regex': regex, 'text': to_match}
			raise LookupError, errmsg

	def match_plain(self, node):
		"""
		Match <plain>...more...
		"""
		if not self._filename.lower().startswith(node[1]):
			errmsg  = _("Unfortunately, %(text)r did not start with %(token)r.")
			errmsg %= {'text': self._filename, 'token': node[1]}
			raise LookupError, errmsg
		self._filename = self._filename[len(node[1]):]

	def prepare_filename(self, format):
		"""
		Cut the pathname to the last path segments we're trying to
		match and strip off the extension.
		"""
		filename = os.path.splitext(self.filename)[0]
		format_depth = format.count('/')

		if format_depth == 0:
			new_path = os.path.basename(filename)
		else:
			head, tail = os.path.split(filename)
			new_path = tail
			for x in range(0, format_depth):
				head, tail = os.path.split(head)
				new_path = os.path.join(tail, new_path)

		self._filename = new_path

	def parse(self, format="%n. %t %% htuoheu %a"):
		"""
		Tries to match a format string on the current filename.
		See self.ftable for a list of modifiers.

		Parsing is done by tokenizing the format string into plaintext
		nodes and regular expression nodes which will be merged and
		matched one after one.
		"""
		self.node_groups = []
		self.matches = []

		format = format.lstrip('/')
		self.prepare_filename(format)
		format = format.replace('/', os.path.sep)

		RE_FORMAT.sub(self.make_node, format)
		self.merge_nodes()

		re_buffer = r''

		for node in self.node_groups:
			if node[0] == 're':
				re_buffer += node[1]
			elif node[0] == 'plain' and re_buffer:
				self.match_re_plain(node, r'^%s$' % re_buffer)
				re_buffer = r''
			elif node[0] == 'plain' and not re_buffer:
				self.match_plain(node)
			else:
				errmsg = _("Node is neither 'plain' nor 're', "
				           "which is really weird O_o")
				raise LookupError, errmsg

		# last ...<regex> to parse
		if re_buffer:
			match = re.match(r'^%s$' % re_buffer, self._filename)
			if match:
				self.matches.append(match)
			else:
				errmsg  = _("Whoops, we can't match the last "
				            "regex %(regex)r on %(text)r")
				errmsg %= {'regex': re_buffer, 'text': self._filename}
				raise LookupError, errmsg

		def mergedicts(x, y):
			x.update(y.groupdict())
			return x

		results = reduce(mergedicts, self.matches, {})

		# sanitize
		for result in results:
			item = results[result]
			if item.isdigit(): item = int(item)
			else: item = item.replace('_', ' ')

		return results

	def try_formats(self):
		"""
		Tries several format strings on the current filename and return
		the first one matching, otherwise raise a LookupError.
		"""
		formats = (
			'%a/%A - %i/%n %i - [%i] %t (%i kbps)',
			'%a - %i - %A/  - %i - %n %t',
			'%n - %a - %t',
			'%a/%A/%i_%n_%t',
			'%a_-_%A_-_%t',
			'%a_-_%n_-_%t',
			'%a_-_%t',
			'%a - %A - %t',
			'%a - %n - %t',
			'%a - %t',
			'%a/%A/%n. %t',
			'%a - %i - %A/%i - %i - %n %t',
			'%a - %i - %A/%i - %t',
			'%a/%n_-_%t_-_%A',
			'%a/%n_-_%A_-_%t',
			'%n-%a-%t',
			'%a - %i - %A/%n - %t',
			'%a-%t',
			'%a - %i - %A/%n %t',
			'%a/%A/%t',
		)

		for check in formats:
			try:
				return self.parse(format=check)
			except LookupError:
				pass

		errmsg  = _("Couldn't find any title information based "
		            "on the path of %(file)r.")
		errmsg %= {'file': self.filename}
		raise LookupError, errmsg

class TitleNotFound(Exception):
	pass

class Songinfo(dict):
	TAG_TRANSLATE = {
		'title': ('TIT2',),
		'artist': ('TPE1', 'TPE2',),
		'album': ('TALB',),
	}

	def __init__(self, filename):
		self._filename = filename
		self._match = None
		dict.__init__(self)

	def fetch_info(self, optional=('album',)):
		"""
		Check the file type and call the corresponding method to get
		title info :-)
		"""
		self._audio = MutagenFile(self._filename)

		required = ('artist', 'title')

		info = {
			'length': self._audio.info.length and int(self._audio.info.length) or 0,
		}

		for tag in required + optional:
			try:
				info[tag] = self.get_taginfo(tag)
			except TitleNotFound:
				if tag in optional:
					continue
				raise

		self.update(info)

	def get_alternative_tag(self, tags):
		for tag in tags:
			item = self._audio.get(tag, None)
			if item and type(item) == type([]):
				return item[0]
			elif item:
				return item

		return None

	def get_from_fname(self, what):
		if self._match is not None:
			match = self._match
		else:
			try:
				parser = FilenameParser(self._filename)
				match = parser.try_formats()
			except LookupError:
				raise TitleNotFound, self._filename

		if match:
			self._match = match
			try:
				return match[what]
			except KeyError:
				pass

		raise TitleNotFound, self._filename

	def get_taginfo(self, what):
		item = self._audio.get(what, None)
		if item and type(item) == type([]):
			return item[0]
		elif not item and what in self.TAG_TRANSLATE:
			item = self.get_alternative_tag(self.TAG_TRANSLATE[what])
			if item: return item
		elif item:
			return item
		else:
			item = self.get_from_fname(what)
			if item: return item

		raise TitleNotFound, self._filename

def to_lastfm(filename, runtime, dry_run=False):
	"""
	Check if we meet the conditions and submit the song info to last.fm.
	"""
	try:
		song = Songinfo(filename)
		song.fetch_info()
	except TitleNotFound, e:
		print "Title for %s not found!" % e
		return

	lfm = lfmclient.Client('lastwatch')

	if song['length'] <= 30:
		return

	if not (runtime >= 240 or song['length'] * 50 / 100 <= runtime):
		return

	try:
		lfmsong = lastfm.repr(song)
	except:
		lfmsong = filename

	if dry_run:
		print _("Would submit %s to last.fm with a total runtime of %d seconds.") % (lfmsong, runtime)
	else:
		print _("Will submit %s to last.fm with a total runtime of %d seconds.") % (lfmsong, runtime)

		song['time'] = time.gmtime()
		lfm.submit(song)

class Music(object):
	def __init__(self, dry_run=False):
		self._running = {}
		self._dry_run = dry_run

	def gc(self, current, rotate=3): # FIXME: what if rotate is 1 or 0?
		"""
		Garbage collector - will ensure that the maintained file
		dictionary doesn't start to grow to the size of an entire
		planetary system :-D
		"""
		if len(self._running) < rotate:
			return

		for fn, st in self._running.iteritems():
			if fn == current:
				continue

			if st == 'delete' or st < self._running.get(current, 0):
				if Settings.DEBUG:
					print "GC: " + _("Removing %s") % fn
				del self._running[fn]
			else:
				continue

			return self.gc(current, rotate)

	def start(self, filename):
		if self._running.has_key(filename) and self._running[filename] == 'munge':
			self._running[filename] = 'delete'
			return

		self.gc(filename)

		self._running[filename] = time.time()
		print _("Started %s!") % filename

	def stop(self, filename):
		if not self._running.has_key(filename):
			return

		if self._running[filename] in ('delete', 'munge'):
			return

		start_time = self._running[filename]
		runtime = time.time() - start_time

		if runtime <= 30:
			if Settings.DEBUG:
				print _("File %s discarded!") % filename
			del self._running[filename]
			return

		to_lastfm(filename, runtime, dry_run=self._dry_run)
		self._running[filename] = 'munge'
		print _("Stopped %s!") % filename

class Handler(ProcessEvent):
	def __init__(self, dry_run=False):
		self._active = False
		self._music = Music(dry_run=dry_run)

	def set_active(self):
		self._active = True

	def process_default(self, event_k):
		if not self._active:
			return

		if Settings.DEBUG:
			print _("Untrapped event: %s") % event_k

	def allowed_file(self, event_k):
		"""
		We can only handle OGG, MP3 and FLAC files, so we'll check if
		the suffix matches in the data we got back from inotify =)
		"""

		suffix = os.path.splitext(event_k.name)[1][1:].lower()

		if suffix in ('ogg', 'mp3', 'flac'):
			return True

		return False

	def process_IN_OPEN(self, event_k):
		if self._active and self.allowed_file(event_k):
			self._music.start(os.path.join(event_k.path, event_k.name))

	def process_IN_CLOSE_NOWRITE(self, event_k):
		if self._active and self.allowed_file(event_k):
			self._music.stop(os.path.join(event_k.path, event_k.name))

def lastwatch(paths, dry_run=False):
	flags = EventsCodes.FLAG_COLLECTIONS.get('OP_FLAGS', None)
	if flags:
		mask = flags.get('IN_OPEN') | flags.get('IN_CLOSE_NOWRITE')
	else:
		mask = EventsCodes.IN_OPEN | EventsCodes.IN_CLOSE_NOWRITE

	wm = WatchManager()

	handler = Handler(dry_run=dry_run)

	watcher = ThreadedNotifier(wm, handler)
	watcher.start()

	try:
		for path in paths:
			path = os.path.realpath(path)

			sys.stdout.write(_("Indexing %s for watching...") % path)
			sys.stdout.flush()

			wm.add_watch(path, mask, rec=True)
			sys.stdout.write(_(" done.")+"\n")

		print _("You have successfully launched Lastwatch.")
		print "\n".join(wrap(_("The directories you have specified will be monitored as "
		                       "long as this process is running, the flowers are blooming "
		                       "and the earth revolves around the sun..."), 80))
		                       # flowers to devhell ;-)
		handler.set_active()

		while True:
			time.sleep(1)

	except KeyboardInterrupt:
		watcher.stop()
		print _("LastWatch stopped.")
		return
	except Exception, err:
		print err

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
	"""
	Fork the current process and redirect all file descriptors
	to the appropriate devices or files (default is /dev/null).
	"""
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0)
	except OSError, err:
		sys.stderr.write(_("We cannot escape into the background: %s") % err.strerror + "\n")
		sys.exit(1)

	# flush the standard output queue
	for f in sys.stdout, sys.stderr:
		f.flush()

	si = file(stdin, 'r')
	so = file(stdout, 'a+')
	se = file(stderr, 'a+', 0)

	# redirect them all to /dev/null (or any other file/device)
	os.dup2(si.fileno(), sys.stdin.fileno())
	os.dup2(so.fileno(), sys.stdout.fileno())
	os.dup2(se.fileno(), sys.stderr.fileno())

def suicide(signum, frame):
	watcher.stop()
	sys.exit(0)

class LWOpts(OptionParser):
	def __init__(self):
		usage = _("Usage: %prog [options] directories...")
		version = _("%%prog version %s") % LASTWATCH_VERSION

		OptionParser.__init__(self, usage=usage, version=version)

		self.add_option("-v", "--verbose",
			action="store_true", dest="verbose", default=False,
			help=_("Be verbose about what's happening (especially "
			       "about the garbage collector)."))

		self.add_option("-n", "--dry-run",
			action="store_true", dest="dryrun", default=False,
			help=_("Do not submit any titles to last.fm."))

		self.add_option("-b", "--background",
			action="store_true", dest="detach", default=False,
			help=_("Fork into the background."))

		# TODO: configuration file
		#self.add_option("-c", "--config", metavar="FILE",
		#	dest="cfgfile", default="~/.lastwatch/config",
		#	help=_("Specify configuration file at FILE instead of "
		#	       "the default location at \"%default\"."))

def main():
	parser = LWOpts()
	options, args = parser.parse_args()

	if len(args) < 1:
		parser.error(_("No directories specified!"))

	if options.detach:
		daemonize()
		signal.signal(signal.SIGINT, suicide)

	if options.verbose:
		Settings.DEBUG = True

	if options.dryrun:
		lastwatch(args, dry_run=True)
	else:
		lastwatch(args)

if __name__ == "__main__":
	main()
