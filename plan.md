# Completed plan: edit confirmed speaker identity mappings

1. [x] Keep confirmed identity mappings non-provisional while exposing their originating game code in Glossary.
2. [x] Let a user reassign that code to another permanent character name, preserving the existing explicit alias save and glossary-migration path.
3. [x] Verify the actual `Ash -> ASHEI` project mapping, cover it with focused tests, version, document, and commit.

# Previously completed plan: reject conflicting legacy speaker aliases

1. [x] Inspect the live project data and identify the stale `Ash -> ASHEI / TELMA` alias as the cause of the missing provisional UI.
2. [x] Treat slash-joined conflict labels as evidence rather than confirmed identities across Glossary, merging, glossary seeding, folders, and AI speaker resolution.
3. [x] Block slash-joined labels from manual Apply, add regression coverage, verify, version, document, and commit the focused fix.

# Previously completed plan: resolve provisional speakers in Glossary

1. [x] Audit the existing provisional color, description/occurrence panes, structured AI `suggested_name` evidence, and confirmed alias save path.
2. [x] Make provisional Character rows use the Merge Speakers unmatched purple and expose the AI suggestion/evidence in the selected-entry details.
3. [x] Add one editable known-speaker selector plus an explicit Apply action for the selected provisional code; keep Merge Speakers editing as a fallback.
4. [x] Route Apply through the existing alias persistence and glossary rename/migration path, then refresh folders, prompts, highlighting, and the open Glossary dialog.
5. [x] Add focused dialog/handler tests, run relevant Windows `.venv` verification, update version/docs, and commit only this iteration's files.
6. [x] Fall back to the active plugin for legacy Character entries that predate the persisted `provisional` flag.
