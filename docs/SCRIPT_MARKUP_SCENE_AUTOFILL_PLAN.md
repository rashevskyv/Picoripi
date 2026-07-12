# Script Markup Studio: scene auto-fill plan

## Agreed behaviour

- A scene is a `Structure` child of a chapter and divides the chapter into parts.
- Auto-fill learns scenes from the existing hierarchy tree, not from an iterator in a scene name.
- Repeated child `Structure` nodes at the same depth in already marked chapters are the scene examples.
- A marked `Breaker` teaches the parser the exact separator text. Matching requires the same characters and length.
- A breaker belongs to the scene that ends at it and is nested at `scene depth + 1` alongside speakers and other scene content.
- The next chapter is also a scene boundary, but it must never create an artificial breaker.
- Actions and narrators inside scene boundaries remain part of the scene.
- Auto-fill applies the learned scene pattern to peer chapters that do not yet contain scene structures.
- Auto-fill does not create a scene container when a chapter contains only one scene-sized block.
- Generated scene names follow the numeric pattern learned from existing sibling scenes and restart for each parent chapter.
- Existing structures are not renamed.

## Manual structure-name iterator

- `$` is only a convenience for manually adding structures with `Ctrl+M`.
- `Scene $` starts at `Scene 1`; `Scene $4` starts at `Scene 4`.
- The number advances among sibling structures at the same tree position.
- Changing the parent structure resets the sequence to the template's starting value.
- Only one iterator per name is supported.
- Stored node names contain the resolved number, not the `$` expression.

## Example provenance and approval

- Every hierarchy mark records its origin: `manual`, `local_autofill`, or `ai`.
- Manual marks are approved examples by default.
- Local Auto-fill and AI results start unapproved and are visibly labelled in the tree.
- Only approved marks teach subsequent Auto-fill/AI example passes.
- Automatic marks can be approved from the tree context menu.
- Legacy saved marks without provenance load as manual, approved examples.

## Implementation steps

1. Add a small, testable resolver for `$` / `$N` structure-name templates.
2. Resolve the template when Script Markup Studio creates a manual `Structure` mark.
3. Extend local example-based auto-fill to discover scene examples through parent/child depth and containment.
4. Learn the exact breaker signature and numeric scene-name pattern from those examples.
5. Split peer chapters without scenes into scene ranges, nesting real breakers inside the preceding scene.
6. Preserve all existing marks and make repeated auto-fill idempotent.
7. Cover manual iteration, per-parent reset, exact breakers, chapter boundaries, nested breakers, and repeated runs with tests.
8. Run focused core/UI tests followed by the surrounding Script Markup Studio suite.
