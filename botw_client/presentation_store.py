"""Exclusive journal lifetime; atomic, flushed snapshots on a local filesystem.

Keep the sidecar lock file: unlinking it would allow two independent locks.
Use one canonical path, not hard-link aliases or network filesystems. Call the
queue serially; the lease excludes other store instances, not concurrent ticks.
"""
import json
import os
from pathlib import Path
import tempfile

from botw_client.presentation import PresentationQueue


class PresentationStore:
    def __init__(self, path, namespace, *, queue_type=PresentationQueue):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = None
        self.queue = None
        handle = open(str(self.path) + '.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock = handle
            snapshot = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None
            self.queue = queue_type(namespace, self.commit, snapshot)
            if snapshot is None:
                self.commit(self.queue.snapshot())
        except BaseException:
            handle.close()
            self.lock = None
            raise

    def commit(self, snapshot):
        if self.lock is None:
            raise RuntimeError('Presentation journal is closed')
        raw = (json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        fd, name = tempfile.mkstemp(prefix=self.path.name + '.', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            # Flush the replaced file too. A failure is fatal even if replace
            # already succeeded; the caller must not continue dispatching.
            with open(self.path, 'r+b') as stream:
                os.fsync(stream.fileno())
            if os.name != 'nt':
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None
        if self.queue is not None:
            self.queue.broken = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
