import os
from PyQt6.QtWidgets import QMessageBox
from utils.logging_utils import log_error

class MemePalacePipelineMixin:
    """Orchestration pipeline execution mixin for MemePalaceBuilderDialog."""

    def _save_pipeline_state(self):
        """Persist current pipeline session variables into global settings."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_pipeline_running", self.pipeline_running)
                sm.set("mempalace_pipeline_step", self.pipeline_step)
                sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                sm.save_settings()
                
                # Keep local variables in sync
                self.saved_pipeline_running = self.pipeline_running
                self.saved_pipeline_step = self.pipeline_step
                self.saved_pipeline_wing = self.wing_edit.text().strip()
                self.saved_pipeline_script = self.file_path_edit.text().strip()
        except Exception as e:
            log_error(f"Failed to save pipeline state: {e}")

    def _start_complete_pipeline(self):
        """Start or resume the complete MemePalace orchestration pipeline sequentially."""
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        has_saved = getattr(self, "saved_pipeline_running", False) and getattr(self, "saved_pipeline_step", 0) > 0
        
        if has_saved:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Resume Pipeline Session")
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setText(
                f"An incomplete MemePalace pipeline session was found at Step {self.saved_pipeline_step}/4.\n\n"
                f"Do you want to continue the session from Step {self.saved_pipeline_step} or start a new session from the beginning?"
            )
            
            continue_btn = msg_box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
            start_over_btn = msg_box.addButton("Start Over", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.setDefaultButton(continue_btn)
            msg_box.exec()
            
            clicked = msg_box.clickedButton()
            if clicked == cancel_btn:
                return
            elif clicked == start_over_btn:
                self.pipeline_running = True
                self.pipeline_step = 1
            else:
                self.pipeline_running = True
                self.pipeline_step = self.saved_pipeline_step
                if getattr(self, "saved_pipeline_wing", ""):
                    self.wing_edit.setText(self.saved_pipeline_wing)
                if getattr(self, "saved_pipeline_script", "") and os.path.exists(self.saved_pipeline_script):
                    self.file_path_edit.setText(self.saved_pipeline_script)
        else:
            reply = QMessageBox.question(
                self, "Run Complete Pipeline",
                "This will sequentially execute all MemePalace steps step-by-step:\n"
                "1. Mine Characters & Terms via AI\n"
                "2. Map BMG to Script Chapters\n"
                "3. AI Analyze All Chapters\n"
                "4. AI Profile Characters Speech\n\n"
                "This process can take several minutes. Do you want to start the complete pipeline?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.pipeline_running = True
            self.pipeline_step = 1

        self.append_log(">>> STARTING COMPLETE MEMEPALACE PIPELINE <<<")
        self._maybe_prevent_sleep()
        self._save_pipeline_state()
        self._run_pipeline_current_step()

    def _run_pipeline_current_step(self):
        """Internal helper to run pipeline current step."""
        if not self.pipeline_running:
            return

        file_path = self.file_path_edit.text().strip()
        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            self._abort_pipeline("AI Provider unavailable.")
            return

        # Reset chapter analysis counts for other steps to prevent progress calculations bug
        if self.pipeline_step != 3:
            self.analysis_total_count = 0
            self.analysis_completed_count = 0

        if self.pipeline_step == 1:
            self.append_log("--- STEP 1/4: Mining Characters & Terms via AI ---")
            self._pre_analyze_script_via_ai_core(file_path, ai_provider)
        elif self.pipeline_step == 2:
            self.append_log("--- STEP 2/4: Mapping BMG to Script Chapters ---")
            self._start_chapters_mapping_core(file_path)
        elif self.pipeline_step == 3:
            self.append_log("--- STEP 3/4: Analyzing All Chapters via AI ---")
            self._analyze_all_chapters_core()
        elif self.pipeline_step == 4:
            self.append_log("--- STEP 4/4: Profiling Characters Speech via AI ---")
            self._profile_characters_speech_via_ai_core(ai_provider)

    def _advance_pipeline(self):
        """Internal helper to advance pipeline."""
        if not getattr(self, "pipeline_running", False):
            return

        self.pipeline_step += 1
        if self.pipeline_step <= 4:
            self._save_pipeline_state()
            self._run_pipeline_current_step()
        else:
            self.pipeline_running = False
            self.pipeline_step = 0
            self._save_pipeline_state()
            self._set_ui_enabled(True)
            self.progress_bar.setValue(100)
            self.append_log(">>> COMPLETE MEMEPALACE PIPELINE FINISHED SUCCESSFULLY! <<<")
            QMessageBox.information(
                self, "Pipeline Success",
                "Congratulations! The complete MemePalace context orchestration pipeline completed successfully!\n\n"
                "All characters mined, dialogue lines mapped to story chapters, AI chapter summaries generated, "
                "and character speech profiles fully synthesized and loaded into the Glossary!"
            )
            self._finish_and_maybe_sleep()
            self._update_pipeline_btn_text()

    def _abort_pipeline(self, error_message):
        """Internal helper to abort pipeline."""
        step = getattr(self, "pipeline_step", 1)
        
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_pipeline_running", True)
                sm.set("mempalace_pipeline_step", step)
                sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                sm.save_settings()
                
                self.saved_pipeline_running = True
                self.saved_pipeline_step = step
                self.saved_pipeline_wing = self.wing_edit.text().strip()
                self.saved_pipeline_script = self.file_path_edit.text().strip()
        except Exception:
            pass

        self.pipeline_running = False
        self.pipeline_step = 0
        self._set_ui_enabled(True)
        self.progress_bar.setValue(0)
        self.append_log(f">>> PIPELINE ABORTED DUE TO ERROR AT STEP {step}: {error_message} <<<")
        QMessageBox.warning(
            self, "Pipeline Failed",
            f"MemePalace Pipeline aborted at Step {step} due to error:\n{error_message}"
        )
        self._finish_and_maybe_sleep()
        self._update_pipeline_btn_text()
