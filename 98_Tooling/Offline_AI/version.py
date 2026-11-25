r"""
File: version.py

Purpose
-------
Declare the BrisartAI release version.

Communication / relationships
-----------------------------
version_info.py loads this file by path.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Settings / parameters
---------------------
Update __version__ together with release documentation.

This file has no independently configurable runtime parameters. The values it exports
are consumed by its owner rather than loaded from another settings file.

The single exported __version__ value is 1.4.0. Changing this string alone does not establish a tested release or migrate the index.

Edge cases
----------
version_info.py owns the fallback when loading fails.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
The constant neither migrates user data nor installs updates.

Examples
--------
__version__ = "1.4.0"
"""
__version__ = "1.4.0"
