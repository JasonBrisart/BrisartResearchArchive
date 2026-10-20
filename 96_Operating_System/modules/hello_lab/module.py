r"""
File: modules/hello_lab/module.py

Purpose
-------
Demonstrate four module permissions by generating an identifier, writing
hello.txt, updating one setting and recording a log message.

Public interface:
- run(api) -- The module entry point: use the four declared permissions and
  return a summary line.

Design notes:

run uses object_id, storage, service:settings and log in that order, then
returns a summary. Each run replaces hello.txt and the last-id setting. The
entry does not call every ModuleAPI method; it demonstrates only the four
operations present in its body.

The shipped entry is loaded by path in
brisartos/modules/tests/test_registry.py. Its generated static-import coverage
line does not represent that integration test.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: none.
Imported by: no other module in this tree imports it directly.
Covered by tests: none directly.

Settings / parameters
---------------------
- MODULE_NAME = 'hello_lab' -- The name typed after run and describe.
- MODULE_DISPLAY_NAME = 'Hello Lab' -- Shown by the describe command as
  display_name.
- MODULE_VERSION = __version__ -- Read from version.py so the example reports
  the release version.
- MODULE_AUTHOR = 'Jason Brisart' -- Shown by the describe command.
- MODULE_DESCRIPTION = 'Uses each part of the module API once.' -- Shown by the
  describe command.
- MODULE_ABI = 'brisartos.module.v1' -- The compatibility string the registry
  requires.
- MODULE_PERMISSIONS = ('log', 'storage', 'object_id', 'service:settings') --
  The permissions the module needs; each is used once.

Edge cases
----------
A permission removed from MODULE_PERMISSIONS makes the call that needed it
raise AccessDenied, which the registry logs as a failed run.

Known limitations
-----------------
- It writes real files when the console uses disk storage, and its settings
  entry is lost when the program ends.
- It reads its version from the BrisartOS root-level version module.

Examples
--------
Run from the repository root.

::

    python -B run.py start --memory
    BrisartOS> run hello_lab
"""

from version import __version__

MODULE_NAME = "hello_lab"
MODULE_DISPLAY_NAME = "Hello Lab"
MODULE_VERSION = __version__
MODULE_AUTHOR = "Jason Brisart"
MODULE_DESCRIPTION = "Uses each part of the module API once."
MODULE_ABI = "brisartos.module.v1"
MODULE_PERMISSIONS = ("log", "storage", "object_id", "service:settings")


def run(api):
    object_id = api.new_object_id()
    path = api.write_text("hello.txt", "Hello from BrisartOS\nObject ID: " + object_id + "\n")
    api.get_service("settings").set("hello_lab.last_id", object_id)
    api.log("wrote " + path)
    return "hello_lab wrote " + path + " (object " + object_id + ")"
