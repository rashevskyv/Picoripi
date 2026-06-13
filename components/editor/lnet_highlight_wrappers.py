class LNETHighlightWrappers:
    """L n e t highlight wrappers implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor
        self.hi = editor.highlight_interface

    def addCriticalProblemHighlight(self, line_number: int):
        """Addcriticalproblemhighlight."""
        self.hi.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        """Removecriticalproblemhighlight."""
        return self.hi.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        """Clearcriticalproblemhighlights."""
        self.hi.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        """Hascriticalproblemhighlight."""
        return self.hi.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        """Addwarninglinehighlight."""
        self.hi.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        """Removewarninglinehighlight."""
        return self.hi.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        """Clearwarninglinehighlights."""
        self.hi.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        """Haswarninglinehighlight."""
        return self.hi.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        """Addwidthexceededhighlight."""
        self.hi.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        """Removewidthexceededhighlight."""
        return self.hi.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        """Clearwidthexceededhighlights."""
        self.hi.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        """Haswidthexceededhighlight."""
        return self.hi.hasWidthExceededHighlight(line_number)
    
    def addShortLineHighlight(self, line_number: int):
        """Addshortlinehighlight."""
        self.hi.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        """Removeshortlinehighlight."""
        return self.hi.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        """Clearshortlinehighlights."""
        self.hi.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        """Hasshortlinehighlight."""
        return self.hi.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        """Addemptyoddsublinehighlight."""
        self.hi.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        """Removeemptyoddsublinehighlight."""
        return self.hi.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        """Clearemptyoddsublinehighlights."""
        self.hi.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        """Hasemptyoddsublinehighlight."""
        return self.hi.hasEmptyOddSublineHighlight(block_number)
