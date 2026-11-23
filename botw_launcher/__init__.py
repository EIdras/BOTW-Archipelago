"""The player's launcher: a window that prepares seeds, starts the game and
relays it with the Archipelago room.

    python botw_launcher/__main__.py [<slot file .apbotw | seed zip>] [--seed <name>]

The package is in three layers, each knowing only the ones above it in this list:

  core/       what the launcher does, without any window: seeds, the Cemu
              profile, rooms, storage, updates. Thin, typed wrappers over the
              project's tools (tools/play_seed.py, tools/cemu_profile.py...).
  jobs.py     the long tasks (a pack build, a play session, a download), each
              run in a child process that reports with one JSON line an event.
              A task that crashes or is cancelled never takes the window down.
  tk/         the window (tkinter: Archipelago's Python has it). It calls core/
              for what is immediate and starts jobs for the rest; nothing else of
              the project imports it. Inside Archipelago, botw_world/client opens it.

Around them: settings.py (what the player chose), logs.py (the log file and the
diagnostic archive), versions.py and handoff.py (versions installed side by
side by an update, and the newest one taking over at start).

To add a long task: write its function in jobs.py with @job. To add a page:
a Page in tk/pages/, added to tk/app.py MainWindow.
"""
