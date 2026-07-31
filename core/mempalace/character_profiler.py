import json
import re
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Any, Optional, Tuple
from core.mempalace_client import MemePalaceClient
from core.translation.providers import BaseTranslationProvider
from utils.logging_utils import log_error, log_ai_traffic, log_warning, log_info
from .weaver_worker import robust_json_loads
from core.tag_utils import ANY_TAG_PATTERN


class MemePalaceCharacterProfilerWorker(QThread):
    """Meme palace character profiler worker implementation."""
    # Signals for UI communication
    progress = pyqtSignal(int, int, str)  # current, total, status
    log = pyqtSignal(str)                 # log message
    finished = pyqtSignal(bool, str)      # success, message

    def __init__(self, 
                 client: MemePalaceClient, 
                 ai_provider: BaseTranslationProvider, 
                 wing_name: str = "Zelda_TP",
                 glossary_manager: Optional[Any] = None,
                 target_lang: str = "Ukrainian",
                 plugin_name: Optional[str] = None,
                 composer: Optional[Any] = None,
                 mw=None):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.glossary_manager = glossary_manager
        self.target_lang = target_lang
        self.plugin_name = plugin_name
        self.composer = composer
        self.mw = mw or (getattr(composer, 'mw', None) if composer else None) or (getattr(glossary_manager, 'mw', None) if glossary_manager else None)
        self.is_cancelled = False

    def cancel(self):
        """Cancel."""
        self.is_cancelled = True
        self.log.emit("Character speech profiling cancellation requested...")

    def _fetch_external_lore(self, char_name: str) -> str:
        """Background lore about a character, from wherever the plugin keeps it.

        The engine does not know what that source is -- a wiki, a guide, nothing
        at all. It asks, and translates whatever English prose comes back.
        A plugin without a lore source simply grounds the profile in the script.
        """
        rules = getattr(self.mw, "current_game_rules", None)
        getter = getattr(rules, "get_external_lore", None)
        if not callable(getter):
            return ""
        try:
            lore = getter(char_name)
        except Exception as exc:
            log_warning(f"External lore lookup failed for '{char_name}': {exc}")
            return ""
        if not lore or not str(lore).strip():
            return ""
        # Lore may arrive with a "Page: <title>" header naming its source page.
        title, _, body = str(lore).partition("\n")
        title = title[len("Page: "):] if title.startswith("Page: ") else char_name
        return self._translate_wiki_to_target_lang(title, (body or "").strip())

    def _translate_wiki_to_target_lang(self, title: str, text: str) -> str:
        """Render the plugin's English lore into the target language.

        Kept in the engine: the AI provider and the target language live here,
        and this step is the same whatever source the lore came from.
        """
        if not text or not text.strip():
            return ""
        
        # If target language is already English, no translation needed
        if self.target_lang.strip().lower() == "english":
            return f"Page: {title}\n{text}"
            
        if self.target_lang.strip().lower() == "ukrainian":
            system_prompt = (
                "Ви — професійний перекладач відеоігор та редактор локалізації. Ваше завдання — зробити точний, "
                "літературний переклад вступного опису персонажа з англомовного довідника на українську мову. "
                "Переклад має бути максимально природним та художнім."
            )
            user_prompt = f"""
Перекладіть наступний опис персонажа '{title}' на українську мову:

{text}

Поверніть ЛИШЕ готовий переклад українською мовою. Не додавайте жодних вступних чи пояснювальних фраз.
"""
        else:
            system_prompt = (
                f"You are an expert game translation editor. Translate the provided character description "
                f"from English into {self.target_lang}. Keep it highly professional and natural."
            )
            user_prompt = f"""
Translate the following character description for '{title}' into {self.target_lang}:

{text}

Return ONLY the translated text. Do not add any introduction or meta comments.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            response = self.ai_provider.translate(messages, session=None)
            translated = response.text.strip()
            log_info(f"Successfully translated background lore for '{title}' to {self.target_lang}")
            return f"Page: {title}\n{translated}"
        except Exception as e:
            log_error(f"Failed to translate background lore for '{title}': {e}")
            return f"Page: {title} (Original English Context)\n{text}"

    def _load_plugin_prompts(self) -> dict:
        """Load prompts.json for active plugin if available."""
        from pathlib import Path
        prompts_data = {}
        if self.plugin_name:
            prompts_path = Path("plugins") / self.plugin_name / "translation_prompts" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("plugins") / "common" / "defaults" / "prompts.json"
            if not prompts_path.exists():
                prompts_path = Path("translation_prompts") / "prompts.json"
            
            if prompts_path.exists():
                try:
                    prompts_data = json.loads(prompts_path.read_text("utf-8"))
                except Exception as e_load:
                    log_error(f"Failed to load prompts.json for plugin {self.plugin_name}: {e_load}")
        return prompts_data

    def _get_glossary_context_for_character(self, char_name: str) -> tuple[Optional[Any], str]:
        """Return an existing glossary entry and a compact context block for a character."""
        if not self.glossary_manager or not char_name:
            return None, ""

        entry = None
        try:
            entry = self.glossary_manager.get_entry(char_name)
        except Exception:
            entry = None

        if entry is None:
            try:
                normalize = getattr(self.glossary_manager, "normalize_term", None)
                normalize = normalize if callable(normalize) else (lambda value: str(value or "").casefold().strip())
                target = normalize(char_name)
                for candidate in self.glossary_manager.get_entries():
                    if normalize(getattr(candidate, "translation", "")) == target:
                        entry = candidate
                        break
            except Exception:
                entry = None

        if entry is None:
            return None, ""

        notes = str(getattr(entry, "notes", "") or "").strip()
        translation = str(getattr(entry, "translation", "") or "").strip()
        section = str(getattr(entry, "section", "") or "").strip()
        parts = [
            f"Original: {getattr(entry, 'original', char_name)}",
            f"Translation: {translation or char_name}",
        ]
        if section:
            parts.append(f"Category: {section}")
        if notes:
            parts.append(f"Notes: {notes}")
        return entry, "\n".join(parts)

    def _get_synthesis_prompts(self, term_name: str, existing_notes: str, details: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve Synthesis prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        s_sys = m_section.get("synthesis_system_prompt")
        s_usr = m_section.get("synthesis_user_prompt")

        if s_sys and s_usr:
            return s_sys.format(target_lang=self.target_lang), s_usr.format(
                term_name=term_name,
                existing_notes=existing_notes,
                details=details,
                target_lang=self.target_lang
            )

        if self.target_lang.strip().lower() == "ukrainian":
            synth_system_prompt = (
                "Ви — професійний лексикограф та перекладач відеоігор. Ваше завдання — об'єднати існуючі нотатки/опис "
                "персонажа у глосарії з новим детальним аналізом його стилю мовлення та характеру від ШІ. Ви повинні синтезувати їх "
                "у один зв'язний, високоякісний, структурований та детальний опис (notes), написаний виключно українською мовою."
            )
            synth_user_prompt = f"""
Синтезуйте наступну інформацію для персонажа '{term_name}':

Існуючий опис у глосарії (нотатки):
{existing_notes}

Нові деталі аналізу мовлення та характеру від ШІ:
{details}

Створіть єдиний, красиво структурований та детальний опис, написаний виключно українською мовою. Уникайте повторень.
Збережіть увесь попередній контекст, обов'язково переклавши його українською мовою (якщо він був англійською), та гармонійно інтегруйте нову інформацію про характер, манеру мовлення, форми звертання та особливості перекладу.
Не повертайте нічого, крім фінального синтезованого тексту українською мовою. Не загортайте в блоки markdown або JSON. Поверніть лише чистий текст опису.
"""
        else:
            synth_system_prompt = (
                f"You are an expert game translation lexicographer. Your task is to combine the existing glossary entry notes "
                f"with new speech analysis insights. You must synthesize them into one coherent, premium, well-structured, "
                f"highly detailed description (notes) written strictly in {self.target_lang}."
            )
            synth_user_prompt = f"""
Synthesize the following information for the character '{term_name}':

Existing Glossary Description (Notes):
{existing_notes}

New AI Speech Analysis Insights:
{details}

Produce a unified, beautifully structured, and highly detailed description written strictly in {self.target_lang}. Avoid redundancy. 
Keep any pre-existing context while seamlessly translating it and integrating the new character and speech features.
Do not output anything else but the synthesized {self.target_lang} text. Do not wrap in markdown blocks or JSON. Just print the final synthesized notes.
"""
        return synth_system_prompt, synth_user_prompt

    def run(self):
        """Run."""
        try:
            self.log.emit("Starting AI Character Speech Profiler...")
            self.progress.emit(5, 100, "Retrieving dialogue lines from database...")

            # 1. Fetch character dialogue lines from local MemPalace DB
            char_dialogues = self.client.get_all_character_lines(self.wing_name)
            
            # Workspace scan fallback if DB is empty but we have composer
            if not char_dialogues and self.composer:
                self.log.emit("No dialogue drawers found in SQLite. Scanning active project workspace strings via composer...")
                mw = getattr(self.composer, "mw", None)
                store = getattr(mw, "data_store", None) if mw else None
                if store and store.data:
                    char_dialogues = {}
                    total_blocks = len(store.data)
                    tag_pattern = ANY_TAG_PATTERN
                    
                    for b_idx in range(total_blocks):
                        if self.is_cancelled:
                            break
                        block_strings = store.data[b_idx]
                        block_label = self.composer._get_block_label(b_idx)
                        
                        self.progress.emit(
                            5 + int((b_idx / total_blocks) * 15),
                            100,
                            f"Workspace scan: Mapping block {block_label} ({b_idx+1}/{total_blocks})..."
                        )
                        self.log.emit(f"Scanning workspace block '{block_label}' for character dialogues...")
                        
                        for s_idx, text in enumerate(block_strings):
                            if not text or not str(text).strip():
                                continue
                                
                            res = self.composer._find_speaker_in_script(b_idx, s_idx, text)
                            if res and isinstance(res, (tuple, list)) and len(res) == 2:
                                speaker, lines_str = res
                                if speaker and speaker != "NONE":
                                    clean_speaker = str(speaker).strip()
                                    if clean_speaker and clean_speaker.lower() not in ("unknown", "none"):
                                        clean_text = tag_pattern.sub('', text).strip()
                                        clean_text = re.sub(r'\s+', ' ', clean_text)
                                        if clean_text:
                                            char_dialogues.setdefault(clean_speaker, []).append(clean_text)
            
            # Filter out minor characters with fewer than 3 lines to speed up profiling and save API costs
            original_char_count = len(char_dialogues)
            char_dialogues = {speaker: d_lines for speaker, d_lines in char_dialogues.items() if len(d_lines) >= 3}
            filtered_count = original_char_count - len(char_dialogues)
            if filtered_count > 0:
                self.log.emit(f"Filtered out {filtered_count} minor characters with fewer than 3 dialogue lines to speed up profiling.")

            if not char_dialogues:
                self.finished.emit(False, "No character dialogues found in database or active project workspace. Please map script chapters first.")
                return

            self.log.emit(f"Found dialogues for {len(char_dialogues)} characters.")
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            # Prepare prompts configuration
            prompts_data = self._load_plugin_prompts()
            
            # System prompt for profiling (optimized for target language)
            if self.target_lang.strip().lower() == "ukrainian":
                system_prompt = (
                    "Ви — видатний директор з локалізації відеоігор, психолог персонажів та професійний лінгвіст. "
                    "Ваше завдання — проаналізувати всі репліки, які вимовляє конкретний персонаж гри, та скласти надзвичайно "
                    "детальний, художній та розлогий мовленнєвий портрет (speech profile) українською мовою для забезпечення абсолютної "
                    "художньої послідовності та автентичності при перекладі."
                )
            else:
                system_prompt = (
                    "You are an expert game localization director, character psychologist, and linguist. "
                    "Your task is to analyze all dialogues spoken by a specific character to compile a comprehensive, "
                    "high-quality, and deeply detailed speech profile to ensure consistency in localized translations."
                )

            total_characters = len(char_dialogues)
            processed_count = 0
            stats_updated = 0
            stats_added = 0
            stats_failed = 0
            stats_empty = 0
            consecutive_failures = 0

            for char_name, lines in char_dialogues.items():
                if self.is_cancelled:
                    break

                existing_entry = None
                script_glossary_context = ""

                # Skip already profiled characters to support incremental resumption
                if self.glossary_manager:
                    existing_entry, script_glossary_context = self._get_glossary_context_for_character(char_name)
                    if existing_entry:
                        has_marker = bool(existing_entry.profiled)
                        has_profile = False
                        if existing_entry.notes:
                            has_profile = ("📌" in existing_entry.notes and 
                                           "🗣️" in existing_entry.notes and 
                                           "💡" in existing_entry.notes)
                        
                        note_lines = [line.strip() for line in existing_entry.notes.splitlines() if line.strip()] if existing_entry.notes else []
                        line_count = len(note_lines)
                        
                        skip = False
                        
                        # 1. Якщо одночасно є і маркер і профайл
                        if has_marker and has_profile:
                            if line_count < 3:
                                # Опис неповний (<3 рядків) -> знімаємо profiled, запускаємо наново!
                                skip = False
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=False
                                    )
                                    self.glossary_manager.save_to_disk()
                                    self.log.emit(f"Character '{char_name}' is marked as Profiled but has <3 lines. Clearing profiled and re-profiling...")
                                except Exception as e_unmark:
                                    log_error(f"Failed to clear profiled for {char_name}: {e_unmark}")
                            else:
                                # Все гаразд -> скіпаємо
                                skip = True
                            
                        # 2. Якщо є профайл і немає маркера, або якщо є маркер і немає профайла
                        elif (has_profile and not has_marker) or (has_marker and not has_profile):
                            if line_count < 3:
                                # Знімаємо profiled, якщо раптом стояла (у випадку has_marker and not has_profile)
                                if has_marker:
                                    try:
                                        self.glossary_manager.update_entry(
                                            original=existing_entry.original,
                                            translation=existing_entry.translation,
                                            notes=existing_entry.notes,
                                            profiled=False
                                        )
                                        self.glossary_manager.save_to_disk()
                                    except Exception:
                                        pass
                                skip = False  # запускаємо
                            else:
                                # якщо більше або дорівнює трьох строк, помічаємо як Profiled і скіпаємо
                                skip = True
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=True
                                    )
                                    self.glossary_manager.save_to_disk()
                                except Exception as e_mark:
                                    log_error(f"Failed to auto-mark profiled for {char_name}: {e_mark}")
                                    
                        # 3. Якщо є профайл і >= 3 строк
                        elif has_profile and line_count >= 3:
                            skip = True
                            if not has_marker:
                                try:
                                    self.glossary_manager.update_entry(
                                        original=existing_entry.original,
                                        translation=existing_entry.translation,
                                        notes=existing_entry.notes,
                                        profiled=True
                                    )
                                    self.glossary_manager.save_to_disk()
                                except Exception:
                                    pass
                                    
                        if skip:
                            self.log.emit(f"Character '{char_name}' already has a completed speech profile. Skipping (incremental resume).")
                            stats_updated += 1
                            processed_count += 1
                            continue

                self.progress.emit(
                    20 + int((processed_count / total_characters) * 75),
                    100,
                    f"Profiling character speech {processed_count + 1}/{total_characters}: {char_name}..."
                )

                self.log.emit(f"Processing character '{char_name}' with {len(lines)} total lines...")
                if script_glossary_context:
                    self.log.emit(f"AI Speech Profiler: Using script Glossary context for '{char_name}'.")

                # 1. Ask the plugin for background lore to ground the profile in facts
                self.log.emit(f"AI Speech Profiler: Looking up background lore for '{char_name}'...")
                wiki_context = self._fetch_external_lore(char_name)
                if wiki_context:
                    self.log.emit(f"AI Speech Profiler: Found background lore for '{char_name}'.")
                else:
                    self.log.emit(f"AI Speech Profiler: No background lore found for '{char_name}' (using script dialogue only).")

                # 2. Filter out non-informative short dialogue lines (< 3 words) and enrich with timeline chapter context
                clean_lines = []
                tag_pattern = ANY_TAG_PATTERN
                for line in lines:
                    # Clean tags before counting words
                    text_no_tags = tag_pattern.sub('', line).strip()
                    words = [w for w in text_no_tags.split() if w.strip()]
                    if len(words) < 3: # Skip short/non-informative lines like "No", "Huh", "Yes"
                        continue
                    
                    # Try to fetch timeline room context (chapter name)
                    ctx = None
                    if self.client:
                        try:
                            ctx = self.client.get_cached_context("", line)
                        except Exception:
                            ctx = None
                            
                    if ctx:
                        room = ctx.get("room", "Unknown Chapter")
                        if self.target_lang.strip().lower() == "ukrainian":
                            clean_lines.append(f'[У главі "{room}"]: "{line}"')
                        else:
                            clean_lines.append(f'[In Chapter "{room}"]: "{line}"')
                    else:
                        clean_lines.append(f'"{line}"')

                # 3. Sample up to 80 representative lines to fit context window and prevent token bloat
                sampled_lines = clean_lines
                if len(clean_lines) > 80:
                    self.log.emit(f"Character '{char_name}' has many informative lines ({len(clean_lines)}). Sampling 80 representative dialogues...")
                    step = len(clean_lines) / 80
                    sampled_lines = [clean_lines[int(i * step)] for i in range(80)]

                # Format dialogues block
                dialogue_text_block = "\n".join(f'- {line}' for line in sampled_lines)

                # Formulate user prompt
                if self.target_lang.strip().lower() == "ukrainian":
                    wiki_section = ""
                    if script_glossary_context:
                        wiki_section += f"\n--- Script Glossary Context (source from Markup Studio) ---\n{script_glossary_context}\n"
                    if wiki_context:
                        wiki_section += f"\n--- Background Lore (Джерело істини) ---\n{wiki_context}\n"
                        
                    user_prompt = f"""
Проаналізуйте наступну інформацію для персонажа '{char_name}':
{wiki_section}
--- Характерні діалоги персонажа у грі ---
{dialogue_text_block}
---

Створіть високоякісний, структурований та НАДЗВИЧАЙНО КОНЦЕНТРОВАНИЙ мовленнєвий портрет українською мовою.
УНИКАЙТЕ БУДЬ-ЯКОЇ ВОДИ та очевидних банальностей! Кожен розділ має бути ультра-коротким (максимум 2-3 інформативні речення, до 40-50 слів), але містити саму суть і конкретні поради.

ВАЖЛИВО: Якщо цей "персонаж" насправді є службовим тегом розповіді/системи (наприклад, "NARRATIVE", "SYSTEM") або якщо про нього немає реального лору та індивідуального стилю мовлення для аналізу, обов'язково поверніть "speech_profile": "" (порожній рядок) в JSON, щоб ми могли пропустити його профілювання. Не генеруйте порожній шаблон із самих лише заголовків без реального змісту! Кожен заповнений розділ обов'язково повинен містити реальний детальний художній опис з інформативними реченнями.

Обов'язково структуруйте опис (поле "speech_profile" у JSON) на такі чіткі розділи з відповідними емодзі-заголовками:

📌 **Хто цей персонаж (Загальний опис та роль)**:
[Коротко (до 2 речень): хто він згідно з лором Вікіпедії, його роль у сюжеті. Базуйтеся САМЕ на наданому Wiki Context (якщо є) і не галюцинуйте!]

🎭 **Характер та психологічний портрет**:
[Коротко (до 2 речень): ключові риси характеру, емоційний стан, манера поведінки]

🗣️ **Особливості мовлення та лексика**:
[Коротко (до 2 речень): стиль спілкування, характерні вигуки, слова-паразити чи унікальні слова. Тон і темп.]

👥 **Відносини з іншими персонажами та соціальний статус**:
[Коротко (до 2 речень): ставлення до Лінка та інших героїв, соціальне становище]

📝 **Форми звертання та граматичні рекомендації**:
[Коротко (до 2 речень): як він звертається до інших (неформально на 'ти' чи формально на 'ви'), граматичні особливості при перекладі]

💡 **Рекомендації для перекладача (Як його перекладати)**:
[Коротко (до 2 речень): конкретні практичні поради перекладачу: які емоційні відтінки чи унікальні українські вирази підібрати]

Поверніть відповідь ВИКЛЮЧНО у форматі JSON. Не обгортайте JSON у блоки markdown (не пишіть ```json) і не додавайте жодного іншого супровідного тексту.
Структура JSON має бути такою:
{{
  "name_translation": "Природний переклад або транслітерація імені персонажа українською мовою (наприклад, 'Тріл')",
  "speech_profile": "[Сюди запишіть весь згенерований стислий структурований портрет українською мовою з усіма вищенаведеними розділами та заголовками]"
}}
"""
                else:
                    wiki_section = ""
                    if script_glossary_context:
                        wiki_section += f"\n--- Script Glossary Context (source from Markup Studio) ---\n{script_glossary_context}\n"
                    if wiki_context:
                        wiki_section += f"\n--- Wiki Context (Source of Truth) ---\n{wiki_context}\n"
                        
                    user_prompt = f"""
Analyze the following information for the character '{char_name}':
{wiki_section}
--- Representative Dialogues ---
{dialogue_text_block}
---

Create a premium, structured, and EXTREMELY CONCISE speech profile written strictly in {self.target_lang}.
AVOID ANY WATER or redundancy! Each section must be ultra-short (maximum 2-3 sentences, up to 40-50 words), focusing only on crucial facts and translation advice.

IMPORTANT: If this "character" is actually a narrative/system tag (like "NARRATIVE", "SYSTEM") or has no real lore and distinct speech pattern to analyze, you MUST return "speech_profile": "" (empty string) in JSON so we can skip profiling them. Do not generate an empty template of headings without real content! Each filled section must contain a substantial description with informative sentences.

Structure the description (the "speech_profile" field in JSON) into these exact sections with emoji headings:

📌 **Who is this character (General description & role)**:
[Briefly (up to 2 sentences): who they are based on the Wiki Context, their role in the game.]

🎭 **Personality and psychological portrait**:
[Briefly (up to 2 sentences): core traits, emotional state, temperament.]

🗣️ **Speech features and vocabulary**:
[Briefly (up to 2 sentences): speech style, register, tone, and tempo.]

👥 **Relationships with other characters and social status**:
[Briefly (up to 2 sentences): how they relate to Link and others, social standing.]

📝 **Forms of address and grammatical recommendations**:
[Briefly (up to 2 sentences): formal vs informal address, specific grammar tips for {self.target_lang} translation.]

💡 **Recommendations for the translator (How to translate)**:
[Briefly (up to 2 sentences): practical tips, specific vocabulary choices or emotional nuances to capture.]

Respond ONLY with a valid JSON object. Do not wrap in markdown json blocks or add any conversational text.
JSON Structure:
{{
  "name_translation": "Natural translation or transliteration of the character's name to {self.target_lang} (e.g. 'Trill')",
  "speech_profile": "[Put the entire synthesized concise structured profile here with all headings listed above]"
}}
"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

                try:
                    # Query AI
                    log_ai_traffic(self.mw, "mempalace_speech_profiling", messages)
                    response = self.ai_provider.translate(messages, session=None)
                    log_ai_traffic(self.mw, "mempalace_speech_profiling", messages, response_text=response.text)
                    consecutive_failures = 0
                    
                    if self.is_cancelled:
                        break

                    # Parse JSON
                    data = robust_json_loads(response.text)
                    name_translation = data.get("name_translation", char_name).strip()
                    speech_profile = data.get("speech_profile", "").strip()

                    if not speech_profile:
                        self.log.emit(f"WARNING: AI returned empty speech profile for '{char_name}'. Skipping.")
                        stats_empty += 1
                        processed_count += 1
                        continue

                    self.log.emit(f"AI Speech Profiler: Successfully generated profile for '{char_name}' (Translated as '{name_translation}').")

                    # 2. Update Glossary Entry
                    if self.glossary_manager:
                        # Look up existing entry by original or translated name
                        existing_entry = self.glossary_manager.get_entry(char_name) or self.glossary_manager.get_entry(name_translation)
                        
                        if existing_entry:
                            # Synthesize existing notes with new speech profile
                            self.log.emit(f"Entry '{existing_entry.original}' exists. Synthesizing notes with AI Speech Profile...")
                            existing_notes = existing_entry.notes or ""
                            
                            synth_sys, synth_usr = self._get_synthesis_prompts(
                                existing_entry.original, existing_notes, speech_profile, prompts_data
                            )
                            synth_messages = [
                                {"role": "system", "content": synth_sys},
                                {"role": "user", "content": synth_usr}
                            ]
                            
                            try:
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages)
                                synth_response = self.ai_provider.translate(synth_messages, session=None)
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages, response_text=synth_response.text)
                                final_notes = synth_response.text.strip()
                                
                                self.glossary_manager.update_entry(
                                    original=existing_entry.original,
                                    translation=existing_entry.translation,
                                    notes=final_notes,
                                    profiled=True
                                )
                                stats_updated += 1
                                self.log.emit(f"SUCCESS: Synthesized speech profile for existing character '{existing_entry.original}'.")
                            except Exception as e_synth:
                                log_ai_traffic(self.mw, "mempalace_speech_profile_synthesis", synth_messages, error=str(e_synth))
                                log_error(f"Failed to synthesize speech notes for {char_name}: {e_synth}")
                                # Fallback: append profile to notes directly
                                if self.target_lang.strip().lower() == "ukrainian":
                                    fallback_notes = f"{existing_notes}\n\nСтиль мовлення: {speech_profile}"
                                else:
                                    fallback_notes = f"{existing_notes}\n\nSpeech Style: {speech_profile}"
                                self.glossary_manager.update_entry(
                                    original=existing_entry.original,
                                    translation=existing_entry.translation,
                                    notes=fallback_notes,
                                    profiled=True
                                )
                                stats_updated += 1
                                self.log.emit(f"FALLBACK: Appended speech profile directly for existing character '{existing_entry.original}'.")
                        else:
                            # Add new glossary entry in Characters section
                            self.glossary_manager.add_entry(
                                original=char_name,
                                translation=name_translation,
                                notes=speech_profile,
                                section="Characters",
                                profiled=True
                            )
                            stats_added += 1
                            self.log.emit(f"SUCCESS: Created new Characters entry '{char_name}' -> '{name_translation}' with AI speech profile.")
                        
                        try:
                            self.glossary_manager.save_to_disk()
                        except Exception as e_save:
                            log_error(f"Failed to auto-save glossary for {char_name}: {e_save}")

                except Exception as e_proc:
                    log_error(f"Failed to process speech profile for {char_name}: {e_proc}")
                    self.log.emit(f"WARNING: Speech profiling failed for '{char_name}': {str(e_proc)}")
                    stats_failed += 1
                    
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        self.log.emit("Too many consecutive AI errors. Stopping character speech profiling to prevent flooding.")
                        self.finished.emit(False, f"Profiling stopped due to multiple consecutive AI errors (last error: {e_proc}).")
                        return

                processed_count += 1

            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            # Save all glossary updates to disk
            if self.glossary_manager:
                try:
                    self.progress.emit(95, 100, "Saving glossary database to disk...")
                    self.glossary_manager.save_to_disk()
                    self.log.emit("Successfully saved updated glossary (.md table) to disk.")
                except Exception as disk_err:
                    log_error(f"Failed to save glossary to disk: {disk_err}")
                    self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

            self.progress.emit(100, 100, "Speech profiling and glossary updates completed!")
            
            # Format success message
            stat_msg = (
                f"Successfully completed character speech profiling!\n\n"
                f"📊 Execution Statistics:\n"
                f"• Total characters processed: {processed_count}\n"
                f"• Successfully updated in Glossary: {stats_updated}\n"
                f"• Newly added to Glossary: {stats_added}\n"
                f"• Failed/skipped due to API errors: {stats_failed}\n"
                f"• Empty AI profiles received: {stats_empty}\n\n"
                f"You can find the generated profiles directly in the Picoripi Glossary editor (Characters tab) "
                f"or as tooltip previews when hovering over these character names in the main translation window."
            )
            self.finished.emit(True, stat_msg)

        except Exception as e:
            log_error(f"Error in MemePalaceCharacterProfilerWorker: {e}", exc_info=True)
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")
