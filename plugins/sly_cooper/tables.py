"""Sly Cooper and the Thievius Raccoonus (ProjectCane port) level .brx: the shader and font tables.

Decodes the part of a level file that LoadSwFromBrx (Sly1-Release sw.cpp) reads before the object tree, so that
the CLUT table, the BMP table and the CFontBrx font records (with their glyph tables) can be read and written
back byte for byte. Everything is little endian. Source references are to the ProjectCane Sly1-Release sources.

Read order from file byte 8 (transition.cpp reads two S32 first, then SW::pfnLoadLoFromBrx = LoadSwFromBrx):
    U8 debug flag, S16 sound bank, U32 name table (sw.cpp), splice map (splicemap.cpp), world options
    (brx.cpp LoadOptionsFromBrx), 32-byte commentary descriptor, u16-prefixed speaker string, 32-byte music
    descriptor, shader section (shd.cpp LoadShadersFromBrx: CLUT, BMP, SHD records, fonts), object tree.
    The texture pixel data follows the object tree after Align(0x10) (sw.cpp, shd.cpp textureDataStart).

The object tree is not decoded here. The option table g_aeopid is extracted from spaprops.cpp BuildEopids and
embedded below as _OPTION_SCHEMA. Pure Python: no Qt, no game data.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Format of one g_aeopid entry (spaprops.cpp BuildEopids): (otyp, grfeopid, crefReq).
# Entries not assigned by BuildEopids stay zero: OTYP_Bool, grfeopid 0. The value is only used for
# grfeopid bit 0x400 (crefReq, argument count). Some otyp values are OR expressions with bit 31 set.
_OPTION_SCHEMA: Tuple[Tuple[int, int, int], ...] = (
    (7, 4, 0), (0, 1, 0), (18, 1025, 0), (10, 256, 0), (18, 1, 0), (8193, 1, 0),
    (8310, 2, 0), (0, 4, 0), (8194, 2, 0), (18, 1, 0), (0, 1, 0), (6, 2, 0),
    (6, 4, 0), (0, 1, 0), (18, 1024, 2), (18, 1024, 2), (18, 1024, 2), (18, 1024, 2),
    (18, 1024, 2), (18, 1024, 2), (18, 1024, 2), (2, 256, 0), (2, 256, 0), (6, 4224, 0),
    (1, 4224, 0), (1, 4224, 0), (4172, 4224, 0), (18, 1, 0), (0, 4, 0), (2, 66, 0),
    (2, 18, 0), (2, 2, 0), (4, 66, 0), (4, 18, 0), (4, 2, 0), (2, 292, 0),
    (2, 36, 0), (2, 66, 0), (2, 2, 0), (2, 2, 0), (8194, 2, 0), (1, 292, 0),
    (1, 292, 0), (0, 292, 0), (6, 292, 0), (1, 292, 0), (1, 292, 0), (1, 292, 0),
    (1, 292, 0), (1, 292, 0), (2, 292, 0), (6, 256, 0), (0, 288, 0), (4196, 292, 0),
    (0, 256, 0), (4110, 256, 0), (1, 288, 0), (9, 288, 0), (1, 288, 0), (9, 288, 0),
    (0, 256, 0), (4110, 256, 0), (5, 288, 0), (1, 288, 0), (9, 288, 0), (1, 288, 0),
    (9, 288, 0), (1, 288, 0), (12, 288, 0), (1, 288, 0), (12, 288, 0), (1, 288, 0),
    (1, 288, 0), (4110, 256, 0), (4110, 256, 0), (3, 0, 0), (4110, 256, 0), (1, 292, 0),
    (9, 292, 0), (10, 292, 0), (9, 292, 0), (10, 292, 0), (5, 292, 0), (5, 292, 0),
    (6, 260, 0), (8194, 36, 0), (18, 1, 0), (18, 1, 0), (18, 1025, 3), (-2147475455, 4, 0),
    (18, 1, 0), (4127, 288, 0), (1, 288, 0), (0, 288, 0), (18, 1, 0), (5, 288, 0),
    (5, 32, 0), (4160, 292, 0), (2, 292, 0), (2, 292, 0), (1, 292, 0), (14, 292, 0),
    (1, 260, 0), (1, 260, 0), (1, 292, 0), (1, 292, 0), (10, 260, 0), (18, 1, 0),
    (18, 1, 0), (1, 260, 0), (4163, 292, 0), (4163, 292, 0), (4163, 292, 0), (4163, 292, 0),
    (4163, 292, 0), (4163, 292, 0), (6, 32, 0), (18, 1, 0), (18, 1, 0), (0, 258, 0),
    (8339, 1, 0), (8338, 1, 0), (8338, 1, 0), (0, 288, 0), (18, 1, 0), (0, 292, 0),
    (18, 1, 0), (1, 34, 0), (4111, 288, 0), (2, 146, 0), (0, 256, 0), (4096, 288, 0),
    (4096, 288, 0), (1, 256, 0), (1, 2194, 0), (1, 2194, 0), (0, 288, 0), (0, 256, 0),
    (0, 288, 0), (0, 288, 0), (0, 288, 0), (0, 288, 0), (-2147475453, 4, 0), (4129, 146, 0),
    (1, 2, 0), (4132, 256, 0), (18, 1025, 1), (0, 1, 0), (0, 292, 0), (2, 18, 0),
    (4, 18, 0), (2, 4, 0), (4, 4, 0), (2, 18, 0), (1, 146, 0), (1, 146, 0),
    (1, 146, 0), (0, 130, 0), (0, 130, 0), (6, 146, 0), (1, 290, 0), (18, 1025, 4),
    (18, 1, 0), (6, 2194, 0), (4159, 2194, 0), (6, 2194, 0), (4106, 2194, 0), (1, 2194, 0),
    (0, 2194, 0), (0, 2194, 0), (0, 2194, 0), (0, 2194, 0), (0, 2194, 0), (1, 146, 0),
    (18, 1, 0), (4200, 34, 0), (2, 18, 0), (2, 4, 0), (4098, 2176, 0), (0, 2176, 0),
    (0, 2176, 0), (5, 128, 0), (1, 2194, 0), (9, 128, 0), (10, 128, 0), (8338, 1, 0),
    (8338, 1, 0), (1, 1, 0), (1, 2, 0), (0, 130, 0), (8323, 2, 0), (8194, 2, 0),
    (1, 2, 0), (1, 34, 0), (1, 34, 0), (5, 34, 0), (0, 34, 0), (18, 1, 0),
    (18, 1, 0), (18, 1, 0), (18, 1, 0), (0, 2194, 0), (0, 2194, 0), (2, 146, 0),
    (6, 4352, 0), (8193, 4128, 0), (8193, 4128, 0), (18, 1, 0), (1, 146, 0), (0, 146, 0),
    (0, 146, 0), (0, 146, 0), (6, 256, 0), (6, 256, 0), (6, 256, 0), (6, 256, 0),
    (0, 2194, 0), (1, 146, 0), (6, 2176, 0), (10, 146, 0), (1, 2194, 0), (1, 2194, 0),
    (6, 256, 0), (7, 256, 0), (7, 256, 0), (0, 292, 0), (0, 292, 0), (5, 146, 0),
    (18, 1, 0), (0, 34, 0), (0, 146, 0), (4162, 2194, 0), (1, 146, 0), (5, 146, 0),
    (2, 146, 0), (0, 146, 0), (14, 4242, 0), (1, 4242, 0), (1, 4242, 0), (1, 4242, 0),
    (6, 128, 0), (0, 146, 0), (1, 146, 0), (4096, 146, 0), (4096, 146, 0), (8195, 18, 0),
    (4124, 146, 0), (1, 2194, 0), (1, 2194, 0), (4146, 290, 0), (0, 146, 0), (6, 256, 0),
    (6, 256, 0), (6, 256, 0), (6, 256, 0), (7, 256, 0), (7, 256, 0), (1, 2194, 0),
    (4105, 2176, 0), (1, 2176, 0), (0, 2176, 0), (0, 2176, 0), (0, 2176, 0), (0, 2176, 0),
    (18, 1025, 4), (6, 128, 0), (4187, 34, 0), (6, 256, 0), (6, 256, 0), (1, 2194, 0),
    (1, 2176, 0), (0, 2176, 0), (0, 2176, 0), (0, 2176, 0), (0, 2194, 0), (6, 256, 0),
    (18, 1025, 4), (0, 2194, 0), (-2147475455, 4, 0), (6, 128, 0), (4187, 34, 0), (0, 290, 0),
    (18, 1, 0), (0, 1, 0), (4198, 4, 0), (6, 256, 0), (1, 2176, 0), (6, 256, 0),
    (0, 146, 0), (6, 256, 0), (6, 256, 0), (6, 256, 0), (0, 2194, 0), (1, 2194, 0),
    (4135, 2, 0), (-2147475408, 4, 0), (18, 1, 0), (18, 1025, 4), (8239, 2, 0), (6, 256, 0),
    (6, 256, 0), (7, 256, 0), (7, 256, 0), (0, 2194, 0), (1, 2194, 0), (1, 2194, 0),
    (4138, 2194, 0), (8239, 2, 0), (4138, 2, 0), (4137, 2, 0), (0, 18, 0), (18, 1, 0),
    (18, 1, 0), (4139, 2194, 0), (1, 2194, 0), (18, 1, 0), (18, 1, 0), (1, 2194, 0),
    (1, 2194, 0), (1, 2194, 0), (4140, 2, 0), (5, 146, 0), (5, 146, 0), (1, 146, 0),
    (4143, 2194, 0), (5, 146, 0), (5, 146, 0), (1, 146, 0), (4143, 2194, 0), (5, 146, 0),
    (5, 146, 0), (1, 146, 0), (4143, 2194, 0), (5, 146, 0), (1, 2194, 0), (1, 2194, 0),
    (1, 2194, 0), (4113, 130, 0), (1, 146, 0), (14, 146, 0), (14, 146, 0), (1, 146, 0),
    (0, 146, 0), (1, 146, 0), (6, 256, 0), (7, 256, 0), (0, 128, 0), (6, 128, 0),
    (5, 290, 0), (0, 290, 0), (4146, 4242, 0), (10, 4242, 0), (1, 4242, 0), (1, 4242, 0),
    (10, 4242, 0), (0, 36, 0), (0, 130, 0), (6, 130, 0), (6, 130, 0), (6, 130, 0),
    (6, 130, 0), (6, 130, 0), (18, 1, 0), (18, 1, 0), (18, 1, 0), (0, 4, 0),
    (4117, 4226, 0), (2, 4226, 0), (2, 4226, 0), (2, 4226, 0), (6, 130, 0), (4118, 4242, 0),
    (2, 4242, 0), (2, 4242, 0), (2, 4242, 0), (10, 4242, 0), (4120, 4242, 0), (10, 4242, 0),
    (1, 4242, 0), (2, 4242, 0), (1, 4242, 0), (1, 4242, 0), (2, 4242, 0), (4119, 4242, 0),
    (10, 4242, 0), (5, 4242, 0), (1, 4242, 0), (1, 4242, 0), (10, 4242, 0), (10, 4242, 0),
    (9, 4242, 0), (4116, 4226, 0), (4114, 256, 0), (4114, 4226, 0), (10, 4242, 0), (9, 4242, 0),
    (4115, 4226, 0), (1, 4242, 0), (6, 4226, 0), (9, 4242, 0), (9, 4242, 0), (9, 4242, 0),
    (0, 4242, 0), (1, 4242, 0), (0, 4242, 0), (4147, 4242, 0), (6, 4226, 0), (4148, 4242, 0),
    (1, 4242, 0), (4149, 4242, 0), (10, 4242, 0), (0, 4242, 0), (18, 1024, 6), (0, 4226, 0),
    (0, 4226, 0), (6, 4226, 0), (1, 4226, 0), (1, 4226, 0), (1, 4226, 0), (1, 4226, 0),
    (0, 4226, 0), (4118, 4242, 0), (2, 4242, 0), (2, 4242, 0), (2, 4242, 0), (6, 130, 0),
    (6, 130, 0), (4119, 4242, 0), (2, 4242, 0), (2, 4242, 0), (2, 4242, 0), (10, 4242, 0),
    (4121, 4242, 0), (10, 4242, 0), (1, 4242, 0), (10, 4242, 0), (5, 4242, 0), (1, 4242, 0),
    (10, 4242, 0), (18, 1024, 6), (10, 146, 0), (6, 130, 0), (6, 130, 0), (6, 130, 0),
    (1, 146, 0), (0, 146, 0), (2, 4242, 0), (1, 4242, 0), (1, 4242, 0), (2, 4242, 0),
    (4120, 4242, 0), (1, 4242, 0), (10, 4242, 0), (9, 4242, 0), (4116, 4226, 0), (4114, 256, 0),
    (4114, 4226, 0), (10, 4242, 0), (9, 4242, 0), (4115, 4226, 0), (1, 4242, 0), (6, 4226, 0),
    (9, 4242, 0), (9, 4242, 0), (9, 4242, 0), (0, 4242, 0), (1, 4242, 0), (0, 4242, 0),
    (4149, 4242, 0), (6, 4226, 0), (4150, 4242, 0), (1, 4242, 0), (4151, 4242, 0), (10, 4242, 0),
    (0, 4242, 0), (0, 4226, 0), (0, 4226, 0), (14, 4242, 0), (1, 4242, 0), (1, 4242, 0),
    (1, 4242, 0), (18, 1, 0), (18, 1, 0), (6, 4226, 0), (1, 4226, 0), (1, 4226, 0),
    (1, 4226, 0), (1, 4226, 0), (0, 4226, 0), (18, 1, 0), (18, 1, 0), (4122, 290, 0),
    (2, 162, 0), (1, 162, 0), (1, 162, 0), (1, 162, 0), (1, 162, 0), (1, 162, 0),
    (2, 290, 0), (0, 290, 0), (0, 290, 0), (0, 146, 0), (10, 162, 0), (1, 162, 0),
    (1, 162, 0), (2, 162, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (1, 0, 0),
    (1, 0, 0), (1, 0, 0), (1, 0, 0), (0, 128, 0), (8339, 1, 0), (8194, 2, 0),
    (6, 36, 0), (6, 4, 0), (6, 4, 0), (1, 34, 0), (8338, 2, 0), (6, 32, 0),
    (18, 1, 0), (8328, 2, 0), (0, 2176, 0), (1, 2176, 0), (1, 162, 0), (1, 162, 0),
    (13, 128, 0), (1, 256, 0), (1, 256, 0), (1, 256, 0), (1, 256, 0), (1, 256, 0),
    (1, 256, 0), (13, 256, 0), (1, 256, 0), (1, 2194, 0), (1, 2194, 0), (1, 34, 0),
    (1, 34, 0), (1, 34, 0), (5, 4242, 0), (5, 4242, 0), (5, 4242, 0), (5, 4242, 0),
    (18, 1, 0), (1, 36, 0), (1, 36, 0), (14, 288, 0), (10, 288, 0), (10, 288, 0),
    (18, 1024, 2), (18, 1, 0), (18, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0),
    (0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0), (18, 1, 0), (5, 1, 0),
    (0, 1, 0), (0, 1, 0), (5, 1, 0), (0, 4, 0), (18, 1, 0), (18, 1, 0),
    (18, 1, 0), (18, 1, 0), (0, 146, 0), (5, 1, 0), (18, 1, 0), (18, 1, 0),
    (5, 1, 0), (18, 1, 0), (18, 1, 0), (18, 1, 0), (18, 1025, 1), (18, 1025, 1),
    (5, 4, 0), (5, 4, 0), (2, 34, 0), (4, 34, 0), (1, 34, 0), (1, 18, 0),
    (12, 18, 0), (1, 34, 0), (1, 34, 0), (1, 34, 0), (1, 34, 0), (1, 34, 0),
    (1, 34, 0), (18, 1, 0), (4177, 1, 0), (4177, 1, 0), (18, 1, 0), (18, 1, 0),
    (18, 1, 0), (0, 1, 0), (6, 128, 0), (2, 128, 0), (2, 128, 0), (2, 128, 0),
    (18, 1, 0), (18, 1, 0), (0, 146, 0), (4124, 146, 0), (6, 4352, 0), (8193, 4128, 0),
    (8193, 4128, 0), (18, 1, 0), (1, 146, 0), (0, 146, 0), (4127, 146, 0), (1, 146, 0),
    (0, 146, 0), (6, 256, 0), (6, 256, 0), (6, 256, 0), (18, 1, 0), (1, 146, 0),
    (0, 4, 0), (1, 290, 0), (1, 2194, 0), (4131, 2194, 0), (0, 146, 0), (6, 128, 0),
    (0, 146, 0), (1, 146, 0), (0, 146, 0), (4131, 2194, 0), (0, 146, 0), (6, 128, 0),
    (4164, 146, 0), (0, 146, 0), (1, 146, 0), (0, 146, 0), (1, 2194, 0), (5, 2194, 0),
    (1, 146, 0), (2, 146, 0), (14, 146, 0), (14, 146, 0), (4178, 146, 0), (18, 0, 0),
    (0, 146, 0), (6, 128, 0), (8302, 18, 0), (1, 146, 0), (6, 162, 0), (10, 146, 0),
    (10, 146, 0), (1, 274, 0), (18, 1024, 2), (18, 1, 0), (8323, 1, 0), (1, 146, 0),
    (18, 1024, 4), (18, 1024, 2), (18, 1024, 2), (18, 1, 0), (18, 1024, 2), (5, 146, 0),
    (0, 146, 0), (18, 1, 0), (10, 146, 0), (0, 146, 0), (6, 146, 0), (8195, 36, 0),
    (0, 146, 0), (0, 146, 0), (1, 146, 0), (9, 146, 0), (4174, 146, 0), (18, 1, 0),
    (5, 146, 0), (2, 146, 0), (0, 146, 0), (6, 256, 0), (6, 256, 0), (1, 128, 0),
    (1, 146, 0), (0, 146, 0), (4133, 2, 0), (0, 146, 0), (0, 4, 0), (10, 146, 0),
    (0, 146, 0), (1, 146, 0), (0, 146, 0), (0, 146, 0), (6, 256, 0), (6, 256, 0),
    (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (6, 146, 0), (6, 128, 0),
    (8288, 2, 0), (18, 1024, 2), (0, 146, 0), (0, 146, 0), (4197, 146, 0), (6, 146, 0),
    (6, 256, 0), (1, 2176, 0), (1, 288, 0), (1, 290, 0), (1, 146, 0), (1, 146, 0),
    (4135, 146, 0), (4136, 146, 0), (0, 146, 0), (1, 146, 0), (1, 146, 0), (10, 146, 0),
    (1, 146, 0), (18, 1, 0), (18, 1, 0), (0, 146, 0), (0, 146, 0), (4124, 146, 0),
    (14, 4242, 0), (1, 4242, 0), (1, 4242, 0), (1, 4242, 0), (1, 146, 0), (0, 130, 0),
    (18, 1, 0), (18, 1, 0), (18, 1, 0), (0, 146, 0), (4178, 34, 0), (18, 1, 0),
    (18, 1, 0), (18, 1, 0), (18, 1, 0), (0, 146, 0), (0, 162, 0), (18, 1, 0),
    (18, 1, 0), (18, 1, 0), (4144, 128, 0), (6, 128, 0), (6, 128, 0), (4127, 128, 0),
    (18, 1024, 3), (18, 1024, 3), (1, 2194, 0), (1, 2194, 0), (1, 2194, 0), (1, 2194, 0),
    (1, 2194, 0), (1, 2194, 0), (1, 146, 0), (1, 2194, 0), (4154, 2, 0), (5, 146, 0),
    (0, 146, 0), (1, 2176, 0), (1, 2176, 0), (1, 2176, 0), (1, 2176, 0), (5, 2176, 0),
    (2, 146, 0), (0, 146, 0), (2, 146, 0), (6, 256, 0), (6, 256, 0), (6, 256, 0),
    (6, 256, 0), (6, 256, 0), (1, 4242, 0), (1, 4226, 0), (9, 4242, 0), (1, 4242, 0),
    (1, 4226, 0), (9, 4242, 0), (10, 4242, 0), (10, 4242, 0), (9, 4242, 0), (10, 4242, 0),
    (10, 4242, 0), (9, 4242, 0), (1, 4242, 0), (1, 4242, 0), (9, 4242, 0), (1, 4242, 0),
    (1, 4242, 0), (9, 4242, 0), (2, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0),
    (1, 146, 0), (1, 146, 0), (5, 130, 0), (4147, 130, 0), (5, 146, 0), (9, 146, 0),
    (1, 146, 0), (10, 146, 0), (5, 128, 0), (1, 146, 0), (1, 146, 0), (9, 146, 0),
    (4145, 34, 0), (1, 2194, 0), (1, 2194, 0), (1, 2194, 0), (1, 2194, 0), (1, 2194, 0),
    (6, 128, 0), (5, 2176, 0), (1, 2194, 0), (1, 2194, 0), (6, 256, 0), (18, 1, 0),
    (18, 1, 0), (1, 2194, 0), (8194, 18, 0), (2, 18, 0), (0, 146, 0), (18, 1024, 1),
    (18, 1024, 1), (1, 2194, 0), (1, 2194, 0), (2, 18, 0), (1, 146, 0), (1, 2194, 0),
    (1, 2194, 0), (2, 146, 0), (1, 2194, 0), (6, 2176, 0), (1, 146, 0), (6, 130, 0),
    (18, 1024, 4), (1, 146, 0), (1, 146, 0), (6, 128, 0), (8315, 18, 0), (10, 146, 0),
    (10, 146, 0), (6, 128, 0), (8315, 18, 0), (0, 146, 0), (0, 146, 0), (1, 146, 0),
    (9, 146, 0), (10, 146, 0), (9, 146, 0), (10, 146, 0), (9, 146, 0), (10, 146, 0),
    (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0),
    (1, 290, 0), (2, 146, 0), (0, 146, 0), (4108, 146, 0), (0, 146, 0), (0, 146, 0),
    (5, 146, 0), (0, 146, 0), (4165, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0),
    (1, 146, 0), (0, 146, 0), (1, 146, 0), (0, 146, 0), (8194, 18, 0), (9, 146, 0),
    (10, 146, 0), (4109, 2, 0), (4109, 162, 0), (1, 146, 0), (1, 146, 0), (6, 160, 0),
    (18, 1, 0), (18, 1, 0), (0, 146, 0), (1, 146, 0), (1, 146, 0), (0, 146, 0),
    (6, 128, 0), (8318, 18, 0), (6, 128, 0), (8292, 18, 0), (4170, 146, 0), (1, 146, 0),
    (1, 146, 0), (4171, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0),
    (1, 146, 0), (18, 1024, 4), (0, 4226, 0), (4158, 146, 0), (5, 18, 0), (18, 1, 0),
    (18, 1, 0), (18, 1, 0), (18, 1, 0), (0, 1, 0), (8195, 2, 0), (18, 1, 0),
    (6, 128, 0), (8194, 18, 0), (8318, 18, 0), (8307, 18, 0), (2, 146, 0), (4, 146, 0),
    (2, 146, 0), (2, 146, 0), (10, 146, 0), (1, 146, 0), (18, 1, 0), (6, 146, 0),
    (8194, 18, 0), (8309, 18, 0), (2, 146, 0), (4166, 146, 0), (9, 146, 0), (9, 146, 0),
    (10, 146, 0), (9, 146, 0), (10, 146, 0), (18, 1, 0), (4153, 146, 0), (6, 128, 0),
    (8307, 18, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (6, 128, 0), (8194, 2, 0),
    (4155, 2178, 0), (4156, 2178, 0), (4156, 34, 0), (10, 146, 0), (10, 146, 0), (10, 146, 0),
    (10, 146, 0), (6, 128, 0), (1, 2194, 0), (10, 146, 0), (1, 2194, 0), (10, 146, 0),
    (10, 146, 0), (10, 146, 0), (10, 146, 0), (1, 2194, 0), (5, 146, 0), (0, 146, 0),
    (4167, 34, 0), (6, 128, 0), (0, 146, 0), (0, 146, 0), (0, 146, 0), (18, 1024, 0),
    (18, 1024, 0), (18, 1024, 2), (18, 1, 0), (18, 1, 0), (6, 146, 0), (0, 36, 0),
    (0, 130, 0), (6, 146, 0), (1, 146, 0), (4167, 66, 0), (0, 146, 0), (1, 146, 0),
    (0, 146, 0), (10, 146, 0), (10, 146, 0), (0, 0, 0), (5, 146, 0), (1, 146, 0),
    (1, 146, 0), (1, 146, 0), (1, 146, 0), (2, 146, 0), (2, 146, 0), (1, 146, 0),
    (1, 146, 0), (6, 160, 0), (2, 146, 0), (1, 146, 0), (6, 256, 0), (18, 1, 0),
    (5, 256, 0), (18, 1024, 0), (18, 1024, 0), (2, 4242, 0), (1, 292, 0), (1, 4242, 0),
    (1, 4242, 0), (2, 4242, 0), (2, 4242, 0), (10, 4242, 0), (10, 4242, 0), (2, 4242, 0),
    (10, 4242, 0), (1, 4242, 0), (18, 1024, 4), (2, 4242, 0), (10, 4242, 0), (1, 4242, 0),
    (18, 1024, 4), (5, 2, 0), (5, 18, 0), (0, 146, 0), (8339, 2, 0), (8307, 146, 0),
    (18, 1, 0), (1, 4, 0), (4175, 34, 0), (0, 146, 0), (1, 146, 0), (0, 146, 0),
    (0, 146, 0), (1, 2194, 0), (1, 2194, 0), (1, 146, 0), (0, 146, 0), (6, 128, 0),
    (8302, 18, 0), (8339, 2, 0), (0, 146, 0), (4177, 146, 0), (0, 146, 0), (6, 256, 0),
    (10, 146, 0), (10, 146, 0), (5, 146, 0), (18, 1024, 2), (6, 128, 0), (6, 128, 0),
    (0, 146, 0), (1, 128, 0), (8339, 2, 0), (8339, 2, 0), (2, 128, 0), (1, 128, 0),
    (10, 128, 0), (5, 146, 0), (1, 146, 0), (6, 256, 0), (1, 4242, 0), (1, 4242, 0),
    (9, 4242, 0), (1, 4242, 0), (1, 4242, 0), (1, 4242, 0), (9, 4242, 0), (1, 4242, 0),
    (1, 4242, 0), (9, 4242, 0), (1, 4242, 0), (1, 4242, 0), (9, 4242, 0), (1, 4242, 0),
    (1, 4242, 0), (9, 4242, 0), (5, 146, 0), (9, 146, 0), (8339, 2, 0), (5, 146, 0),
    (1, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (8302, 34, 0), (8302, 34, 0),
    (5, 146, 0), (18, 1, 0), (18, 1, 0), (8330, 18, 0), (4183, 290, 0), (18, 1, 0),
    (4184, 146, 0), (5, 146, 0), (8311, 18, 0), (8311, 18, 0), (8272, 18, 0), (1, 146, 0),
    (5, 146, 0), (9, 146, 0), (10, 146, 0), (9, 146, 0), (10, 146, 0), (0, 1, 0),
    (0, 1, 0), (0, 1, 0), (8307, 34, 0), (8307, 34, 0), (2, 4, 0), (1, 146, 0),
    (1, 146, 0), (1, 146, 0), (1, 146, 0), (18, 1, 0), (4176, 34, 0), (18, 1025, 0),
    (18, 1, 0), (18, 1, 0), (18, 1025, 1), (18, 1025, 1), (18, 1025, 1), (18, 1025, 1),
    (18, 1025, 1), (18, 1025, 2), (18, 1025, 4), (18, 1025, 3), (18, 1025, 3), (18, 1025, 3),
    (18, 1025, 2), (18, 1025, 1), (0, 146, 0), (18, 1025, 0), (18, 1025, 0), (13, 146, 0),
    (13, 146, 0), (13, 146, 0), (1, 146, 0), (1, 146, 0), (1, 146, 0), (4188, 146, 0),
    (8195, 18, 0), (4190, 34, 0), (0, 32, 0), (18, 1, 0), (18, 1, 0), (1, 146, 0),
    (1, 146, 0), (18, 1, 0), (5, 146, 0), (4191, 162, 0), (5, 290, 0), (5, 290, 0),
    (18, 1, 0), (18, 1, 0), (8339, 2, 0), (8307, 18, 0), (18, 1, 0), (18, 1, 0),
    (18, 1, 0), (8307, 18, 0), (8335, 18, 0), (18, 1025, 3), (18, 1025, 3), (18, 1025, 2),
    (18, 1025, 2), (18, 1025, 2), (18, 1025, 2), (5, 18, 0), (18, 1, 0), (0, 18, 0),
    (4199, 34, 0), (18, 1, 0), (5, 146, 0), (5, 146, 0), (18, 1, 0), (18, 1, 0),
    (5, 18, 0), (8311, 18, 0), (18, 1, 0),
)
OPTION_COUNT = 1179

_WORLD_START = 8  # two S32 read by transition.cpp before LoadSwFromBrx

# OTYP values (spaprops.h enum OTYP) used by the reader.
_OTYP_BOOL = 0
_OTYP_FLOAT = 1
_OTYP_VECTOR = 2
_OTYP_VECTOR4 = 3
_OTYP_MATRIX = 4
_OTYP_INT = 5
_OTYP_OID = 6
_OTYP_CID = 7
_OTYP_CLQ = 9
_OTYP_LM = 10
_OTYP_SMP = 11
_OTYP_SMPA = 12
_OTYP_RGBA = 13
_OTYP_SFXID = 14
_OTYP_WID = 15
_OTYP_TBID = 16
_OTYP_MSGID = 17
_OTYP_OPTID = 20

_GRF_THUNK_ARGS = 0x400  # LoadOptionFromBrx: crefReq arguments, each with its own S16 otyp

# Bytes read by LoadOptionFromBrx for one value (both the 0x80 path and the plain path agree).
_PLAIN_OPTION_SIZE = {
    _OTYP_BOOL: 1, _OTYP_FLOAT: 4, _OTYP_VECTOR: 12, _OTYP_VECTOR4: 16, _OTYP_MATRIX: 12,
    _OTYP_INT: 4, _OTYP_CLQ: 12, _OTYP_LM: 8, _OTYP_SMP: 12, _OTYP_SMPA: 16, _OTYP_RGBA: 4,
}
# Bytes read for one crefReq argument (grfeopid 0x400 path). Other types read nothing unless the
# range rule below applies. Vector4, Matrix, Smp, Smpa, Rgba, Ishd, Void, Musid read 0 bytes here.
_ARG_OPTION_SIZE = {
    _OTYP_BOOL: 1, _OTYP_FLOAT: 4, _OTYP_VECTOR: 12, _OTYP_INT: 4, _OTYP_CLQ: 12, _OTYP_LM: 8,
    _OTYP_OID: 2, _OTYP_CID: 2, _OTYP_SFXID: 2, _OTYP_WID: 2, _OTYP_TBID: 2, _OTYP_MSGID: 2,
    _OTYP_OPTID: 2,
}

# TAGK payload sizes in a splice-map pair (ref.h TAGK, serialize.cpp PpairSerializeIn).
_TAGK_PAIR = 30
_TAGK_PAYLOAD = {
    20: 4, 21: 4, 22: 12, 23: 64, 24: 12, 25: 8, 26: 12, 27: 4, 28: 4, 29: 4, 32: 4,
}

# SAAK values with a loader (shdanim.cpp NewSaa). Each loader reads 24 bytes.
_SAAK_KNOWN = frozenset(range(1, 9))
_SAA_BODY_SIZE = 24

_CLUT_STRUCT = struct.Struct("<IHHI")  # grfzon, numColors, colorSize, baseOffset
_BMP_STRUCT = struct.Struct("<HHIbbHII")  # bmpWidth, bmpHeight, grfzon, psm, cgsRow, cgsPixels, cbPixels, baseOffset
_FONT_HEADER_STRUCT = struct.Struct("<HhBBBBfI")  # ibmp, iclut, dxChar, dxSpace, dy, fontk, rxScale, cglyff
_GLYPH_STRUCT = struct.Struct("<hhhh")  # wch, x, y, dx
_SHD_HEAD_SIZE = 20  # shdk, grfshd, oid, rgba x4, rgbaVolume x4, grfzon, oidAltSat, rp, ctex
_TEX_HEAD_SIZE = 6  # oid, grftex, cibmp, ciclut
_SAA_HEAD_SIZE = 2  # saak (U16); a known saak then has oid S16, fInstanced U16 and the 24-byte body


class TablesError(ValueError):
    """The data does not match the format described in this module."""


@dataclass(frozen=True)
class Clut:
    """One CLUT property (shd.cpp LoadColorTablesFromBrx). Entry size 12 bytes."""

    offset: int
    grfzon: int
    num_colors: int
    color_size: int
    base_offset: int  # relative to texture_start


@dataclass(frozen=True)
class Bmp:
    """One BMP property (shd.cpp LoadBitmapsFromBrx). Entry size 20 bytes."""

    offset: int
    width: int
    height: int
    grfzon: int
    psm: int
    cgs_row: int
    cgs_pixels: int
    cb_pixels: int
    base_offset: int  # relative to texture_start


@dataclass(frozen=True)
class Glyph:
    """One glyph of a CFontBrx (font.cpp CFontBrx::LoadFromBrx). Entry size 8 bytes."""

    wch: int  # Unicode code point
    x: int  # atlas position
    y: int
    dx: int  # advance


@dataclass(frozen=True)
class Font:
    """One CFontBrx record: 16-byte header, then cglyff glyphs."""

    offset: int  # position of the header
    ibmp: int  # index into the BMP table
    iclut: int  # index into the CLUT table
    dx_char: int
    dx_space: int
    dy: int
    fontk: int
    rx_scale: float
    glyph_offset: int  # position of the first glyph (header offset + 16)
    glyphs: Tuple[Glyph, ...]

    @property
    def end(self) -> int:
        return self.glyph_offset + _GLYPH_STRUCT.size * len(self.glyphs)


@dataclass(frozen=True)
class ShaderSpan:
    """Byte range of one SHD record and the number of texture entries (TEX) it holds."""

    offset: int
    end: int
    ctex: int


@dataclass(frozen=True)
class WorldTables:
    """Decoded prefix of one level file. All offsets are absolute positions in the file."""

    ibnk: int
    option_count: int
    cluts: Tuple[Clut, ...]
    bmps: Tuple[Bmp, ...]
    shaders: Tuple[ShaderSpan, ...]
    fonts: Tuple[Font, ...]
    shader_end: int  # position right after the last font record
    texture_start: Optional[int] = None  # always None: needs the object tree, which is not decoded


class _Cursor:
    """Little-endian reader that refuses to read past the end of the data."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int) -> None:
        self.data = data
        self.pos = pos

    def take(self, count: int) -> bytes:
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise TablesError(f"read of {count} bytes at {self.pos:#x} passes the end of the data")
        raw = self.data[self.pos:end]
        self.pos = end
        return raw

    def skip(self, count: int) -> None:
        self.take(count)

    def unpack(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def u8(self) -> int:
        return self.unpack("<B")

    def s16(self) -> int:
        return self.unpack("<h")

    def u16(self) -> int:
        return self.unpack("<H")

    def u32(self) -> int:
        return self.unpack("<I")


def _skip_pair_chain(cur: _Cursor) -> None:
    """One PpairSerializeIn call: a tag byte, its payload, then the next pair while bit 7 is set.

    A tag byte of 0xFF is a null pair and has no payload or next pair."""
    while True:
        tag_byte = cur.u8()
        if tag_byte == 0xFF:
            return
        tag = tag_byte & 0x7F
        if tag == _TAGK_PAIR:
            _skip_pair_chain(cur)
        else:
            cur.skip(_TAGK_PAYLOAD.get(tag, 0))
        if not tag_byte & 0x80:
            return


def _skip_splice_map(cur: _Cursor) -> None:
    """LoadSwSpliceFromBrx with g_fLoadDebugInfo == 0: three U32 counts, then one pair chain per splice.

    The symid and extra option name tables are not stored in the file when debug info is off."""
    splice_count = cur.u32()
    cur.u32()  # symidMax
    cur.u32()  # extraOptCount
    for _ in range(splice_count):
        _skip_pair_chain(cur)


def _skip_plain_option(otyp: int, cur: _Cursor) -> None:
    cur.skip(_PLAIN_OPTION_SIZE.get(otyp, 2))  # default branch reads one S16


def _skip_thunk_arg(cur: _Cursor) -> None:
    """One crefReq argument: an S16 otyp, then its value bytes as LoadOptionFromBrx reads them."""
    otyp = cur.s16()
    size = _ARG_OPTION_SIZE.get(otyp)
    if size is None:
        # default: reads S16 only when (otyp & 0x7fffffff) >> 12 == 1, i.e. otyp in 0x1000..0x1fff
        size = 2 if (((otyp & 0xFFFFFFFF) & 0x7FFFFFFF) >> 12) == 1 else 0
    cur.skip(size)


def _skip_option(cur: _Cursor, entry: Tuple[int, int, int]) -> None:
    otyp, grfeopid, carg = entry
    if grfeopid & _GRF_THUNK_ARGS:
        for _ in range(carg):
            _skip_thunk_arg(cur)
        return
    _skip_plain_option(otyp, cur)


def _skip_options(cur: _Cursor) -> int:
    """LoadOptionsFromBrx: S16 eopid per option, a negative eopid ends the list. Returns the option count."""
    count = 0
    while True:
        eopid = cur.s16()
        if eopid < 0:
            return count
        if eopid >= OPTION_COUNT:
            raise TablesError(f"option id {eopid} is outside g_aeopid[{OPTION_COUNT}]")
        _skip_option(cur, _OPTION_SCHEMA[eopid])
        count += 1


def _read_clut_table(cur: _Cursor) -> List[Clut]:
    count = cur.u16()
    result = []
    for _ in range(count):
        offset = cur.pos
        grfzon, num_colors, color_size, base_offset = _CLUT_STRUCT.unpack(cur.take(_CLUT_STRUCT.size))
        result.append(Clut(offset, grfzon, num_colors, color_size, base_offset))
    return result


def _read_bmp_table(cur: _Cursor) -> List[Bmp]:
    count = cur.u16()
    result = []
    for _ in range(count):
        offset = cur.pos
        fields = _BMP_STRUCT.unpack(cur.take(_BMP_STRUCT.size))
        result.append(Bmp(offset, *fields))
    return result


def _skip_shader(cur: _Cursor) -> ShaderSpan:
    """One SHD record: head, optional SAA animation, TEX entries (LoadShadersFromBrx and LoadTexFromBrx)."""
    offset = cur.pos
    head = cur.take(_SHD_HEAD_SIZE)
    ctex = head[_SHD_HEAD_SIZE - 1]
    saak = cur.u16()  # PsaaLoadFromBrx; only known saak values carry more bytes
    if saak in _SAAK_KNOWN:
        cur.skip(2 + 2 + _SAA_BODY_SIZE)  # oid S16, fInstanced U16, loader body
    for _ in range(ctex):
        tex_head = cur.take(_TEX_HEAD_SIZE)  # oid U16, grftex S16, cibmp U8, ciclut U8
        cibmp = tex_head[4]
        ciclut = tex_head[5]
        cur.skip(2 * (cibmp + ciclut))  # U16 BMP indices, then U16 CLUT indices
    return ShaderSpan(offset, cur.pos, ctex)


def _read_font(cur: _Cursor) -> Font:
    """One CFontBrx::LoadFromBrx record. The header is 16 bytes; each glyph is 8 bytes."""
    offset = cur.pos
    ibmp, iclut, dx_char, dx_space, dy, fontk, rx_scale, cglyff = _FONT_HEADER_STRUCT.unpack(
        cur.take(_FONT_HEADER_STRUCT.size))
    glyph_offset = cur.pos
    glyphs = []
    for _ in range(cglyff):
        glyphs.append(Glyph(*_GLYPH_STRUCT.unpack(cur.take(_GLYPH_STRUCT.size))))
    return Font(offset, ibmp, iclut, dx_char, dx_space, dy, fontk, rx_scale, glyph_offset, tuple(glyphs))


def read_tables(data: bytes) -> WorldTables:
    """Decode the level prefix up to the end of the font table.

    texture_start is None here: it is the position after the object tree and Align(0x10), and the object tree
    is not decoded."""
    cur = _Cursor(data, _WORLD_START)
    cur.u8()  # debug flag, unused by the loader
    ibnk = cur.s16()
    cur.u32()  # name table count (LoadNameTableFromBrx reads one U32)
    _skip_splice_map(cur)
    option_count = _skip_options(cur)
    cur.skip(32)  # commentary audio descriptor (encrypted file descriptor, kept verbatim by the loader)
    cur.skip(cur.u16())  # commentary speakers (ReadStringSw)
    cur.skip(32)  # music descriptor
    cluts = _read_clut_table(cur)
    bmps = _read_bmp_table(cur)
    shd_count = cur.u16()
    cur.u16()  # g_cpsaa, a count used only for reserve()
    shaders = [_skip_shader(cur) for _ in range(shd_count)]
    font_count = cur.u16()
    fonts = [_read_font(cur) for _ in range(font_count)]
    return WorldTables(
        ibnk=ibnk,
        option_count=option_count,
        cluts=tuple(cluts),
        bmps=tuple(bmps),
        shaders=tuple(shaders),
        fonts=tuple(fonts),
        shader_end=cur.pos,
    )


def write_clut_entry(entry: Clut) -> bytes:
    return _CLUT_STRUCT.pack(entry.grfzon, entry.num_colors, entry.color_size, entry.base_offset)


def write_bmp_entry(entry: Bmp) -> bytes:
    return _BMP_STRUCT.pack(entry.width, entry.height, entry.grfzon, entry.psm, entry.cgs_row,
                            entry.cgs_pixels, entry.cb_pixels, entry.base_offset)


def write_font_header(font: Font) -> bytes:
    return _FONT_HEADER_STRUCT.pack(font.ibmp, font.iclut, font.dx_char, font.dx_space, font.dy,
                                    font.fontk, font.rx_scale, len(font.glyphs))


def write_font_glyph_table(glyphs: Tuple[Glyph, ...]) -> bytes:
    return b"".join(_GLYPH_STRUCT.pack(g.wch, g.x, g.y, g.dx) for g in glyphs)


def write_font(font: Font) -> bytes:
    return write_font_header(font) + write_font_glyph_table(font.glyphs)
