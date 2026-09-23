"""
BrisartOS Settings Service
Pure Python.
No dependencies.
"""


class SettingsService:

    def __init__(self):
        self.version = "0.1.0"

    def status(self):
        return "Settings Service Online"