from .developer import SeniorDeveloper

class Migrator(SeniorDeveloper):
    """Translates source code from one language to another.
    Inherits all file-read/write logic from SeniorDeveloper; behavior
    is driven entirely by the migrator.md prompt."""
