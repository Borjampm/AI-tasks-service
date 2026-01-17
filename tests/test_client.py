"""Unit tests for client utilities."""

import pytest
import sys
from pathlib import Path

# Add client to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "client"))

from main import is_local_url


class TestIsLocalUrl:
    """Tests for is_local_url function."""

    def test_localhost_returns_true(self):
        """localhost should be recognized as local."""
        assert is_local_url("localhost") is True

    def test_localhost_with_port_returns_true(self):
        """localhost:50051 should be recognized as local."""
        assert is_local_url("localhost:50051") is True

    def test_loopback_ipv4_returns_true(self):
        """127.0.0.1 should be recognized as local."""
        assert is_local_url("127.0.0.1") is True

    def test_loopback_ipv4_with_port_returns_true(self):
        """127.0.0.1:8080 should be recognized as local."""
        assert is_local_url("127.0.0.1:8080") is True

    def test_loopback_range_with_port_returns_true(self):
        """127.x.x.x range should be recognized as local."""
        assert is_local_url("127.0.0.100:8080") is True

    def test_ipv6_localhost_returns_true(self):
        """::1 (IPv6 localhost) should be recognized as local."""
        assert is_local_url("::1") is True

    def test_all_interfaces_returns_true(self):
        """0.0.0.0 should be recognized as local."""
        assert is_local_url("0.0.0.0") is True

    def test_external_domain_returns_false(self):
        """example.com should not be recognized as local."""
        assert is_local_url("example.com") is False

    def test_external_domain_with_port_returns_false(self):
        """api.example.com:443 should not be recognized as local."""
        assert is_local_url("api.example.com:443") is False

    def test_private_network_returns_false(self):
        """192.168.1.1 (private but not localhost) should not be recognized as local."""
        assert is_local_url("192.168.1.1") is False
