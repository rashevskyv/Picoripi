import json

from PyQt6.QtWidgets import QDialog, QMessageBox

from handlers.translation.glossary.dialogs import CategorySelectionDialog
from core.i18n import tr


class ClassifyMixin:
    def classify_glossary_via_ai(self) -> None:
        """Classify glossary via ai."""
        entries = self.glossary_manager.get_entries()
        if not entries:
            QMessageBox.information(self.mw, tr('Glossary'), tr('No glossary entries to classify.'))
            return

        provider = self.mw.translation_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return

        # 1. Start Stage 1: Ask AI to suggest categories
        terms_list = "\n".join(f"- {e.original} -> {e.translation}" for e in entries[:150]) # limit to 150 for safety
        
        system_prompt = (
            "You are an expert game translation director. Your task is to analyze a list of glossary terms "
            "and suggest a set of 4 to 7 highly relevant thematic categories (such as 'Characters', 'Items', "
            "'Locations', 'Magic', 'Other') to organize them."
        )
        user_prompt = f"""
Analyze the following list of glossary terms:
{terms_list}

Suggest 4 to 7 thematic categories to organize these terms. Common categories include: "Characters", "Items", "Locations", "Magic", "Other".
Return the response STRICTLY as a valid JSON list of strings (e.g., ["Characters", "Items", "Locations", "Magic", "Other"]).
Do not write any markdown formatting like ```json, just output raw JSON text.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        task_details = {
            "type": "classify_suggest_types",
            "precomposed_prompt": messages,
            "attempt": 1,
            "max_retries": 1,
            "dialog_steps": ["Analyzing glossary terms...", "Choosing categories...", "Classifying terms...", "Finished!"],
            "entries": entries
        }
        
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Analyze", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_classify_suggest_success(self, response, context: dict) -> None:
        """Internal helper to handle classify suggest success."""
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.mw.translation_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        
        try:
            suggested_categories = json.loads(cleaned)
            if not isinstance(suggested_categories, list):
                suggested_categories = ["Characters", "Items", "Locations", "Magic", "Other"]
        except Exception:
            suggested_categories = ["Characters", "Items", "Locations", "Magic", "Other"]
            
        # Show Category Selection Dialog
        dialog = CategorySelectionDialog(self.dialog, suggested_categories)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        selected_categories = dialog.get_selected_categories()
        if not selected_categories:
            QMessageBox.information(self.dialog, tr('Glossary'), tr('No categories selected. Operation cancelled.'))
            return
            
        # 2. Start Stage 2: Classify terms into selected categories
        provider = self.mw.translation_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return
            
        entries = context.get("entries", [])
        terms_data = [{"original": e.original, "translation": e.translation, "notes": e.notes} for e in entries]
        terms_json = json.dumps(terms_data, ensure_ascii=False)
        categories_str = ", ".join(f'"{c}"' for c in selected_categories)
        
        system_prompt = (
            "You are an expert game translation director. Your task is to classify a list of glossary terms "
            f"into the following categories: {categories_str}."
        )
        user_prompt = f"""
Classify each of the following glossary terms into exactly one of these categories: {categories_str}.
If a term fits multiple categories, assign it to the most relevant one. If it doesn't fit any of the specific categories, assign it to "Other".

Glossary terms to classify:
{terms_json}

Respond STRICTLY in JSON format as a dictionary where the keys are the original terms and the values are their assigned category from the list.
Do not write any markdown code blocks (like ```json), just output the raw JSON dictionary.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        task_details = {
            "type": "classify_apply",
            "precomposed_prompt": messages,
            "attempt": 1,
            "max_retries": 1,
            "dialog_steps": ["Analyzing glossary terms...", "Choosing categories...", "Classifying terms...", "Finished!"],
            "entries": entries,
            "selected_categories": selected_categories
        }
        
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Classify", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_classify_apply_success(self, response, context: dict) -> None:
        """Internal helper to handle classify apply success."""
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.mw.translation_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        
        try:
            classification_map = json.loads(cleaned)
        except Exception as e:
            QMessageBox.warning(self.dialog, tr('AI Error'), f"Failed to parse AI classification: {e}")
            return
            
        if not isinstance(classification_map, dict):
            QMessageBox.warning(self.dialog, tr('AI Error'), tr('AI did not return a valid dictionary mapping terms to categories.'))
            return
            
        # Update glossary manager categories (sections)
        updated_count = 0
        entries = context.get("entries", [])
        for entry in entries:
            assigned_cat = classification_map.get(entry.original)
            if assigned_cat:
                self.glossary_manager.update_entry(
                    original=entry.original,
                    translation=entry.translation,
                    notes=entry.notes,
                    section=assigned_cat
                )
                updated_count += 1
                
        # Save updated glossary to disk
        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()
        
        # Hot-reload in glossary dialog if visible
        if self.dialog:
            new_entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            occurrence_map = self.glossary_manager.get_occurrence_map()
            self.dialog.reload_data(new_entries, occurrence_map)
            
        QMessageBox.information(
            self.dialog if self.dialog else self.mw,
            tr('Success'),
            f"Successfully organized {updated_count} glossary terms into categories!"
        )

    def _handle_classify_error(self, error_message: str, context: dict) -> None:
        """Internal helper to handle classify error."""
        self.main_handler.ui_handler.finish_ai_operation()
        msg = error_message or "AI request failed."
        QMessageBox.warning(self.dialog if self.dialog else self.mw, tr('AI Error'), msg)

