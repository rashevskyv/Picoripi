from PyQt6.QtGui import QTextBlock
from typing import Optional

class LNETHighlightInterface:
    """L n e t highlight interface implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def _momentary_highlight_tag(self, block: QTextBlock, start_in_block: int, length: int):
        """Internal helper to momentary highlight tag."""
        self.editor.highlightManager.momentaryHighlightTag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        """Internal helper to apply all extra selections."""
        self.editor.highlightManager.applyHighlights()

    def addCriticalProblemHighlight(self, line_number: int):
        """Addcriticalproblemhighlight."""
        self.editor.highlightManager.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        """Removecriticalproblemhighlight."""
        return self.editor.highlightManager.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        """Clearcriticalproblemhighlights."""
        self.editor.highlightManager.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        """Hascriticalproblemhighlight."""
        return self.editor.highlightManager.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        """Addwarninglinehighlight."""
        self.editor.highlightManager.addWarningLineHighlight(line_number)


    def removeWarningLineHighlight(self, line_number: int) -> bool:
        """Removewarninglinehighlight."""
        return self.editor.highlightManager.removeWarningLineHighlight(line_number)


    def clearWarningLineHighlights(self):
        """Clearwarninglinehighlights."""
        self.editor.highlightManager.clearWarningLineHighlights()


    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        """Haswarninglinehighlight."""
        return self.editor.highlightManager.hasWarningLineHighlight(line_number)


    def addWidthExceededHighlight(self, line_number: int):
        """Addwidthexceededhighlight."""
        pass


    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        """Removewidthexceededhighlight."""
        return False

    def clearWidthExceededHighlights(self):
        """Clearwidthexceededhighlights."""
        pass

    def hasWidthExceededHighlight(self, line_number: Optional[int] = None) -> bool:
        """Haswidthexceededhighlight."""
        return False

    def addShortLineHighlight(self, line_number: int):
        """Addshortlinehighlight."""
        pass

    def removeShortLineHighlight(self, line_number: int) -> bool:
        """Removeshortlinehighlight."""
        return False

    def clearShortLineHighlights(self):
        """Clearshortlinehighlights."""
        pass

    def hasShortLineHighlight(self, line_number: Optional[int] = None) -> bool:
        """Hasshortlinehighlight."""
        return False

    def addEmptyOddSublineHighlight(self, block_number: int):
        """Addemptyoddsublinehighlight."""
        if hasattr(self.editor.highlightManager, 'addEmptyOddSublineHighlight'):
            self.editor.highlightManager.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        """Removeemptyoddsublinehighlight."""
        if hasattr(self.editor.highlightManager, 'removeEmptyOddSublineHighlight'):
            return self.editor.highlightManager.removeEmptyOddSublineHighlight(block_number)
        return False

    def clearEmptyOddSublineHighlights(self):
        """Clearemptyoddsublinehighlights."""
        if hasattr(self.editor.highlightManager, 'clearEmptyOddSublineHighlights'):
            self.editor.highlightManager.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number: Optional[int] = None) -> bool:
        """Hasemptyoddsublinehighlight."""
        if hasattr(self.editor.highlightManager, 'hasEmptyOddSublineHighlight'):
            return self.editor.highlightManager.hasEmptyOddSublineHighlight(block_number)
        return False

    def setPreviewSelectedLineHighlight(self, line_number: int):
        """Setpreviewselectedlinehighlight."""
        self.editor.highlightManager.setPreviewSelectedLineHighlight(line_number)

    def clearPreviewSelectedLineHighlight(self):
        """Clearpreviewselectedlinehighlight."""
        self.editor.highlightManager.clearPreviewSelectedLineHighlight()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        """Setlinkedcursorposition."""
        self.editor.highlightManager.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        """Applyqueuedhighlights."""
        self.editor.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        """Clearallproblemtypehighlights."""
        self.editor.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        """Addproblemlinehighlight."""
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        """Removeproblemlinehighlight."""
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        """Clearproblemlinehighlights."""
        self.clearAllProblemTypeHighlights()
        
    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        """Hasproblemhighlight."""
        return self.hasCriticalProblemHighlight(line_number)