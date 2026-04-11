from .qa_engineer import QAEngineer

class EquivalenceChecker(QAEngineer):
    """Verifies behavioral equivalence between source and migrated code.
    Inherits all sandbox/file-read logic from QAEngineer; behavior
    is driven entirely by the equivalence-checker.md prompt."""
