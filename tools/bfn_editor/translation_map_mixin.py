import os
from core.i18n import tr
from utils.logging_utils import log_info, log_error


class TranslationMapMixin:
    def get_translation_map_path(self):
        import os
        project_dir = None
        active_plugin = None
        parent_win = self.parent()
        if parent_win:
            mw = getattr(parent_win, "mw", None) if hasattr(parent_win, "mw") else parent_win
            if hasattr(mw, "project_manager") and mw.project_manager and mw.project_manager.project_dir:
                project_dir = mw.project_manager.project_dir
            if hasattr(mw, "active_game_plugin"):
                active_plugin = mw.active_game_plugin
                
        mapping_path = None
        if project_dir:
            mapping_path = os.path.join(project_dir, "translation_map.json")
        elif active_plugin:
            plugin_dir = os.path.join("plugins", active_plugin)
            if os.path.exists(plugin_dir):
                mapping_path = os.path.join(plugin_dir, "translation_map.json")
        return mapping_path

    def load_translation_map(self):
        self.translation_map = {}
        self.reverse_translation_map = {}
        try:
            mapping_path = self.get_translation_map_path()
            if mapping_path and os.path.exists(mapping_path):
                import json
                with open(mapping_path, "r", encoding="utf-8") as f:
                    raw_map = json.load(f)
                    
                self.translation_map = {}
                needs_save = False
                
                # 1. Normalize mapping direction: Ukrainian character (ord >= 256) must be the key,
                # CP1252 character (ord < 256) must be the value.
                normalized_map = {}
                for k, v in raw_map.items():
                    if k.startswith("#g") or v.startswith("#g"):
                        normalized_map[k] = v
                    elif len(k) == 1 and len(v) == 1:
                        if ord(k) < 256 and ord(v) >= 256:
                            # Swap to make Ukrainian character the key
                            normalized_map[v] = k
                        elif ord(k) >= 256 and ord(v) < 256:
                            normalized_map[k] = v
                        else:
                            normalized_map[k] = v
                            
                # 2. First pass: parse and migrate any synthetic mappings to real physical mappings in MAP1
                migrated_map = {}
                for k, v in normalized_map.items():
                    # Check if either k or v is a synthetic key "#g{idx}"
                    synthetic_key = None
                    virtual_char = None
                    if k.startswith("#g"):
                        synthetic_key = k
                        virtual_char = v
                    elif v.startswith("#g"):
                        synthetic_key = v
                        virtual_char = k
                        
                    if synthetic_key and virtual_char:
                        try:
                            glyph_idx = int(synthetic_key[2:])
                            # Check if this glyph already has a physical character code in MAP1
                            current_code = self.get_current_char_code_for_glyph(glyph_idx)
                            
                            # If it doesn't have a mapped code, or if the current code is already taken
                            # (excluding the synthetic key itself) or is equal to glyph_idx which could conflict,
                            # dynamically allocate a clean printable character code!
                            taken_codes = [ord(val) for key, val in normalized_map.items() if len(val) == 1 and key != synthetic_key]
                            if current_code <= 0 or current_code >= 0xFFFF or current_code in taken_codes or current_code == glyph_idx:
                                physical_code = self.get_next_free_char_code(migrated_map)
                                if physical_code is None:
                                    physical_code = glyph_idx
                            else:
                                physical_code = current_code
                                
                            self.update_char_mapping(glyph_idx, physical_code)
                            orig_char = chr(physical_code)
                                
                            # Convert to clean physical mapping in memory
                            migrated_map[virtual_char] = orig_char
                            needs_save = True
                        except Exception as e:
                            log_error(f"Failed to migrate synthetic key {synthetic_key}: {e}")
                    else:
                        # Keep normal entries as-is
                        migrated_map[k] = v
                        
                # 3. Second pass: heal any control characters/non-printable character codes in migrated_map
                healed_map = {}
                for k, v in migrated_map.items():
                    if len(k) == 1 and len(v) == 1:
                        char_code = ord(v)
                        # Control/non-printable range in Unicode/CP1252
                        if char_code < 32 or (127 <= char_code <= 160):
                            try:
                                # Find which glyph currently maps to this control code
                                glyph_idx = -1
                                for idx in range(self.start_glyph, self.end_glyph + 1):
                                    if self.get_current_char_code_for_glyph(idx) == char_code:
                                        glyph_idx = idx
                                        break
                                        
                                if glyph_idx != -1:
                                    physical_code = self.get_next_free_char_code(healed_map)
                                    if physical_code is not None:
                                        self.update_char_mapping(glyph_idx, physical_code)
                                        v = chr(physical_code)
                                        needs_save = True
                            except Exception as e:
                                log_error(f"Failed to heal control character code {char_code} for glyph {glyph_idx}: {e}")
                    healed_map[k] = v
                    
                # Load healed entries
                # Valid entry: key is non-ASCII unicode (ord >= 128), value is printable CP1252 (161-255)
                # Reject entries with control/non-printable value codes
                for k, v in healed_map.items():
                    if len(k) == 1 and len(v) == 1:
                        k_code = ord(k)
                        v_code = ord(v)
                        # Key must be non-ASCII (Cyrillic etc.), value must be printable CP1252 range 161-255
                        if k_code >= 128 and 161 <= v_code <= 255:
                            self.translation_map[k] = v
                        elif k_code >= 128 and v_code >= 128:
                            # Borderline case: both non-ASCII, allow but mark for heal next time
                            self.translation_map[k] = v
                            needs_save = True
                    elif k.startswith("#g") or v.startswith("#g"): # fallback if migration failed
                        self.translation_map[k] = v
                        
                # Rebuild reverse map only from normal (non-synthetic) entries
                self.reverse_translation_map = {
                    v: k for k, v in self.translation_map.items()
                    if not k.startswith("#g") and not v.startswith("#g")
                }
                
                # 4. Fourth pass: re-register any physical codes that are in translation_map
                # but NOT present in the current MAP1 (e.g. BFN wasn't saved after empty glyph assignment).
                # Find all codes currently registered in MAP1:
                registered_codes = set()
                for m in self.metadata.get("MAP1", []):
                    m_type = m.get("mapping_type", 0)
                    if m_type == 0:
                        for code in range(m.get("first_char", 0), m.get("last_char", 0) + 1):
                            registered_codes.add(code)
                    elif m_type == 2:
                        first_char = m.get("first_char", 0)
                        for c_idx, g_idx in enumerate(m.get("entries", [])):
                            if g_idx != 0xFFFF:
                                registered_codes.add(first_char + c_idx)
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for ki in range(half):
                            registered_codes.add(entries[ki])
                
                # Find all glyph indices that have NO code in MAP1 (empty glyphs)
                # Read range from metadata directly — self.start_glyph/end_glyph may not be set yet
                gly_meta = self.metadata.get("GLY1", [{}])[0]
                _heal_start = int(gly_meta.get("start_glyph", 0))
                _heal_end = int(gly_meta.get("end_glyph", _heal_start))
                all_glyphs = set(range(_heal_start, _heal_end + 1))
                mapped_glyphs = set()
                for m in self.metadata.get("MAP1", []):
                    m_type = m.get("mapping_type", 0)
                    if m_type == 2:
                        for g_idx in m.get("entries", []):
                            if g_idx != 0xFFFF:
                                mapped_glyphs.add(g_idx)
                    elif m_type == 3:
                        entries = m.get("entries", [])
                        half = len(entries) // 2
                        for ki in range(half):
                            mapped_glyphs.add(entries[half + ki])
                empty_glyphs = sorted(all_glyphs - mapped_glyphs)
                empty_glyph_iter = iter(empty_glyphs)
                
                orphan_codes_found = False
                for virtual_char, phys_char in list(self.translation_map.items()):
                    if len(virtual_char) != 1 or len(phys_char) != 1:
                        continue
                    phys_code = ord(phys_char)
                    if phys_code not in registered_codes:
                        # This physical code has no glyph assigned — find an empty glyph and assign it
                        try:
                            empty_glyph = next(empty_glyph_iter)
                            self.update_char_mapping(empty_glyph, phys_code)
                            registered_codes.add(phys_code)
                            mapped_glyphs.add(empty_glyph)
                            orphan_codes_found = True
                            log_info(f"BFN Editor: Re-registered orphan code {phys_code} ('{virtual_char}') to glyph {empty_glyph}")
                        except StopIteration:
                            log_error(f"BFN Editor: No empty glyphs left to re-register code {phys_code} ('{virtual_char}')")
                
                if orphan_codes_found:
                    needs_save = True
                
                if needs_save:
                    # Save the cleaned mapping_file without synthetic keys back to disk
                    self.save_translation_map()
                    # Physically save the BFN font file to commit the MAP1 changes to disk
                    try:
                        self.save_changes(silent=True)
                    except Exception as e:
                        log_error(f"Failed to auto-save BFN font during migration: {e}")
                    
                log_info(f"BFN Editor: Loaded {len(self.translation_map)} characters from translation_map.json.")
        except Exception as e:
            log_error(f"Failed to load translation map: {e}")

    def save_translation_map(self):
        try:
            mapping_path = self.get_translation_map_path()
            if mapping_path:
                import json
                # Filter out corrupt entries before saving:
                # - key must be 1 char, non-ASCII (ord >= 128)
                # - value must be 1 char, printable CP1252 (161-255)
                # Synthetic keys (#g...) are never saved to disk
                clean_map = {}
                for k, v in self.translation_map.items():
                    if k.startswith("#g") or (isinstance(v, str) and v.startswith("#g")):
                        continue  # skip synthetic entries
                    if len(k) == 1 and len(v) == 1:
                        k_code = ord(k)
                        v_code = ord(v)
                        if k_code >= 128 and 161 <= v_code <= 255:
                            clean_map[k] = v
                        # skip entries with control/invalid value codes
                    # skip entries with non-single-char keys/values
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump(clean_map, f, indent=4, ensure_ascii=False)
                self.status.showMessage(tr("Updated translation_map.json with {0} characters!", len(clean_map)))
        except Exception as e:
            log_error(f"Failed to save translation map: {e}")

    def get_next_free_char_code(self, temp_translation_map=None):
        used_codes = set()
        
        # 1. Collect codes used in the active translation map
        trans_map = temp_translation_map if temp_translation_map is not None else getattr(self, 'translation_map', {})
        if trans_map:
            for v in trans_map.values():
                if isinstance(v, str) and len(v) == 1:
                    used_codes.add(ord(v))
                elif isinstance(v, str) and v.startswith("#g"):
                    try:
                        used_codes.add(int(v[2:]))
                    except Exception:
                        pass
        
        # 2. Add ASCII printable characters to avoid overwriting them
        for code in range(32, 128):
            used_codes.add(code)
            
        # 3. Add control / non-printable CP1252 characters to avoid them
        for code in range(0, 32):
            used_codes.add(code)
        for code in range(127, 161):
            used_codes.add(code)
                        
        # 4. Find the first free code in the CP1252 printable range 161-255
        for code in range(161, 256):
            if code not in used_codes:
                return code
                
        return None

    def get_original_char_for_glyph(self, glyph_idx):
        metadata = self.original_font_metadata if self.original_font_metadata else self.metadata
        maps = metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            m_first = m.get("first_char", 0)
            m_last = m.get("last_char", 0)
            if m_type == 0:
                if m_first <= glyph_idx <= m_last:
                    try:
                        return bytes([glyph_idx]).decode('cp1252')
                    except Exception:
                        try:
                            return chr(glyph_idx)
                        except Exception:
                            pass
            elif m_type == 2:
                entries = m.get("entries", [])
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == glyph_idx:
                        code = m_first + c_idx
                        try:
                            return bytes([code]).decode('cp1252')
                        except Exception:
                            try:
                                return chr(code)
                            except Exception:
                                pass
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        code = entries[k]
                        try:
                            return bytes([code]).decode('cp1252')
                        except Exception:
                            try:
                                return chr(code)
                            except Exception:
                                pass
        return ""

    def generate_translation_map(self) -> dict:
        """
        Generate a translation mapping dictionary {trans_char: orig_char} 
        by comparing translated and original MAP1 characters for each glyph.
        """
        translation_map = {}
        if not self.original_font_metadata:
            return translation_map

        maps = self.metadata.get("MAP1", [])
        orig_maps = self.original_font_metadata.get("MAP1", [])

        def get_char_for_glyph(glyph_idx, map_blocks):
            for m in map_blocks:
                m_type = m.get("mapping_type", 0)
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_type == 0:
                    if m_first <= glyph_idx <= m_last:
                        try:
                            return bytes([glyph_idx]).decode('cp1252')
                        except Exception:
                            try:
                                return chr(glyph_idx)
                            except Exception:
                                pass
                elif m_type == 2:
                    entries = m.get("entries", [])
                    for c_idx, g_idx in enumerate(entries):
                        if g_idx == glyph_idx:
                            code = m_first + c_idx
                            if code > 0:
                                try:
                                    return bytes([code]).decode('cp1252')
                                except Exception:
                                    try:
                                        return chr(code)
                                    except Exception:
                                        pass
                            break
                elif m_type == 3:
                    entries = m.get("entries", [])
                    half = len(entries) // 2
                    for k in range(half):
                        if entries[half + k] == glyph_idx:
                            code = entries[k]
                            if code > 0:
                                try:
                                    return bytes([code]).decode('cp1252')
                                except Exception:
                                    try:
                                        return chr(code)
                                    except Exception:
                                        pass
            return ""

        for idx in range(self.start_glyph, self.end_glyph + 1):
            try:
                trans_char = get_char_for_glyph(idx, maps)
                orig_char = get_char_for_glyph(idx, orig_maps)
                
                if trans_char:
                    virtual_char = self.reverse_translation_map.get(trans_char)
                    if virtual_char:
                        if virtual_char != orig_char:
                            translation_map[virtual_char] = trans_char
                    elif orig_char and trans_char != orig_char:
                        if len(trans_char) == 1 and len(orig_char) == 1:
                            if ord(trans_char) >= 128 and ord(orig_char) >= 128:
                                translation_map[trans_char] = orig_char
            except Exception:
                pass

        return translation_map

    def get_current_char_code_for_glyph(self, glyph_idx):
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            if m_type == 0:
                m_first = m.get("first_char", 0)
                m_last = m.get("last_char", 0)
                if m_first <= glyph_idx <= m_last:
                    return glyph_idx
            elif m_type == 2:
                entries = m.get("entries", [])
                for c_idx, g_idx in enumerate(entries):
                    if g_idx == glyph_idx:
                        return m.get("first_char", 0) + c_idx
            elif m_type == 3:
                entries = m.get("entries", [])
                half = len(entries) // 2
                for k in range(half):
                    if entries[half + k] == glyph_idx:
                        return entries[k]
        return 0
