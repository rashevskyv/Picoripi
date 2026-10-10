# Silent Hill (PS1) PC port: how it was built here

The port is SlickAmogus/silent-hill-decomp (GPL-3.0, `pc_port/`). Its source is not changed. No binaries are kept in this repository.

## Inputs (not in git)

| Item | Source | Check |
|---|---|---|
| Port source | https://github.com/SlickAmogus/silent-hill-decomp (clone, depth 1) | `pc_port/CMakeLists.txt` |
| PsyCross | https://github.com/SlickAmogus/PsyCross (submodule `pc_port/PsyCross`, clone, depth 1) | `pc_port/PsyCross/CMakeLists.txt` |
| rcheevos | https://github.com/RetroAchievements/rcheevos, commit pinned by the port: `2ad0b8672f68a48148620164510b963039e49eb1` | `pc_port/third_party/rcheevos/src/rc_client.c` |
| OpenAL Soft 1.25.2 | https://openal-soft.org/openal-binaries/openal-soft-1.25.2-bin.zip (official site; the page lists no checksum) | SHA-256 `67a0c4b800bd860c93c04f38caf8cbe4875f9c84700ac430efc451f70e265434` (computed here) |
| libjpeg-turbo 3.2.0 MinGW | https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.2.0/libjpeg-turbo-3.2.0-gcc-x64.exe (GitHub asset digest) | SHA-256 `5a71ea596c573ea3b44c8e7b5e78613d3a28dc9490dc714e7222c9f63f55e454` (matches) |
| SDL2 (MinGW dev) | local tools folder `_shared\tools\SDL2-2.32.10\x86_64-w64-mingw32` | `lib\libSDL2.a` |
| Toolchain | w64devkit (gcc 16.2, cmake 4.4, ninja) in `_shared\tools\w64devkit` | `cmake --version` |

The libjpeg installer is not an Inno Setup file; its `include\` and `lib\` folders were taken with 7-Zip.

## Build

1. Copy the whole repository (`port\`) to a path **without spaces**. `windres` fails on spaces in include paths.
2. Configure and build with w64devkit (ninja):

```
cmake -S <copy>\pc_port -B <build> -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSH_BUILD_MAP_DLLS=OFF -DSH_FMV_FFMPEG=OFF \
  -DCMAKE_C_COMPILER=<w64devkit>\bin\gcc.exe -DCMAKE_CXX_COMPILER=<w64devkit>\bin\g++.exe \
  -DCMAKE_CXX_FLAGS="-include cmath" \
  -DCMAKE_PREFIX_PATH=<SDL2>\x86_64-w64-mingw32 \
  -DOPENAL_INCLUDE_DIR=<openal>\include -DOPENAL_LIBRARY=<openal>\libs\Win64\libOpenAL32.dll.a \
  -DJPEG_INCLUDE_DIR=<libjpeg>\include -DJPEG_LIBRARY=<libjpeg>\lib\libjpeg.dll.a \
  -DCMAKE_C_STANDARD_LIBRARIES=-lwinhttp -DCMAKE_CXX_STANDARD_LIBRARIES=-lwinhttp
ninja -C <build>
```

Why each flag:

- `-include cmath`: `PsyX_render.cpp` uses `sinf` and friends without `<cmath>`. Newer gcc does not include it through other headers.
- `-lwinhttp` as the last library: `pc_ra_http.c` needs WinHTTP. It must come after the object files.
- `SH_BUILD_MAP_DLLS=OFF`: builds the starting area only (the 42 map DLLs add about 500 compile steps).
- `SH_FMV_FFMPEG=OFF`: the ffmpeg FMV fallback is optional.
- OpenAL is required by `PsyCross` (`find_package(OpenAL REQUIRED)`) and by `PsyX_SPULegacy.cpp` (`AL/al.h`).
- libjpeg is required by `src/fmv/fmv_player.cpp` (`jpeglib.h`).

## Run

Copy next to `SilentHillPC.exe`: `OpenAL32.dll` (router\Win64), `SDL2.dll`, `libjpeg-62.dll` (bin of the libjpeg package), and `gamedata\` with the disc image. The port reads `gamedata\` relative to its working directory. For a run without sound set `ALSOFT_DRIVERS=null` and `SDL_AUDIODRIVER=dummy` in the environment.

## Known gaps

- The title screen text is compiled in the port. The disc's `BODYPROG` title strings are not read by the port, so editing them on the disc does not change the title.
- Glyph and map message edits on the disc: the port source reads map messages from `VIN\*.BIN` when they differ from the compiled text, and loads the font from the disc. Not yet proven on a screen (see the status file).
- RetroAchievements needs the rcheevos commit above; without it the build fails to link.
