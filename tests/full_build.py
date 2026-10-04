"""The tests that build a whole pack from the game's files: minutes, not seconds.

They run with BOTW_FULL_TESTS=1 (`run-tests.cmd full`), and must before a commit
that changes what a pack holds (botw_patch/, tools/build_*, native/, data/item_map.json):
their pins are what catches an unintended change. GitHub's runner has no game
files: it skips them either way.
"""
import os
import unittest

FULL = os.environ.get("BOTW_FULL_TESTS") == "1"
full_build = unittest.skipUnless(FULL, "builds a whole pack: run with BOTW_FULL_TESTS=1 (run-tests.cmd full)")
