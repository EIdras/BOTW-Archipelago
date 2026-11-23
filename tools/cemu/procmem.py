"""The process memory backend of this platform: winmem on Windows, linuxmem elsewhere.

Imported flat, as mailbox.py does (sys.path holds tools/cemu), so that both
backends stay plain modules of the tools.cemu namespace and neither is loaded
on the other platform.
"""
import sys

if sys.platform == "win32":
    from winmem import Process
else:
    from linuxmem import Process

__all__ = ["Process"]
