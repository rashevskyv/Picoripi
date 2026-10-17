"""The in-place layouts of the 3DS system strings on the owner's files (env PICORIPI_ROMHACKING).

A label of the browser (user data names the pane) and the System Settings startup line (a line baked in the layout)
are drawn from the owner's romfs; the pane is outlined in the picture.
"""
import romhacking_root
from plugins.system_3ds import layout_render as lr
from plugins.system_3ds import preview_panel
from plugins.system_3ds.rules import GameRules

REPO = ("_shared", "3ds_sysfont_ua", "repo_manual")
FONT = REPO + ("work", "0004009B00014002", "cbf_std.bcfnt.lz")

pytestmark = romhacking_root.needs(FONT)


def _root():
    return str(romhacking_root.path(*REPO))


def _outline_pixels(image):
    return sum(1 for pixel in image.getdata() if pixel == lr.OUTLINE)


def test_a_label_of_the_browser_is_drawn_in_its_pane_and_the_pane_is_outlined():
    rules = GameRules()
    request = preview_panel._Request(_root(), "Ім'я користувача:", 157, 1, "", rules.line_widths_of, "browser",
                                     "Option_ProxyUserID")
    shown = preview_panel.draw_request(request, lambda: False)
    assert shown.image.size == (320, 240)
    assert shown.status.startswith("In place: pane UserIdTxb")
    assert _outline_pixels(shown.image) > 0


def test_the_startup_line_of_system_settings_is_drawn_in_place():
    rules = GameRules()
    key = "up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0"
    request = preview_panel._Request(_root(), "Виберіть мову.", 342, 1, "", rules.line_widths_of, "system_settings",
                                     key)
    shown = preview_panel.draw_request(request, lambda: False)
    assert shown.image.size == (400, 240)
    assert "TextBoxTitle_00" in shown.status
    assert "Other languages of the pane are drawn as stored." in shown.status
