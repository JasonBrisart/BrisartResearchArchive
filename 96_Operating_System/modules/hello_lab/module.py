"""
File: modules/hello_lab/module.py

Purpose
-------
Hello Lab Module
Pure Python.
No dependencies.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
Module-level named settings: MODULE_NAME, MODULE_DISPLAY_NAME, MODULE_VERSION, MODULE_AUTHOR, MODULE_DESCRIPTION, MODULE_ABI, MODULE_PERMISSIONS. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.
"""

MODULE_NAME = "hello_lab"
MODULE_DISPLAY_NAME = "Hello Lab Module"
MODULE_VERSION = "0.2.0"
MODULE_AUTHOR = "Jason Brisart"
MODULE_DESCRIPTION = (
    "Demonstration module for "
    "BrisartOS modular runtime."
)
MODULE_ABI = (
    "brisartos.module.v1"
)
MODULE_PERMISSIONS = (
    "log",
    "module_data",
    "object_id",
    "service:filesystem",
)
def run(api):
    print()
    print("===================")
    print(" HELLO LAB MODULE")
    print("===================")
    print()
    object_id = (
        api.new_object_id()
    )
    print(
        "Generated Object ID:"
    )
    print(object_id)
    api.write_module_text(
        "hello_lab",
        "hello.txt",
        (
            "Hello from "
            "BrisartOS\n"
            f"Object ID: "
            f"{object_id}\n"
        )
    )
    api.log(
        "hello_lab",
        "module executed"
    )
    print()
    print(
        "File written "
        "successfully."
    )
    fs = api.get_service("filesystem")
    fs.write_text(
        MODULE_NAME,
        "service_demo.txt",
        (
            "Written through the "
            "filesystem service.\n"
            f"Object ID: {object_id}\n"
        )
    )
    print()
    print("Filesystem service files:")
    for name in fs.list_files(MODULE_NAME):
        print(f" - {name}")
    print()
