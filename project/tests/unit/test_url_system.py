"""
Phase 2 URL System Unit Tests.
Validates URL validation, deterministic normalization, BFS queueing, and deduplication.
"""
import pytest
from project.utils.url_normalizer import normalize_url, is_valid_url
from project.services.url_manager import URLManager


class TestURLValidationAndNormalization:
    """Validates Section 7 URL rules."""

    def test_valid_urls(self):
        assert is_valid_url("http://example.com") is True
        assert is_valid_url("https://example.com/page?query=1") is True
        assert is_valid_url("https://sub.domain.org:8080/path") is True

    def test_invalid_and_unsupported_schemes(self):
        assert is_valid_url("ftp://example.com/file") is False
        assert is_valid_url("file:///C:/local/file.txt") is False
        assert is_valid_url("javascript:void(0)") is False
        assert is_valid_url("data:text/html,<html></html>") is False
        assert is_valid_url("") is False
        assert is_valid_url("not a url") is False

    def test_scheme_and_hostname_lowercasing(self):
        norm = normalize_url("HTTPS://WWW.Example.COM/Path/To/Page")
        assert norm == "https://www.example.com/Path/To/Page"

    def test_default_port_stripping(self):
        assert normalize_url("http://example.com:80/page") == "http://example.com/page"
        assert normalize_url("https://example.com:443/page") == "https://example.com/page"
        # Non-default ports should be preserved
        assert normalize_url("http://example.com:8080/page") == "http://example.com:8080/page"

    def test_fragment_stripping(self):
        norm = normalize_url("https://example.com/article#introduction")
        assert norm == "https://example.com/article"

    def test_path_normalization(self):
        norm = normalize_url("https://example.com/a//b/./c/../d")
        assert norm == "https://example.com/a/b/d"

    def test_deterministic_query_parameter_sorting(self):
        norm1 = normalize_url("https://example.com/search?z=3&a=1&m=2")
        norm2 = normalize_url("https://example.com/search?m=2&z=3&a=1")
        assert norm1 == norm2
        assert norm1 == "https://example.com/search?a=1&m=2&z=3"

    def test_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_url("ftp://invalid.com")


class TestURLManagerBFSAndDeduplication:
    """Validates Section 8 and Section 9 BFS queue and deduplication rules."""

    def test_seed_url_addition_and_deduplication(self):
        mgr = URLManager()
        s1 = mgr.add_seed("https://example.com/start")
        assert s1 is not None
        assert s1.depth == 0
        assert s1.url == "https://example.com/start"

        # Duplicate seed should be skipped
        s2 = mgr.add_seed("HTTPS://example.com/start#frag")
        assert s2 is None
        assert mgr.queue_size() == 1
        assert mgr.total_discovered_count() == 1

    def test_bfs_order(self):
        mgr = URLManager()
        mgr.add_seed("https://example.com/page1")
        mgr.add_seed("https://example.com/page2")
        mgr.add_seed("https://example.com/page3")

        first = mgr.pop_next_url()
        second = mgr.pop_next_url()
        third = mgr.pop_next_url()

        assert first.url == "https://example.com/page1"
        assert second.url == "https://example.com/page2"
        assert third.url == "https://example.com/page3"
        assert mgr.has_urls() is False

    def test_depth_restriction_enforcement(self):
        mgr = URLManager()
        seed = mgr.add_seed("https://example.com")
        assert seed.depth == 0

        # Depth 1 links
        links_depth_1 = [
            "https://example.com/about",
            "https://example.com/contact",
        ]
        added_1 = mgr.add_discovered_links(
            parent_depth=0,
            links=links_depth_1,
            max_depth=1,
            recursive=True,
        )
        assert len(added_1) == 2
        for item in added_1:
            assert item.depth == 1

        # Attempting to add depth 2 links when max_depth=1
        links_depth_2 = ["https://example.com/about/team"]
        added_2 = mgr.add_discovered_links(
            parent_depth=1,
            links=links_depth_2,
            max_depth=1,
            recursive=True,
        )
        assert len(added_2) == 0  # Not queued because 1 + 1 > 1

    def test_recursive_false_disables_link_discovery(self):
        mgr = URLManager()
        mgr.add_seed("https://example.com")

        added = mgr.add_discovered_links(
            parent_depth=0,
            links=["https://example.com/child1", "https://example.com/child2"],
            max_depth=3,
            recursive=False,  # Recursion disabled
        )
        assert len(added) == 0
        assert mgr.queue_size() == 1  # Only seed in queue
