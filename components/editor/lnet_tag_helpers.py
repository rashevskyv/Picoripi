from typing import List, Optional, Tuple
from PyQt6.QtGui import QTextCursor

class LNETTagHelpers:
    """L n e t tag helpers implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def find_icon_sequence_in_block(self, block_text: str, sequences: List[str], position_in_block: int) -> Optional[Tuple[int, int, str]]:
        """Find icon sequence in block."""
        if not block_text or not sequences:
            return None
        
        for token in sequences:
            start = -1
            while True:
                start = block_text.find(token, start + 1)
                if start == -1:
                    break
                end = start + len(token)
                if start <= position_in_block < end:
                    return start, end, token
        return None

    def snap_cursor_out_of_icon_sequences(self, move_right: bool) -> bool:
        """Snap cursor out of icon sequences."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection(): return False
        
        block = cursor.block()
        if not block.isValid(): return False

        sequences = self.editor._get_icon_sequences()
        if not sequences: return False

        pos_in_block = cursor.positionInBlock()
        block_text = block.text()
        
        all_matches = []
        for token in sequences:
            start = -1
            while True:
                start = block_text.find(token, start + 1)
                if start == -1: break
                all_matches.append((start, start + len(token), token))
        
        if not all_matches: return False

        for start, end, token in all_matches:
            if start < pos_in_block < end:
                new_pos = end if move_right else start
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + new_pos)
                self.editor.setTextCursor(new_cursor)
                self.editor._momentary_highlight_tag(block, start, len(token))
                return True
            elif move_right and pos_in_block == start:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + end)
                self.editor.setTextCursor(new_cursor)
                self.editor._momentary_highlight_tag(block, start, len(token))
                return True
            elif not move_right and pos_in_block == end:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + start)
                self.editor.setTextCursor(new_cursor)
                self.editor._momentary_highlight_tag(block, start, len(token))
                return True
                
        return False
