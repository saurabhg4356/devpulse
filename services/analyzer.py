"""Base Analyzer abstract class demonstrating OOP inheritance and polymorphic analysis."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Analyzer(ABC):
    """Abstract base class establishing the contract for all domain analyzers.
    
    Demonstrates OOP:
    - Abstraction: Defines the abstract template `analyze()` method.
    - Polymorphism: Derived classes (RepositoryAnalyzer, CommitAnalyzer, FileAnalyzer)
      implement different analysis logic across identical calling signatures.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def analyze(self, target: Any) -> Dict[str, Any]:
        """Execute domain-specific analysis.
        
        Args:
            target: Input data (e.g., repository metadata, commits list, file stats).
            
        Returns:
            Dictionary containing structured analysis results.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
