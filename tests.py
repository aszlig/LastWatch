#!/usr/bin/env python
import unittest
import lastwatch


class FilenameTest(unittest.TestCase):
    def parse_and_check(self, path, expected_result):
        parser = lastwatch.FilenameParser(path)
        self.assertEqual(parser.parse(), expected_result)

    def test_filename1(self):
        path = '/music/Moonspell/The Antidote/01. The Antidote.ogg'

        result = {
            'album': 'The Antidote',
            'title': 'The Antidote',
            'number': '01',
            'artist': 'Moonspell',
        }

        self.parse_and_check(path, result)

    def test_filename2(self):
        path = '/music/Linkin Park - A Thousand Suns (2010)/'
        path += '08. Linkin Park - Waiting for the End.ogg'

        result = {
            'album': 'A Thousand Suns',
            'title': 'Waiting for the End',
            'number': '08',
            'artist': 'Linkin Park',
        }

        self.parse_and_check(path, result)


if __name__ == '__main__':
    unittest.main()
