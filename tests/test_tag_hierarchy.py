"""Tests for tag hierarchy operations."""

import pytest
from comp.run._tag import Tag, is_parent_or_equal


class TestIsParentOrEqual:
    """Test is_parent_or_equal function."""

    def test_equal_tags(self):
        """A tag is equal to itself (distance 0)."""
        tag = Tag(["status"], "builtin")
        assert is_parent_or_equal(tag, tag) == 0

    def test_direct_parent(self):
        """Parent tag is immediate parent of direct child (distance 1)."""
        parent = Tag(["status"], "builtin")
        child = Tag(["status", "active"], "builtin")
        assert is_parent_or_equal(parent, child) == 1

    def test_grandparent(self):
        """Grandparent tag is 2 steps up (distance 2)."""
        grandparent = Tag(["status"], "builtin")
        grandchild = Tag(["status", "error", "timeout"], "builtin")
        assert is_parent_or_equal(grandparent, grandchild) == 2

    def test_intermediate_parent(self):
        """Intermediate parent in hierarchy (distance 1)."""
        parent = Tag(["status", "error"], "builtin")
        child = Tag(["status", "error", "timeout"], "builtin")
        assert is_parent_or_equal(parent, child) == 1

    def test_not_parent_wrong_direction(self):
        """Child is not parent of parent (returns -1)."""
        parent = Tag(["status"], "builtin")
        child = Tag(["status", "active"], "builtin")
        assert is_parent_or_equal(child, parent) == -1

    def test_not_parent_sibling(self):
        """Siblings are not parents of each other (returns -1)."""
        tag1 = Tag(["status", "active"], "builtin")
        tag2 = Tag(["status", "inactive"], "builtin")
        assert is_parent_or_equal(tag1, tag2) == -1
        assert is_parent_or_equal(tag2, tag1) == -1

    def test_not_parent_different_root(self):
        """Tags from different roots are not related (returns -1)."""
        tag1 = Tag(["status"], "builtin")
        tag2 = Tag(["priority"], "builtin")
        assert is_parent_or_equal(tag1, tag2) == -1

    def test_not_parent_different_namespace(self):
        """Tags from different namespaces are not related (returns -1)."""
        tag1 = Tag(["status"], "builtin")
        tag2 = Tag(["status"], "other")
        assert is_parent_or_equal(tag1, tag2) == -1

    def test_builtin_fail_hierarchy(self):
        """Test with actual builtin fail tag hierarchy."""
        fail = Tag(["fail"], "builtin")
        fail_syntax = Tag(["fail", "syntax"], "builtin")
        fail_missing = Tag(["fail", "missing"], "builtin")

        # fail is immediate parent of both children (distance 1)
        assert is_parent_or_equal(fail, fail_syntax) == 1
        assert is_parent_or_equal(fail, fail_missing) == 1

        # Children are not parents of each other (returns -1)
        assert is_parent_or_equal(fail_syntax, fail_missing) == -1
        assert is_parent_or_equal(fail_missing, fail_syntax) == -1

        # Children are not parents of parent (returns -1)
        assert is_parent_or_equal(fail_syntax, fail) == -1
        assert is_parent_or_equal(fail_missing, fail) == -1

    def test_deep_hierarchy(self):
        """Test with deeper hierarchy levels."""
        level0 = Tag(["a"], "builtin")
        level1 = Tag(["a", "b"], "builtin")
        level2 = Tag(["a", "b", "c"], "builtin")
        level3 = Tag(["a", "b", "c", "d"], "builtin")

        assert is_parent_or_equal(level0, level0) == 0
        assert is_parent_or_equal(level0, level1) == 1
        assert is_parent_or_equal(level0, level2) == 2
        assert is_parent_or_equal(level0, level3) == 3
        assert is_parent_or_equal(level1, level2) == 1
        assert is_parent_or_equal(level1, level3) == 2
        assert is_parent_or_equal(level2, level3) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
