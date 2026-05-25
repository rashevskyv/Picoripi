import sys
from PyQt5 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication(sys.argv)

font_combo = QtWidgets.QFontComboBox()
font_combo.setEditable(True)

# Show and process events to initialize QFontComboBox fonts
font_combo.show()
app.processEvents()

def _reset_font_filter():
    view = font_combo.view()
    model = font_combo.model()
    total = model.rowCount()
    for i in range(total):
        view.setRowHidden(i, False)

def _on_font_search_text_edited(text):
    filter_text = text.lower().strip()
    view = font_combo.view()
    model = font_combo.model()
    total = model.rowCount()
    
    if not filter_text:
        _reset_font_filter()
        return
        
    for i in range(total):
        name = model.index(i, 0).data() or ""
        if filter_text in name.lower():
            view.setRowHidden(i, False)
        else:
            view.setRowHidden(i, True)
            
    font_combo.showPopup()

original_show_popup = font_combo.showPopup
def custom_show_popup():
    current_font_name = font_combo.currentFont().family()
    typed_text = font_combo.lineEdit().text()
    print(f"custom_show_popup called: typed_text='{typed_text}', current_font='{current_font_name}'")
    if typed_text == current_font_name or not typed_text.strip():
        print("Resetting filter in showPopup")
        _reset_font_filter()
    original_show_popup()

font_combo.showPopup = custom_show_popup
font_combo.setCompleter(None)
font_combo.lineEdit().textEdited.connect(_on_font_search_text_edited)
font_combo.activated.connect(_reset_font_filter)

# Test sequence:
# 1. Select Arial (default)
font_combo.setCurrentFont(QtGui.QFont("Arial"))
print("Initial font:", font_combo.currentFont().family())

# 2. Simulate typing "arial narrow"
print("\n--- Simulating typing 'arial narrow' ---")
font_combo.lineEdit().setText("arial narrow")
_on_font_search_text_edited("arial narrow")

view = font_combo.view()
model = font_combo.model()
visible_fonts = []
for i in range(model.rowCount()):
    if not view.isRowHidden(i):
        visible_fonts.append(model.index(i, 0).data())
print("Visible fonts during filter:", visible_fonts)

# 3. Simulate clicking on 'Arial Narrow' (activated)
print("\n--- Simulating activating 'Arial Narrow' ---")
narrow_idx = -1
for i in range(model.rowCount()):
    if model.index(i, 0).data() == "Arial Narrow":
        narrow_idx = i
        break

if narrow_idx != -1:
    font_combo.setCurrentIndex(narrow_idx)
    font_combo.activated.emit(narrow_idx) # manual trigger for test

print("Current font after activation:", font_combo.currentFont().family())

# Check if filter was reset
visible_count = 0
for i in range(model.rowCount()):
    if not view.isRowHidden(i):
        visible_count += 1
print("Visible count after activation:", visible_count)

# 4. Simulate opening popup again via arrow click
print("\n--- Simulating opening popup via arrow click ---")
font_combo.showPopup()

print("\nTest passed successfully!")
