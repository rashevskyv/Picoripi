from components.ai_chat_dialog import AIChatDialog, _ChatTab

def test_ai_chat_dialog_tab_and_controls(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    tab = dialog.add_new_tab()
    assert isinstance(tab, _ChatTab)
    assert tab.status_label is not None
    assert tab.queue_bar is not None
    assert tab.stop_button is not None
    assert not tab.stop_button.isVisible()
    assert not tab.queue_bar.isVisible()
    assert tab.send_button.width() >= 105
    assert tab.stop_button.width() >= 105
    assert tab.send_button.width() == tab.stop_button.width()

def test_chat_tab_generating_toggle(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    tab = dialog.add_new_tab()

    tab.set_generating(True)
    assert not tab.stop_button.isHidden()
    assert tab.stop_button.isEnabled()
    assert tab.send_button.height() == 68
    assert tab.send_button.width() >= 105

    tab.set_generating(False)
    assert tab.stop_button.isHidden()
    assert not tab.stop_button.isEnabled()
    assert tab.send_button.height() == 100
    assert tab.send_button.width() >= 105

def test_chat_tab_queue_count(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    tab = dialog.add_new_tab()

    tab.set_queue_count(2)
    assert not tab.queue_bar.isHidden()
    assert '2' in tab.queue_label.text()

    tab.set_queue_count(0)
    assert tab.queue_bar.isHidden()

def test_dialog_helper_methods(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    tab = dialog.add_new_tab()

    dialog.set_tab_status(0, 'Connecting... (5s)')
    assert tab.status_label.text() == 'Connecting... (5s)'

    dialog.set_tab_generating(0, True)
    assert not tab.stop_button.isHidden()

    dialog.set_tab_queue_count(0, 1)
    assert not tab.queue_bar.isHidden()


def test_chat_tab_scroll_and_text_operations(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.resize(500, 400)
    dialog.show()
    tab = dialog.add_new_tab()

    for i in range(40):
        tab.history_view.append(f"User line {i}")

    end_pos = dialog.get_tab_document_end_pos(0)
    assert end_pos > 0
    assert end_pos == tab.get_document_end_pos()

    dialog.scroll_to_response(0, end_pos // 2)
    # Scrollbar moved
    sb = tab.history_view.verticalScrollBar()
    dialog.scroll_to_bottom(0)
    assert dialog.is_tab_at_bottom(0)
    assert tab.is_at_bottom()

    dialog.insert_tab_stream_chunk(0, "AI streamed text with 'quotes' & symbols", auto_scroll=True)
    assert "AI streamed text with 'quotes' & symbols" in tab.history_view.toPlainText()

    dialog.remove_tab_text_after(0, end_pos)
    assert "AI streamed text" not in tab.history_view.toPlainText()


def test_chat_tab_reset_context_and_bottom_buttons(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.resize(500, 400)
    dialog.show()
    tab = dialog.add_new_tab()

    assert tab.reset_context_button is not None
    assert tab.scroll_bottom_button is not None
    assert tab.floating_bottom_btn is not None

    with qtbot.waitSignal(dialog.reset_context_requested, timeout=1000):
        tab.reset_context_button.click()

    for i in range(50):
        tab.history_view.append(f"Chat line {i}")
    tab.history_view.verticalScrollBar().setValue(0)
    tab._update_floating_bottom_btn()

    assert tab.floating_bottom_btn.isVisible()
    tab.floating_bottom_btn.click()
    assert tab.is_at_bottom()
    assert not tab.floating_bottom_btn.isVisible()

    # When generating, reset context should be disabled
    tab.set_generating(True)
    assert not tab.reset_context_button.isEnabled()
    tab.set_generating(False)
    assert tab.reset_context_button.isEnabled()


def test_ai_chat_dialog_window_flags_and_independent_window(qtbot):
    from PyQt6.QtCore import Qt
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.Window == Qt.WindowType.Window
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint != 0
    assert flags & Qt.WindowType.WindowCloseButtonHint != 0
    assert dialog.parent() is None


def test_chat_tab_retry_button(qtbot):
    dialog = AIChatDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    tab = dialog.add_new_tab()

    assert hasattr(tab, 'retry_button')
    assert tab.retry_button is not None
    # Initially not visible
    assert tab.retry_button.isHidden()
    assert tab.send_button.height() == 100
    assert tab.retry_button.width() >= 105
    assert tab.retry_button.width() == tab.send_button.width()

    # Enable retry
    tab.set_can_retry(True, last_message="Hello world to retry")
    assert not tab.retry_button.isHidden()
    assert tab.retry_button.isEnabled()
    assert tab.send_button.height() == 68
    assert "Hello world to retry" in tab.retry_button.toolTip()

    # When generating, retry button is hidden and stop button is shown
    tab.set_generating(True)
    assert tab.retry_button.isHidden()
    assert not tab.stop_button.isHidden()
    assert tab.send_button.height() == 68

    # When generation finishes, retry button is restored
    tab.set_generating(False)
    assert not tab.retry_button.isHidden()
    assert tab.stop_button.isHidden()
    assert tab.send_button.height() == 68

    # Clicking retry emits signal from dialog
    with qtbot.waitSignal(dialog.retry_requested, timeout=1000) as blocker:
        tab.retry_button.click()
    assert blocker.args == [0]

    # Disable retry
    tab.set_can_retry(False)
    assert tab.retry_button.isHidden()
    assert tab.send_button.height() == 100
