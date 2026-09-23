"""
BrisartOS Version
Single source of truth for the BrisartOS version string.
Pure Python. No dependencies.
"""
NAME = "BrisartOS"
VERSION = "0.10.0-alpha"


def version_text():
    return f"{NAME} {VERSION}"


if __name__ == "__main__":
    print(version_text())
