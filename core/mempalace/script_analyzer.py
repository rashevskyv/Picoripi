import json
import re
import os
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional, Tuple
from core.mempalace_client import MemePalaceClient
from core.translation.providers import BaseTranslationProvider
from utils.logging_utils import log_error, log_ai_traffic
from .weaver_worker import robust_json_loads


_OBJECT_TYPE_SECTIONS = {
    "item": "Items",
    "items": "Items",
    "object": "Items",
    "objects": "Items",
    "location": "Locations",
    "locations": "Locations",
    "place": "Locations",
    "places": "Locations",
    "term": "Terms",
    "terms": "Terms",
    "terminology": "Terms",
}


def _section_or_default(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _object_section(item: dict) -> str:
    section = item.get("section") or item.get("category")
    if section:
        return _section_or_default(section, "Terms")
    item_type = str(item.get("type") or "").strip().casefold()
    return _OBJECT_TYPE_SECTIONS.get(item_type, "Terms")


class MemePalaceScriptAnalyzerWorker(QThread):
    """Meme palace script analyzer worker implementation."""
    # Signals for UI communication
    progress = pyqtSignal(int, int, str)  # current, total, status
    log = pyqtSignal(str)                 # log message
    finished = pyqtSignal(bool, str)      # success, message

    def __init__(self, 
                 client: MemePalaceClient, 
                 file_path: str, 
                 ai_provider: BaseTranslationProvider, 
                 wing_name: str = "Zelda_TP",
                 glossary_manager: Optional[Any] = None,
                 target_lang: str = "Ukrainian",
                 plugin_name: Optional[str] = None,
                 mw=None):
        """Initialize a new instance."""
        super().__init__()
        self.client = client
        self.file_path = file_path
        self.ai_provider = ai_provider
        self.wing_name = wing_name
        self.glossary_manager = glossary_manager
        self.target_lang = target_lang
        self.plugin_name = plugin_name
        self.mw = mw or (getattr(glossary_manager, 'mw', None) if glossary_manager else None)
        self.is_cancelled = False

    def cancel(self):
        """Cancel."""
        self.is_cancelled = True
        self.log.emit("Script pre-analysis cancellation requested...")

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
                    self.log.emit(f"MemePalace Worker: Loaded per-plugin prompts config from {prompts_path}")
                except Exception as e_load:
                    log_error(f"Failed to load prompts.json for plugin {self.plugin_name}: {e_load}")
        return prompts_data

    def _get_mining_prompts(self, script_segment: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve Mining prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        p_sys = m_section.get("mining_system_prompt")
        p_usr = m_section.get("mining_user_prompt")

        if p_sys and p_usr:
            return p_sys.format(target_lang=self.target_lang), p_usr.format(script_segment=script_segment, target_lang=self.target_lang)

        glossary_guidance = """

GLOSSARY CONTEXT RULES:
- If the script contains a Markdown heading named "Glossary", treat that section as source-of-truth context, not dialogue.
- Headings directly under "Glossary" are semantic categories. Use their names as hints, for example Characters, Items, Locations, Terms, or any custom category name.
- Entries under a character-like category belong in "characters". Entries under every other category belong in "objects_and_terms".
- For every object/term extracted from a Glossary category, include "category" with the exact category heading text.
"""

        # Fallback built-in prompts
        if self.target_lang.strip().lower() == "ukrainian":
            system_prompt = (
                "Ви — професійний сценарист відеоігор та директор з локалізації. Ваше завдання — проаналізувати список персонажів "
                "та вступний текст ігрового скрипту, вилучити всіх ключових персонажів, їхні профілі, важливі предмети, "
                "локації чи термінологію, а також соціальні зв'язки. Ви повинні писати всі детальні описи, атрибути, "
                "описи стосунків та типи звертання виключно українською мовою."
            )
            user_prompt = f"""
Проаналізуйте наступний вступний фрагмент ігрового скрипту.
Вилучіть:
1. Усіх згаданих персонажів з їхнім детальним описом та роллю в сюжеті.
2. Атрибути персонажів для забезпечення послідовності перекладу українською мовою:
   - "gender": 'male', 'female' або 'unknown'.
   - "age_group": 'child', 'adult', 'elder' або 'unknown'.
   - "relationship_summary": детальний опис того, ким є цей персонаж для інших, виключно українською мовою (наприклад, 'наставник Лінка, чоловік Улі').
   - "address_type": граматичний статус звертання виключно українською мовою (наприклад, 'звертається до Лінка неформально (на "ти"), до мера звертається шанобливо/формально (на "ви")').
   - "description": детальний опис характеру та сюжетної ролі виключно українською мовою.
3. Kлючові ігрові/сюжетні предмети, локації або спеціальну термінологію ("objects_and_terms") з чітким описом того, що це таке, виключно українською мовою.
4. Соціальні зв'язки між персонажами, які визначають стиль їхнього спілкування в українському перекладі:
   - "addresses_informally" (використовують "ти"): для близьких друзів, рівних за статусом, родини, дітей чи наставників, що звертаються до учнів.
   - "addresses_respectfully" (шанобливе "ти" або шанобливе "ви").
   - "addresses_formally" (використовують "ви"): для королівських осіб, високопосадовців, незнайомців або при формальній ієрархії.

ВСТУПНИЙ СЕГМЕНТ СКРИПТУ:
{script_segment}
{glossary_guidance}

У відповідь поверніть ВИКЛЮЧНО валідний об'єкт JSON. Не додавайте блоки markdown чи будь-які інші пояснення.
Структура JSON:
{{
  "characters": [
    {{
      "name": "RUSL",
      "gender": "male",
      "age_group": "adult",
      "relationship_summary": "наставник Лінка, чоловік Улі, батько Коліна",
      "address_type": "звертається до Лінка неформально ('ти'), до мера звертається шанобливо/формально ('ви')",
      "description": "Хоробрий мечник із селища Ордон, який є наставником Лінка та просить його доставити щит до замку Хайрул."
    }}
  ],
  "objects_and_terms": [
    {{
      "name": "Ordon Shield",
      "category": "Items",
      "description": "Дерев'яний щит з шкіряними елементами, виготовлений Руслем для того, щоб Лінк доставив його до замку Хайрул."
    }}
  ],
  "relations": [
    {{"source": "RUSL", "relation": "addresses_informally", "target": "LINK", "reason": "mentor speaking to student"}},
    {{"source": "LINK", "relation": "addresses_respectfully", "target": "RUSL", "reason": "student speaking to mentor"}}
  ]
}}
"""
        else:
            system_prompt = (
                f"You are an expert game narrative architect and localization director. Your task is to analyze a game script's "
                f"character list and introduction text, and extract all key characters, their character profiles, "
                f"important gameplay/story objects, locations, or terminology, and social relations. "
                f"You must write all detailed descriptions, attributes, relationship summaries, and address types strictly in {self.target_lang}."
            )
            user_prompt = f"""
Analyze the following introduction segment of a game script.
Extract:
1. All characters mentioned with their detailed description and specific story role.
2. Character attributes for target language translation consistency (specifically for {self.target_lang} translation):
   - "gender": 'male', 'female', or 'unknown'.
   - "age_group": 'child', 'adult', 'elder', or 'unknown'.
   - "relationship_summary": detailed explanation of who this character is to others strictly in {self.target_lang} (e.g., 'mentor of Link').
   - "address_type": grammar address status strictly in {self.target_lang} (e.g., 'speaks to Link informally').
   - "description": detailed context and personality description strictly in {self.target_lang}.
3. Key gameplay/story objects, items, locations, or special terminology ("objects_and_terms") found in the script with a clear description of what they are, written strictly in {self.target_lang}.
4. Social relations between characters that dictate how they should speak to each other in {self.target_lang} translation:
    - "addresses_informally" (meaning they use informal forms of address, e.g. 'tu', 'du', or equivalent): for close friends, equals, family, children, mentors speaking to students.
    - "addresses_respectfully" (meaning they use respectful forms of address).
    - "addresses_formally" (meaning they use formal forms of address, e.g. 'usted', 'Sie', or equivalent).
   
INTRO TEXT SEGMENT:
{script_segment}
{glossary_guidance}

Respond ONLY with a valid JSON object. Do not include markdown blocks or any other explanation.
JSON structure:
{{
  "characters": [
    {{
      "name": "RUSL",
      "gender": "male",
      "age_group": "adult",
      "relationship_summary": "mentor of Link, husband of Uli",
      "address_type": "addresses Link informally, addresses mayor respectfully",
      "description": "Brave swordsman from Ordon..."
    }}
  ],
  "objects_and_terms": [
    {{
      "name": "Ordon Shield",
      "category": "Items",
      "description": "Wooden shield crafted by Rusl..."
    }}
  ],
  "relations": [
    {{"source": "RUSL", "relation": "addresses_informally", "target": "LINK", "reason": "mentor speaking to student"}}
  ]
}}
"""
        return system_prompt, user_prompt

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
                "терміна у глосарії з новими деталями, знайденими в ігровому скрипті. Ви повинні синтезувати їх "
                "у один зв'язний, високоякісний, структурований та детальний опис (notes), написаний виключно українською мовою."
            )
            synth_user_prompt = f"""
Синтезуйте наступну інформацію для терміна/персонажа '{term_name}':

Існуючий опис у глосарії (нотатки):
{existing_notes}

Нові сюжетні деталі зі скрипту:
{details}

Створіть єдиний, красиво структурований та детальний опис, написаний виключно українською мовою. Уникайте повторень.
Збережіть увесь попередній контекст, обов'язково переклавши його українською мовою (якщо він був англійською), та гармонійно інтегруйте нову інформацію (стать, вік, стосунки, стилі звертання та роль у грі).
Не повертайте нічого, крім фінального синтезованого тексту українською мовою. Не загортайте в блоки markdown або JSON. Поверніть лише чистий текст опису.
"""
        else:
            synth_system_prompt = (
                f"You are an expert game translation lexicographer. Your task is to combine the existing glossary entry notes "
                f"with new narrative insights extracted from the game script. You must synthesize them into one coherent, premium, well-structured, "
                f"highly detailed description (notes) written strictly in {self.target_lang}."
            )
            synth_user_prompt = f"""
Synthesize the following information for the term/character '{term_name}':

Existing Glossary Description (Notes):
{existing_notes}

New Script Insights:
{details}

Produce a unified, beautifully structured, and highly detailed description written strictly in {self.target_lang}. Avoid redundancy. 
Keep any pre-existing context while seamlessly translating it and integrating the new information (like gender, age, relationships, address styles, and gameplay role). 
Do not output anything else but the synthesized {self.target_lang} text. Do not wrap in markdown blocks or JSON. Just print the final synthesized notes paragraph or text body.
"""
        return synth_system_prompt, synth_user_prompt

    def _get_new_term_prompts(self, term_name: str, details: str, prompts_data: dict) -> Tuple[str, str]:
        """Resolve New Term prompts with per-plugin customizations and fallbacks."""
        m_section = prompts_data.get("mempalace", {})
        nt_sys = m_section.get("new_term_system_prompt")
        nt_usr = m_section.get("new_term_user_prompt")

        if nt_sys and nt_usr:
            return nt_sys.format(target_lang=self.target_lang), nt_usr.format(
                term_name=term_name,
                details=details,
                target_lang=self.target_lang
            )

        if self.target_lang.strip().lower() == "ukrainian":
            new_term_system_prompt = (
                "Ви — професійний перекладач ретро-ігор з англійської на українську мову. Ваше завдання — "
                "запропонувати природний переклад або транслітерацію назви терміна українською мовою, "
                "а також згенерувати детальний структурований опис (нотатки) виключно українською мовою на основі наданих сюжетних деталей."
            )
            new_term_user_prompt = f"""
Створити новий запис у глосарії для терміна: '{term_name}'

Сюжетні деталі зі скрипту:
{details}

У відповідь поверніть ВИКЛЮЧНО валідний об'єкт JSON. Не додавайте блоки markdown чи будь-які інші пояснення.
Структура JSON:
{{
  "translation": "Природний переклад або транслітерація українською мовою (наприклад, 'Русль' або 'Ордонський щит')",
  "notes": "Високоякісний структурований опис, написаний виключно українською мовою, який містить стать, вікову групу, стосунки, форми звертання та сюжетний контекст."
}}
"""
        else:
            new_term_system_prompt = (
                f"You are an expert retro game translator from English to {self.target_lang}. "
                f"Your task is to provide a natural translated or transliterated name for the term in {self.target_lang}, "
                f"and generate a premium structured description (notes) written strictly in {self.target_lang} based on script insights."
            )
            new_term_user_prompt = f"""
Create a new glossary record for term: '{term_name}'

Script Insights:
{details}

Respond ONLY with a valid JSON object. Do not include markdown blocks or any other explanation.
JSON structure:
{{
  "translation": "Natural translation or transliteration in {self.target_lang} (e.g. 'Rusl')",
  "notes": "Premium structured description written strictly in {self.target_lang} including gender, age group, relationships, address forms, and narrative context."
}}
"""
        return new_term_system_prompt, new_term_user_prompt

    def run(self):
        """Run."""
        try:
            self.log.emit("Starting AI Script Pre-Analyzer...")
            self.progress.emit(10, 100, "Reading script introduction...")

            # 1. Read first 2000 lines of the script (where cast/intro resides)
            if not os.path.exists(self.file_path):
                self.finished.emit(False, f"Script file not found: {self.file_path}")
                return

            if self.file_path.lower().endswith(".md"):
                self.log.emit("Markdown script detected. Processing locally without AI queries...")
                self.progress.emit(25, 100, "Parsing Markdown script structures...")
                from core.markdown_script_parser import parse_markdown_script
                parsed = parse_markdown_script(self.file_path)
                
                characters = parsed.get("characters", [])
                terms = parsed.get("terms", [])
                
                # Format objects_and_terms as expected by the database step
                objects_and_terms = []
                for t in terms:
                    objects_and_terms.append({
                        "name": t.get("original", t.get("name")),
                        "description": t.get("description", ""),
                        "section": t.get("section") or "Terms",
                    })

                self.progress.emit(50, 100, "Processing character profiles and writing to Glossary...")
                if self.glossary_manager:
                    # process characters
                    for char in characters:
                        term_name = char["name"]
                        target_section = char.get("section") or "Characters"
                        if self.target_lang.strip().lower() == "ukrainian":
                            notes = f"Стать: {char['gender']}. Вік: {char['age_group']}. Зв'язки: {char['relationship_summary']}. Звертання: {char['address_type']}. Опис: {char['description']}"
                        else:
                            notes = f"Gender: {char['gender']}. Age: {char['age_group']}. Relations: {char['relationship_summary']}. Address Style: {char['address_type']}. Description: {char['description']}"
                        
                        existing = self.glossary_manager.get_entry(term_name)
                        if existing:
                            self.glossary_manager.update_entry(
                                original=existing.original,
                                translation=char.get("translation", existing.translation),
                                notes=notes,
                                section=getattr(existing, "section", None) or target_section
                            )
                        else:
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=char.get("translation", term_name),
                                notes=notes,
                                section=target_section
                            )

                    # process terms
                    for t in terms:
                        term_name = t["original"]
                        notes = t.get("description", "")
                        target_section = t.get("section") or "Terms"
                        existing = self.glossary_manager.get_entry(term_name)
                        if existing:
                            self.glossary_manager.update_entry(
                                original=existing.original,
                                translation=t.get("translation", existing.translation),
                                notes=notes,
                                section=getattr(existing, "section", None) or target_section
                            )
                        else:
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=t.get("translation", term_name),
                                notes=notes,
                                section=target_section
                            )
                    
                    try:
                        self.glossary_manager.save_to_disk()
                        self.log.emit("Successfully saved updated glossary database (.md table) to disk.")
                    except Exception as disk_err:
                        log_error(f"Failed to save glossary to disk: {disk_err}")
                        self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

                # Build relations from characters profiles
                relations = []
                for char in characters:
                    source_name = char.get("translation", char.get("name")).upper()
                    if char.get("relationship_summary"):
                        relations.append({
                            "source": source_name,
                            "relation": char.get("relationship_summary"),
                            "target": "Global_Cast"
                        })
                    if char.get("address_type"):
                        relations.append({
                            "source": source_name,
                            "relation": char.get("address_type"),
                            "target": "Style"
                        })

                self.progress.emit(90, 100, "Writing character profiles to SQLite Memory Palace...")
                # Write to local SQLite Palace
                self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}")
                cast_content = "CHARACTER CAST PROFILES:\n"
                for char in characters:
                    name = char.get("name", "Unknown").upper()
                    desc = char.get("description", "")
                    cast_content += f"- {name}: {desc}\n"
                    
                self.client.add_room(self.wing_name, "Global_Cast_Profiles", "Global character details and profiles.")
                self.client.add_drawer(
                    self.wing_name,
                    "Global_Cast_Profiles",
                    "character_cast_profiles",
                    cast_content,
                    {"characters": characters}
                )

                for rel in relations:
                    self.client.add_relation(
                        self.wing_name,
                        rel["source"],
                        rel["relation"],
                        rel["target"],
                        valid_from="Global_Cast"
                    )
                    self.log.emit(f"Saved Relation: {rel['source']} -[{rel['relation']}]-> {rel['target']}")

                self.progress.emit(100, 100, "Script pre-analysis and glossary synthesis completed!")
                self.finished.emit(True, f"Successfully parsed Markdown script locally! Found {len(characters)} characters. Glossary has been synchronized.")
                return

            # Read with cp1252 to handle special symbols in GameFAQ scripts
            with open(self.file_path, "r", encoding="cp1252", errors="replace") as f:
                intro_lines = []
                for _ in range(2000):
                    line = f.readline()
                    if not line:
                        break
                    intro_lines.append(line)

            script_segment = "".join(intro_lines)
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            self.progress.emit(25, 100, "Sending script segment to AI for terminology & character mining...")
            self.log.emit(f"Extracted {len(intro_lines)} lines for AI Persona Miner. Querying LLM...")

            # Load prompts.json configuration (per-plugin)
            prompts_data = self._load_plugin_prompts()

            # 2. Formulate Prompt for Character and Term mining
            system_prompt, user_prompt = self._get_mining_prompts(script_segment, prompts_data)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            log_ai_traffic(self.mw, "mempalace_terminology_mining", messages)
            try:
                response = self.ai_provider.translate(messages, session=None)
                log_ai_traffic(self.mw, "mempalace_terminology_mining", messages, response_text=response.text)
            except Exception as e_mining:
                log_ai_traffic(self.mw, "mempalace_terminology_mining", messages, error=str(e_mining))
                raise e_mining
            
            if self.is_cancelled:
                self.finished.emit(False, "Process cancelled by user.")
                return

            self.progress.emit(50, 100, "Processing AI response and writing to SQLite...")
            
            # 3. Parse JSON response using robust parser
            data = robust_json_loads(response.text)
            characters = data.get("characters", [])
            objects_and_terms = data.get("objects_and_terms", [])
            relations = data.get("relations", [])

            self.log.emit(f"AI found {len(characters)} character profiles, {len(objects_and_terms)} objects/terms, and {len(relations)} relations.")

            # 4. Process and enrich Picoripi Glossary
            if self.glossary_manager:
                self.log.emit(f"Active Glossary Manager detected. Populating and synthesizing glossary entries in {self.target_lang}...")
                
                # Combine characters and objects for glossary processing
                items_to_process = []
                for char in characters:
                    items_to_process.append({
                        "name": char.get("name", "").strip(),
                        "type": "character",
                        "gender": char.get("gender", "unknown"),
                        "age_group": char.get("age_group", "unknown"),
                        "relationship_summary": char.get("relationship_summary", ""),
                        "address_type": char.get("address_type", ""),
                        "description": char.get("description", ""),
                        "section": char.get("section") or "Characters",
                    })
                for obj in objects_and_terms:
                    items_to_process.append({
                        "name": obj.get("name", "").strip(),
                        "type": "object",
                        "description": obj.get("description", ""),
                        "section": _object_section(obj),
                    })

                total_items = len(items_to_process)
                for item_idx, item in enumerate(items_to_process):
                    if self.is_cancelled:
                        break
                    
                    term_name = item["name"]
                    if not term_name:
                        continue
                    
                    # Update progress slightly during glossary loop (from 50% to 85%)
                    sub_pct = 50 + int((item_idx / total_items) * 35)
                    self.progress.emit(sub_pct, 100, f"Synthesizing Glossary Entry {item_idx + 1}/{total_items}: {term_name}...")

                    # Search in glossary manager (case-insensitive)
                    existing_entry = self.glossary_manager.get_entry(term_name)
                    
                    if existing_entry:
                        # Term exists! Synthesize notes with existing ones, preserving translation!
                        self.log.emit(f"Term '{term_name}' exists in glossary. Synthesizing notes via AI strictly in {self.target_lang} (preserving translation)...")
                        
                        existing_notes = existing_entry.notes or ""
                        
                        if self.target_lang.strip().lower() == "ukrainian":
                            if item["type"] == "character":
                                details = f"""
- Тип сутності: Персонаж
- Стать: {item['gender']}
- Вікова категорія: {item['age_group']}
- Стосунки/Родинні зв'язки: {item['relationship_summary']}
- Форми звертання (на "ти" / на "ви"): {item['address_type']}
- Новий сюжетний контекст: {item['description']}
"""
                            else:
                                details = f"""
- Тип сутності: Предмет/Локація/Термін
- Новий сюжетний контекст: {item['description']}
"""
                        else:
                            if item["type"] == "character":
                                details = f"""
- Entity Type: Character
- Gender: {item['gender']}
- Age Group: {item['age_group']}
- Relations: {item['relationship_summary']}
- Forms of Address: {item['address_type']}
- New Context: {item['description']}
"""
                            else:
                                details = f"""
- Entity Type: Item/Location/Term
- New Context: {item['description']}
"""
                        
                        synth_system_prompt, synth_user_prompt = self._get_synthesis_prompts(
                            term_name, existing_notes, details, prompts_data
                        )

                        synth_messages = [
                            {"role": "system", "content": synth_system_prompt},
                            {"role": "user", "content": synth_user_prompt}
                        ]
                        
                        try:
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages)
                            synth_response = self.ai_provider.translate(synth_messages, session=None)
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages, response_text=synth_response.text)
                            synthesized_notes = synth_response.text.strip()
                            
                            # Safely update the entry in the glossary
                            self.glossary_manager.update_entry(
                                original=existing_entry.original,
                                translation=existing_entry.translation,
                                notes=synthesized_notes,
                                section=getattr(existing_entry, "section", None) or item["section"],
                            )
                            self.log.emit(f"SUCCESS: Synthesized entry for '{term_name}' (notes updated in {self.target_lang}, translation '{existing_entry.translation}' kept).")
                        except Exception as e_synth:
                            log_ai_traffic(self.mw, "mempalace_notes_synthesis", synth_messages, error=str(e_synth))
                            log_error(f"Failed to synthesize notes for existing term {term_name}: {e_synth}")
                            self.log.emit(f"WARNING: Notes synthesis failed for '{term_name}': {str(e_synth)}")
                    
                    else:
                        # New term! Translate term and construct initial notes in self.target_lang
                        self.log.emit(f"Term '{term_name}' is new. Translating name and creating structured notes in {self.target_lang} via AI...")
                        
                        if self.target_lang.strip().lower() == "ukrainian":
                            if item["type"] == "character":
                                details = f"""
- Тип сутності: Персонаж
- Стать: {item['gender']}
- Вікова категорія: {item['age_group']}
- Стосунки/Родинні зв'язки: {item['relationship_summary']}
- Форми звертання (на "ти" / на "ви"): {item['address_type']}
- Опис: {item['description']}
"""
                            else:
                                details = f"""
- Тип сутності: Предмет/Локація/Термін
- Опис: {item['description']}
"""
                        else:
                            if item["type"] == "character":
                                details = f"""
- Entity Type: Character
- Gender: {item['gender']}
- Age Group: {item['age_group']}
- Relations: {item['relationship_summary']}
- Forms of Address: {item['address_type']}
- Description: {item['description']}
"""
                            else:
                                details = f"""
- Entity Type: Item/Location/Term
- Description: {item['description']}
"""

                        new_term_system_prompt, new_term_user_prompt = self._get_new_term_prompts(
                            term_name, details, prompts_data
                        )

                        new_term_messages = [
                            {"role": "system", "content": new_term_system_prompt},
                            {"role": "user", "content": new_term_user_prompt}
                        ]
                        
                        try:
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages)
                            new_term_response = self.ai_provider.translate(new_term_messages, session=None)
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages, response_text=new_term_response.text)
                            term_data = robust_json_loads(new_term_response.text)
                            translated_name = term_data.get("translation", term_name).strip()
                            synthesized_notes = term_data.get("notes", "").strip()
                            
                            # Add new entry to the glossary
                            section = item["section"]
                            self.glossary_manager.add_entry(
                                original=term_name,
                                translation=translated_name,
                                notes=synthesized_notes,
                                section=section
                            )
                            self.log.emit(f"SUCCESS: Created new entry '{term_name}' -> '{translated_name}' in section '{section}' with description in {self.target_lang}.")
                        except Exception as e_new:
                            log_ai_traffic(self.mw, "mempalace_new_term_creation", new_term_messages, error=str(e_new))
                            log_error(f"Failed to translate and save new term {term_name}: {e_new}")
                            self.log.emit(f"WARNING: Creation failed for new term '{term_name}': {str(e_new)}")

                # Write all glossary updates to disk
                try:
                    self.glossary_manager.save_to_disk()
                    self.log.emit("Successfully saved updated glossary database (.md table) to disk.")
                except Exception as disk_err:
                    log_error(f"Failed to save glossary to disk: {disk_err}")
                    self.log.emit(f"ERROR saving glossary to disk: {disk_err}")

            self.progress.emit(90, 100, "Writing character profiles to SQLite Memory Palace...")

            # 5. Write to local SQLite Palace (for viewer consistency)
            self.client.add_wing(self.wing_name, f"Chronological Memory Palace for {self.wing_name}")
            
            # Save character cast profiles to a dedicated drawer in a special room
            cast_content = "CHARACTER CAST PROFILES:\n"
            for char in characters:
                name = char.get("name", "Unknown").upper()
                desc = char.get("description", "")
                cast_content += f"- {name}: {desc}\n"
                
            self.client.add_room(self.wing_name, "Global_Cast_Profiles", "Global character details and profiles.")
            self.client.add_drawer(
                self.wing_name,
                "Global_Cast_Profiles",
                "character_cast_profiles",
                cast_content,
                {"characters": characters}
            )

            # Write relations to temporal knowledge graph
            for rel in relations:
                source = rel.get("source", "Unknown").upper()
                relation = rel.get("relation", "addresses_informally")
                target = rel.get("target", "Unknown").upper()
                reason = rel.get("reason", "")
                
                self.client.add_relation(
                    self.wing_name,
                    source,
                    relation,
                    target,
                    valid_from="Global_Cast"
                )
                self.log.emit(f"Saved Relation: {source} -[{relation}]-> {target} ({reason})")

            self.progress.emit(100, 100, "Script pre-analysis and glossary synthesis completed!")
            self.finished.emit(True, f"Successfully parsed script! Found {len(characters)} characters and {len(relations)} relations. Glossary has been synchronized and saved to disk.")

        except Exception as e:
            log_error(f"Error in MemePalaceScriptAnalyzerWorker: {e}", exc_info=True)
            self.log.emit(f"FATAL ERROR: {str(e)}")
            self.finished.emit(False, f"Error occurred: {str(e)}")
