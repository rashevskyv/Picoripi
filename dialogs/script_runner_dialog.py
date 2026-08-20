import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel, QMessageBox, QLineEdit
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

class ScriptRunnerDialog(QDialog):
    def __init__(self, parent, script_path: str):
        super().__init__(parent)
        self.script_path = script_path
        self.setWindowTitle("External Script Execution")
        self.resize(750, 480)
        self.setMinimumSize(500, 300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        
        self.process = None
        self.setup_ui()
        self.start_script()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header showing status and script path
        self.status_label = QLabel("Starting external script...", self)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")
        layout.addWidget(self.status_label)
        
        path_label = QLabel(f"Script: {self.script_path}", self)
        path_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        
        # Console output area
        self.console_edit = QPlainTextEdit(self)
        self.console_edit.setReadOnly(True)
        
        # Console Styling: Dark theme terminal look
        self.console_edit.setStyleSheet(
            "background-color: #121212; color: #e5e7eb; border: 1px solid #374151; border-radius: 4px;"
        )
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Monospace", 10)
        self.console_edit.setFont(font)
        layout.addWidget(self.console_edit)
        
        # Interactive stdin layout (input field + Send button)
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Type input for script here and press Enter to send...")
        self.input_edit.setStyleSheet(
            "background-color: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 6px; font-family: Consolas, monospace;"
        )
        self.input_edit.returnPressed.connect(self.send_input)
        self.input_edit.setEnabled(False)
        input_layout.addWidget(self.input_edit)
        
        self.send_button = QPushButton("Send", self)
        self.send_button.setToolTip(
            "<b>Send</b><br>"
            "Click — pass the typed line to the running script's standard input "
            "(Enter in the input field does the same).<br>"
            "Enabled only while a process is running."
        )
        self.send_button.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;"
        )
        self.send_button.clicked.connect(self.send_input)
        self.send_button.setEnabled(False)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Footer buttons (Stop, Close)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.stop_button = QPushButton("Stop Process", self)
        self.stop_button.setToolTip(
            "<b>Stop process</b><br>"
            "Click — terminate the running script. Output produced so far stays in "
            "the log."
        )
        self.stop_button.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        btn_layout.addWidget(self.stop_button)
        
        self.close_button = QPushButton("Close", self)
        self.close_button.setToolTip(
            "<b>Close</b><br>"
            "Click — close this window. Stop the process first if it is still "
            "running."
        )
        self.close_button.setStyleSheet("padding: 6px 12px; border-radius: 4px;")
        self.close_button.clicked.connect(self.close)
        btn_layout.addWidget(self.close_button)
        
        layout.addLayout(btn_layout)

    def start_script(self):
        script_dir = os.path.dirname(self.script_path)
        
        self.process = QProcess(self)
        self.process.setWorkingDirectory(script_dir)
        
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)
        self.process.errorOccurred.connect(self.handle_error)
        
        self.status_label.setText("Running script...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #d97706;") # Orange for running
        self.stop_button.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_edit.setFocus()
        
        # Set environment variables
        env = self.process.processEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        
        is_batch = self.script_path.lower().endswith(('.bat', '.cmd'))
        if is_batch and os.name == 'nt':
            self.process.start("cmd.exe", ["/c", self.script_path])
        else:
            self.process.start(self.script_path)

    def append_output(self, text: str, is_error: bool = False, is_input: bool = False):
        cursor = self.console_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Format stdout vs stderr vs user input
        fmt = QTextCharFormat()
        if is_input:
            fmt.setForeground(QColor("#38bdf8"))  # Cyan for user input
            fmt.setFontWeight(QFont.Weight.Bold.value)
        elif is_error:
            fmt.setForeground(QColor("#f87171"))  # Red-ish
        else:
            fmt.setForeground(QColor("#4ade80"))  # Light green-ish
            
        cursor.insertText(text, fmt)
        self.console_edit.setTextCursor(cursor)
        self.console_edit.ensureCursorVisible()

    def send_input(self):
        if not self.process or self.process.state() != QProcess.ProcessState.Running:
            return
            
        text = self.input_edit.text()
        # Append input text to console so user sees what they typed
        self.append_output(text + "\n", is_input=True)
        
        # Try to encode with regional encoding on Windows, fallback to utf-8
        encoding = "utf-8"
        if os.name == 'nt':
            encoding = "cp1251"
            
        try:
            data = (text + "\n").encode(encoding)
        except Exception:
            try:
                data = (text + "\n").encode("utf-8")
            except Exception:
                data = (text + "\n").encode("utf-8", errors="ignore")
                
        self.process.write(data)
        self.input_edit.clear()

    def _decode_data(self, data) -> str:
        try:
            return data.data().decode("utf-8")
        except UnicodeDecodeError:
            try:
                return data.data().decode("cp1251")
            except UnicodeDecodeError:
                try:
                    return data.data().decode("cp866")
                except UnicodeDecodeError:
                    return data.data().decode("utf-8", errors="replace")

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        text = self._decode_data(data)
        self.append_output(text, is_error=False)

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        text = self._decode_data(data)
        self.append_output(text, is_error=True)

    def handle_finished(self, exit_code, exit_status):
        self.stop_button.setEnabled(False)
        self.input_edit.setEnabled(False)
        self.send_button.setEnabled(False)
        if exit_status == QProcess.ExitStatus.NormalExit:
            if exit_code == 0:
                self.status_label.setText("Success: Script finished successfully!")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a34a;") # Green
            else:
                self.status_label.setText(f"Error: Script exited with code {exit_code}")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;") # Red
        else:
            self.status_label.setText("Crashed: Script crashed or was stopped.")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")

    def handle_error(self, error):
        self.stop_button.setEnabled(False)
        self.input_edit.setEnabled(False)
        self.send_button.setEnabled(False)
        err_msg = self.process.errorString()
        self.append_output(f"\n[Process Error]: {err_msg}\n", is_error=True)
        self.status_label.setText("Error: Failed to execute script.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")

    def stop_process(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self,
                "Stop Process",
                "Are you sure you want to terminate the running script?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.process.terminate()
                if not self.process.waitForFinished(2000):
                    self.process.kill()

    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self,
                "Script Still Running",
                "The script is still running. Would you like to terminate it and close the window?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.process.terminate()
                if not self.process.waitForFinished(2000):
                    self.process.kill()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
