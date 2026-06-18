from .models import ProblemMatch, FixResult
from .context import RuleContext, GameProblemProfile
from .base import ProblemRule
from .registry import ProblemRuleRegistry
from .common_rules import (
    WidthRule,
    BadSpacingRule,
    MissingIconSpacingRule,
    ShortLineRule,
    SingleWordSublineRule,
    EmptyFirstLineOfPageRule,
    EmptyOddSublineDisplayRule,
    BrokenIconHyphenRule,
    TagWarningRule,
    StarTagRule
)

def create_default_registry(profile: GameProblemProfile) -> ProblemRuleRegistry:
    """
    Creates a ProblemRuleRegistry populated with all default common rules, 
    and BMG-specific StarTagRule if BMG profile is active.
    """
    rules = [
        WidthRule(),
        BadSpacingRule(),
        MissingIconSpacingRule(),
        ShortLineRule(),
        SingleWordSublineRule(),
        EmptyFirstLineOfPageRule(),
        EmptyOddSublineDisplayRule(),
        BrokenIconHyphenRule(),
        TagWarningRule()
    ]
    if profile.star_section_mode:
        rules.append(StarTagRule())
        
    return ProblemRuleRegistry(profile, rules)
