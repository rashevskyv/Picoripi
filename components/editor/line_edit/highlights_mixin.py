"""Highlight add/remove/clear/has wrappers and related helpers."""
from __future__ import annotations


class HighlightsMixin:
    """Highlight add/remove/clear/has wrappers and related helpers."""

    def _momentary_highlight_tag(self, block, start_in_block, length):
        """Internal helper to momentary highlight tag."""
        self.highlight_interface._momentary_highlight_tag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        """Internal helper to apply all extra selections."""
        self.highlight_interface._apply_all_extra_selections()

    def addCriticalProblemHighlight(self, line_number: int):
        """Addcriticalproblemhighlight."""
        self.hi_wrappers.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        """Removecriticalproblemhighlight."""
        return self.hi_wrappers.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        """Clearcriticalproblemhighlights."""
        self.hi_wrappers.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        """Hascriticalproblemhighlight."""
        return self.hi_wrappers.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        """Addwarninglinehighlight."""
        self.hi_wrappers.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        """Removewarninglinehighlight."""
        return self.hi_wrappers.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        """Clearwarninglinehighlights."""
        self.hi_wrappers.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        """Haswarninglinehighlight."""
        return self.hi_wrappers.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        """Addwidthexceededhighlight."""
        self.hi_wrappers.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        """Removewidthexceededhighlight."""
        return self.hi_wrappers.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        """Clearwidthexceededhighlights."""
        self.hi_wrappers.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        """Haswidthexceededhighlight."""
        return self.hi_wrappers.hasWidthExceededHighlight(line_number)

    def addShortLineHighlight(self, line_number: int):
        """Addshortlinehighlight."""
        self.hi_wrappers.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        """Removeshortlinehighlight."""
        return self.hi_wrappers.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        """Clearshortlinehighlights."""
        self.hi_wrappers.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        """Hasshortlinehighlight."""
        return self.hi_wrappers.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        """Addemptyoddsublinehighlight."""
        self.hi_wrappers.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        """Removeemptyoddsublinehighlight."""
        return self.hi_wrappers.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        """Clearemptyoddsublinehighlights."""
        self.hi_wrappers.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        """Hasemptyoddsublinehighlight."""
        return self.hi_wrappers.hasEmptyOddSublineHighlight(block_number)

    def clearPreviewSelectedLineHighlight(self):
        """Clearpreviewselectedlinehighlight."""
        self.highlightManager.set_background_for_lines(set(), self._previously_selected_lines)
        self.clear_selection()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        """Setlinkedcursorposition."""
        self.hi_wrappers.hi.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        """Applyqueuedhighlights."""
        self.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        """Clearallproblemtypehighlights."""
        self.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        """Addproblemlinehighlight."""
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        """Removeproblemlinehighlight."""
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        """Clearproblemlinehighlights."""
        self.clearAllProblemTypeHighlights()

    def hasProblemHighlight(self, line_number = None) -> bool:
        """Hasproblemhighlight."""
        return self.hasCriticalProblemHighlight(line_number)
