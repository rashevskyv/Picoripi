"""
Tests for core/project_models.py — Category, Block, Project data models.
Safety net for refactoring: project management changes.
"""
from core.project_models import Category, Block, Project


# ── Category ────────────────────────────────────────────────────────

class TestCategory:
    def test_create_with_defaults(self):
        cat = Category(name="Test")
        assert cat.name == "Test"
        assert cat.id  # UUID should be generated
        assert cat.children == []
        assert cat.line_indices == []

    def test_to_dict_from_dict_roundtrip(self):
        cat = Category(name="NPCs", description="All NPCs", line_indices=[0, 1, 2])
        d = cat.to_dict()
        restored = Category.from_dict(d)
        assert restored.name == cat.name
        assert restored.description == cat.description
        assert restored.line_indices == cat.line_indices
        assert restored.id == cat.id

    def test_add_child(self):
        parent = Category(name="Parent")
        child = Category(name="Child")
        parent.add_child(child)
        assert len(parent.children) == 1
        assert parent.children[0].name == "Child"
        assert child.parent_id == parent.id

    def test_remove_child(self):
        parent = Category(name="Parent")
        child = Category(name="Child")
        parent.add_child(child)
        result = parent.remove_child(child.id)
        assert result is True
        assert len(parent.children) == 0

    def test_remove_nonexistent_child(self):
        parent = Category(name="Parent")
        result = parent.remove_child("fake-id")
        assert result is False

    def test_find_category_direct(self):
        cat = Category(name="Root")
        found = cat.find_category(cat.id)
        assert found is cat

    def test_find_category_nested(self):
        root = Category(name="Root")
        child = Category(name="Child")
        grandchild = Category(name="Grandchild")
        child.add_child(grandchild)
        root.add_child(child)
        found = root.find_category(grandchild.id)
        assert found is grandchild

    def test_serialization_with_children(self):
        parent = Category(name="Parent")
        child = Category(name="Child", line_indices=[5, 6])
        parent.add_child(child)
        d = parent.to_dict()
        restored = Category.from_dict(d)
        assert len(restored.children) == 1
        assert restored.children[0].name == "Child"
        assert restored.children[0].line_indices == [5, 6]


# ── Block ───────────────────────────────────────────────────────────

class TestBlock:
    def test_create_with_defaults(self):
        block = Block(name="Messages")
        assert block.name == "Messages"
        assert block.source_file == ""
        assert block.translation_file == ""
        assert block.categories == []

    def test_to_dict_from_dict_roundtrip(self):
        block = Block(
            name="Dialog",
            source_file="sources/dialog.txt",
            translation_file="translation/dialog.txt",
            description="Main dialog"
        )
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert restored.name == block.name
        assert restored.source_file == block.source_file
        assert restored.translation_file == block.translation_file
        assert restored.id == block.id

    def test_add_category(self):
        block = Block(name="B")
        cat = Category(name="C")
        block.add_category(cat)
        assert len(block.categories) == 1

    def test_remove_category(self):
        block = Block(name="B")
        cat = Category(name="C")
        block.add_category(cat)
        result = block.remove_category(cat.id)
        assert result is True
        assert len(block.categories) == 0

    def test_find_category_recursive(self):
        block = Block(name="B")
        cat = Category(name="Parent")
        child = Category(name="Child")
        cat.add_child(child)
        block.add_category(cat)
        found = block.find_category(child.id)
        assert found is child

    def test_get_all_categories_flat(self):
        block = Block(name="B")
        cat1 = Category(name="C1")
        cat2 = Category(name="C2")
        child = Category(name="C1.1")
        cat1.add_child(child)
        block.add_category(cat1)
        block.add_category(cat2)
        flat = block.get_all_categories_flat()
        assert len(flat) == 3

    def test_get_categorized_line_indices(self):
        block = Block(name="B")
        cat1 = Category(name="C1", line_indices=[0, 1, 2])
        cat2 = Category(name="C2", line_indices=[5, 6])
        block.add_category(cat1)
        block.add_category(cat2)
        indices = block.get_categorized_line_indices()
        assert 0 in indices
        assert 5 in indices
        assert 3 not in indices

    def test_serialization_with_categories(self):
        block = Block(name="B")
        cat = Category(name="C", line_indices=[1, 3])
        block.add_category(cat)
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert len(restored.categories) == 1
        assert restored.categories[0].line_indices == [1, 3]


# ── Project ─────────────────────────────────────────────────────────

class TestProject:
    def test_create_with_defaults(self):
        proj = Project(name="Test")
        assert proj.name == "Test"
        assert proj.blocks == []

    def test_add_block(self):
        proj = Project(name="P")
        block = Block(name="B")
        proj.add_block(block)
        assert len(proj.blocks) == 1

    def test_remove_block(self):
        proj = Project(name="P")
        block = Block(name="B")
        proj.add_block(block)
        result = proj.remove_block(block.id)
        assert result is True
        assert len(proj.blocks) == 0

    def test_find_block_by_id(self):
        proj = Project(name="P")
        block = Block(name="Target")
        proj.add_block(Block(name="Other"))
        proj.add_block(block)
        found = proj.find_block(block.id)
        assert found is block

    def test_find_block_by_name(self):
        proj = Project(name="P")
        proj.add_block(Block(name="Alpha"))
        proj.add_block(Block(name="Beta"))
        found = proj.find_block_by_name("Beta")
        assert found is not None
        assert found.name == "Beta"

    def test_find_nonexistent_block(self):
        proj = Project(name="P")
        assert proj.find_block("fake-id") is None
        assert proj.find_block_by_name("Nope") is None

    def test_full_serialization_roundtrip(self):
        """Complex structure: project with blocks, categories, children."""
        proj = Project(name="Complex", plugin_name="zelda_mc", description="Test")
        block = Block(name="B1", source_file="s.txt", translation_file="t.txt")
        cat = Category(name="C1", line_indices=[0, 1])
        child = Category(name="C1.1", line_indices=[0])
        cat.add_child(child)
        block.add_category(cat)
        proj.add_block(block)

        d = proj.to_dict()
        restored = Project.from_dict(d)

        assert restored.name == "Complex"
        assert restored.plugin_name == "zelda_mc"
        assert len(restored.blocks) == 1
        assert restored.blocks[0].name == "B1"
        assert len(restored.blocks[0].categories) == 1
        assert len(restored.blocks[0].categories[0].children) == 1
