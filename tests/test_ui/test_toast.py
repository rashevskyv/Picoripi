from PyQt6.QtWidgets import QWidget
from components.toast import ToastNotification

def test_toast_show_without_qapp(monkeypatch):
    # Mock QApplication.instance to return None
    from PyQt6.QtWidgets import QApplication
    monkeypatch.setattr(QApplication, "instance", lambda: None)
    
    res = ToastNotification.show_toast(None, "Test Message")
    assert res is None

def test_toast_creation_and_lifecycle(qapp):
    # Clean active toasts list
    ToastNotification._active_toasts.clear()
    
    parent = QWidget()
    toast = ToastNotification.show_toast(parent, "Test Message", duration=100)
    
    assert toast is not None
    assert toast.message == "Test Message"
    assert toast in ToastNotification._active_toasts
    
    # Trigger cleanup manually to test ref removal
    toast.close_and_cleanup()
    assert toast not in ToastNotification._active_toasts
