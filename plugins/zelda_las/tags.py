"""Link's Awakening (Switch) MSBT control tags: no MSBP catalogue ships with the files, so every tag is shown raw.

A raw tag reads as ``{tag:G:T:hex}`` and encodes back to the same bytes, so a file always round-trips.
"""
from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

CODEC = TagCodec({})
