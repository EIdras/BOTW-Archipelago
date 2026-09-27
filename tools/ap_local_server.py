"""Create a local AP 0.6.7 room for isolated integration tests."""
from __future__ import annotations

from MultiServer import Context


def make_context(archive):
    # MultiServer.Context deletes these two keys from the shared global
    # DataPackage in its constructor. Restore them when several rooms are
    # created in one Python test process; each actual launcher uses one room.
    import worlds

    for package in worlds.network_data_package["games"].values():
        package.setdefault("item_name_groups", {})
        package.setdefault("location_name_groups", {})
    context = Context("127.0.0.1", 0, "", "", 0, 0, False)
    context.load(str(archive))
    context.init_save(False)
    return context
