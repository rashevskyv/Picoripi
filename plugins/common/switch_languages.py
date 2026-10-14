"""Nintendo Switch region-language codes (``EUru``, ``USen``, ...) and their reference-column labels.

The same codes name TotK's ``Mals/<code>.Product.*.sarc.zs`` archives and LAS's ``region*/<code>`` romfs folders.
"""

# Code -> reference label. Russian keeps "Russian (RU)": the host shows it first.
LANGUAGES = {
    "EUru": "Russian (RU)", "USen": "English (US)", "EUen": "English (EU)", "EUde": "German (DE)",
    "EUfr": "French (EU)", "USfr": "French (US)", "EUes": "Spanish (EU)", "USes": "Spanish (US)",
    "EUit": "Italian (IT)", "EUnl": "Dutch (NL)", "USpt": "Portuguese (US)", "JPja": "Japanese (JA)",
    "KRko": "Korean (KO)", "CNzh": "Chinese, simplified (CN)", "TWzh": "Chinese, traditional (TW)",
}
