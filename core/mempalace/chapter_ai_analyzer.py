from PyQt6.QtCore import QThread, pyqtSignal
from core.mempalace_client import MemePalaceClient
from core.translation.providers import ProviderResponse
from utils.logging_utils import log_error, log_ai_traffic


class MemePalaceChapterAIAnalyzerWorker(QThread):
    """Meme palace chapter a i analyzer worker implementation."""
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: MemePalaceClient, ai_provider, chapter_id: int, num: str, title: str, content: str, start_line: int = 1, target_lang: str = "Ukrainian", mw=None):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.ai_provider = ai_provider
        self.chapter_id = chapter_id
        self.num = num
        self.title = title
        self.content = content
        self.start_line = start_line
        self.target_lang = target_lang
        self.mw = mw
        self.is_cancelled = False

    def cancel(self):
        """Cancel."""
        self.is_cancelled = True

    def run(self):
        """Run."""
        try:
            self.log.emit(f"Analyzing Chapter {self.num}: {self.title} via AI...")
            self.progress.emit(0, 100, "Preparing prompt...")
            
            if not self.ai_provider:
                self.finished.emit(False, "No AI Provider configured.")
                return

            # Number the lines of the content sequentially starting from start_line
            lines = self.content.splitlines()
            numbered_lines = []
            for i, line in enumerate(lines):
                actual_line_num = self.start_line + i
                numbered_lines.append(f"{actual_line_num}: {line}")
            
            content_snippet = "\n".join(numbered_lines)
            if len(content_snippet) > 35000:
                content_snippet = content_snippet[:35000] + "\n\n[TRUNCATED FOR LENGTH...]"

            target_lang = self.target_lang
            system_prompt = (
                "You are an expert game narrative architect. Your task is to analyze a game script chapter "
                "and divide it into logical, sequential story events (micro-scenes or narrative events) with precise line ranges. "
                "Format your entire response as a single valid JSON array of objects. Each object must have fields: "
                "'start_line', 'end_line', 'event_name', and 'summary_translated'. Ensure that there are no line gaps between events, "
                "and they cover the entire chapter sequentially."
            )
            
            user_prompt = f"""
Analyze the following game script chapter where each line is prefixed with its actual script file line number.
Divide this chapter into sequential, logical narrative events (scenes or plot points).
For each event, determine the start line and end line numbers and write a brief, 1-2 sentence summary of what is happening in {target_lang}.

CHAPTER: Chapter {self.num} - {self.title}

SCRIPT TEXT:
{content_snippet}

Your output must be a valid JSON array of objects. Do not wrap the JSON in markdown formatting (do not use ```json). Return ONLY the raw JSON string.
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            self.progress.emit(30, 100, "Sending request to AI...")
            self.log.emit("Sending request to AI provider. This might take 10-20 seconds...")
            
            log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages)
            try:
                response: ProviderResponse = self.ai_provider.translate(
                    messages, session=None, settings_override={"think": 1, "timeout": 300}
                )
                log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages, response_text=response.text)
            except Exception as e_ch:
                log_ai_traffic(self.mw, "mempalace_chapter_analysis", messages, error=str(e_ch))
                raise e_ch
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled.")
                return

            summary = response.text.strip()
            if not summary:
                self.finished.emit(False, "Received empty summary from AI.")
                return

            # Clean json formatting tags if any
            cleaned_json = summary
            if cleaned_json.startswith("```"):
                lines_json = cleaned_json.splitlines()
                if lines_json[0].startswith("```"):
                    lines_json = lines_json[1:]
                if lines_json and lines_json[-1].startswith("```"):
                    lines_json = lines_json[:-1]
                cleaned_json = "\n".join(lines_json).strip()

            self.progress.emit(80, 100, "Saving summary to database...")
            self.client.save_chapter_summary(self.chapter_id, cleaned_json)

            self.progress.emit(100, 100, "Analysis complete!")
            self.finished.emit(True, f"Chapter {self.num} successfully analyzed and saved.")

        except Exception as e:
            log_error(f"Error in MemePalaceChapterAIAnalyzerWorker: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {e}")
