from PyQt5.QtGui import QTextBlock
from typing import Optional

class LNETHighlightInterface:
    def __init__(self, editor):
        self.editor = editor

    def _momentary_highlight_tag(self, block: QTextBlock, start_in_block: int, length: int):
        self.editor.highlightManager.momentaryHighlightTag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        self.editor.highlightManager.applyHighlights()

    def addCriticalProblemHighlight(self, line_number: int):
        self.editor.highlightManager.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        return self.editor.highlightManager.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        self.editor.highlightManager.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.editor.highlightManager.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        self.editor.highlightManager.addWarningLineHighlight(line_number)


    def removeWarningLineHighlight(self, line_number: int) -> bool:
        return self.editor.highlightManager.removeWarningLineHighlight(line_number)


    def clearWarningLineHighlights(self):
        self.editor.highlightManager.clearWarningLineHighlights()


    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.editor.highlightManager.hasWarningLineHighlight(line_number)


    def addWidthExceededHighlight(self, line_number: int):
        pass


    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        return False

    def clearWidthExceededHighlights(self):
        pass

    def hasWidthExceededHighlight(self, line_number: Optional[int] = None) -> bool:
        return False

    def addShortLineHighlight(self, line_number: int):
        pass

    def removeShortLineHighlight(self, line_number: int) -> bool:
        return False

    def clearShortLineHighlights(self):
        pass

    def hasShortLineHighlight(self, line_number: Optional[int] = None) -> bool:
        return False

    def addEmptyOddSublineHighlight(self, block_number: int):
        if hasattr(self.editor.highlightManager, 'addEmptyOddSublineHighlight'):
            self.editor.highlightManager.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        if hasattr(self.editor.highlightManager, 'removeEmptyOddSublineHighlight'):
            return self.editor.highlightManager.removeEmptyOddSublineHighlight(block_number)
        return False

    def clearEmptyOddSublineHighlights(self):
        if hasattr(self.editor.highlightManager, 'clearEmptyOddSublineHighlights'):
            self.editor.highlightManager.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number: Optional[int] = None) -> bool:
        if hasattr(self.editor.highlightManager, 'hasEmptyOddSublineHighlight'):
            return self.editor.highlightManager.hasEmptyOddSublineHighlight(block_number)
        return False

    def setPreviewSelectedLineHighlight(self, line_number: int):
        self.editor.highlightManager.setPreviewSelectedLineHighlight(line_number)

    def clearPreviewSelectedLineHighlight(self):
        self.editor.highlightManager.clearPreviewSelectedLineHighlight()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self.editor.highlightManager.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        self.editor.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        self.editor.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        self.clearAllProblemTypeHighlights()
        
    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.hasCriticalProblemHighlight(line_number)