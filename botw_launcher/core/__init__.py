"""What the launcher does, without any window (see botw_launcher/__init__.py).

Functions here raise the exceptions of the tools they wrap, narrowed to
ValueError, OSError and RuntimeError (cemu_install.CemuInstallError is one):
the caller shows their message to the player as it is, so it must be a sentence
the player can act on.
"""
