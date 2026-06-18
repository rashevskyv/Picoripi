from abc import ABC, abstractmethod
from typing import List
from .models import ProblemMatch, FixResult
from .context import RuleContext

class ProblemRule(ABC):
    """
    Abstract base class for all translation validation/fixing rules.
    """
    @property
    @abstractmethod
    def id(self) -> str:
        """
        The unique ID of the problem (e.g. 'WIDTH_EXCEEDED').
        Note that this is a logical ID, not prefixed with game code.
        """
        pass

    @property
    def metadata(self) -> dict:
        """
        Metadata containing name, short_name, description, severity, priority.
        """
        return {}

    @abstractmethod
    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        """
        Scan text and return any matches.
        """
        pass

    @abstractmethod
    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        """
        Fix matches and return the modified text and set of fixed problem IDs.
        """
        pass
