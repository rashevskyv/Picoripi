"""Text box scale: patch values, effective scale after rounding, expected-byte checks. Synthetic ROM bytes only."""
import pytest

from plugins.conker_bfd import box_scale as bs, code_patches as cp, n64_archive as na


def _rom_with_original_divisors():
    rom = bytearray(b"\x00" * 0x4000)
    rom[bs.X_OFFSET:bs.X_OFFSET + 2] = bs.X_EXPECTED
    rom[bs.Y_OFFSET:bs.Y_OFFSET + 2] = bs.Y_EXPECTED
    return bytes(rom)


def test_scale_one_gives_no_patches_and_the_same_rom():
    assert bs.scale_patches(1.0) == ()
    rom = _rom_with_original_divisors()
    assert cp.apply_raw(rom, bs.scale_patches(1.0)) is rom


def test_a_larger_box_patches_both_divisors_within_rounding():
    patches = bs.scale_patches(1.25)
    assert [p.offset for p in patches] == [bs.X_OFFSET, bs.Y_OFFSET]
    assert [p.expected for p in patches] == [bs.X_EXPECTED, bs.Y_EXPECTED]
    width, height = bs.effective_scale(1.25)
    assert abs(width - 1.25) / 1.25 < 0.01
    assert abs(height - 1.25) / 1.25 < 0.01


def test_the_patched_rom_carries_the_new_divisors():
    patched = cp.apply_raw(_rom_with_original_divisors(), bs.scale_patches(1.25))
    assert patched[bs.X_OFFSET:bs.X_OFFSET + 2] == bs.scale_patches(1.25)[0].new
    assert patched[bs.Y_OFFSET:bs.Y_OFFSET + 2] == bs.scale_patches(1.25)[1].new


def test_a_smaller_box_moves_the_scale_the_other_way():
    width, _ = bs.effective_scale(0.5)
    assert abs(width - 0.5) / 0.5 < 0.01


def test_a_non_positive_scale_is_refused():
    with pytest.raises(ValueError):
        bs.scale_patches(0.0)
    with pytest.raises(ValueError):
        bs.scale_patches(-1.0)


def test_bytes_that_differ_from_the_expected_divisor_are_refused():
    rom = bytearray(_rom_with_original_divisors())
    rom[bs.X_OFFSET:bs.X_OFFSET + 2] = b"\x12\x34"
    with pytest.raises(na.RomError):
        cp.apply_raw(bytes(rom), bs.scale_patches(1.25))
