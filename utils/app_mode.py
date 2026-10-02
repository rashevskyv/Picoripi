"""How the code is being run: inside the interactive application, or headless.

``headless`` is set once by whoever embeds the code without a person at the
screen and without a running event loop -- the test suite (``tests/conftest.py``)
or a script. Then background work runs inline and nothing modal is shown.

Read it as ``app_mode.headless`` at the moment of the decision; never copy the
value at import time. The code must not try to detect its caller by itself
(``'pytest' in sys.modules``): the caller says what it is.
"""

headless: bool = False
