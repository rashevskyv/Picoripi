"""The message table of Luigi's Mansion (GameCube): one ``message/messageNN.csv`` member of an event archive.

The file is Shift-JIS text (the English slot is ASCII; a few messages are Japanese). A record ends with CRLF, so
``<SPEAK>(n)`` in the event script reads record n. An LF inside a record is a line break within the message. Tags
are ``<TAG>`` or ``<TAG>(n)``. A file that does not decode as Shift-JIS is not a message table.
"""
from __future__ import annotations

from typing import List, Sequence

from core.i18n import tr

ENCODING = "cp932"
RECORD_END = "\r\n"


class Table:
    """One message file. ``build`` returns the original bytes while no record changed."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        text = self.raw.decode(ENCODING)   # ValueError (UnicodeDecodeError) for a file that is not Shift-JIS
        self.tail = text.endswith(RECORD_END)
        body = text[:-len(RECORD_END)] if self.tail else text
        self._texts: List[str] = body.split(RECORD_END) if text else []

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return [str(i + 1) for i in range(len(self._texts))]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != len(self._texts):
            raise ValueError(tr("the message file holds {0} records, {1} were given", len(self._texts), len(texts)))
        for number, text in enumerate(texts, 1):
            if RECORD_END in text:
                raise ValueError(tr("record {0}: a record break (CRLF) is not allowed inside a message", number))
            try:
                text.encode(ENCODING)
            except UnicodeEncodeError as error:
                raise ValueError(tr("record {0}: the character {1} has no Shift-JIS code", number, repr(text[error.start]))) from None
        body = RECORD_END.join(texts)
        return (body + RECORD_END if self.tail else body).encode(ENCODING)
