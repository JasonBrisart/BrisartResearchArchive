r"""
File: brisart_ai/web/tests/test_public_fetch_policy.py

Purpose
-------
Exercise the public URL policy at fetch and redirect boundaries.

Communication / relationships
-----------------------------
Exercises brisart_ai.web.fetcher without network access.

Settings / parameters
---------------------
Uses unittest and urllib request redirect handler.

Edge cases
----------
Tests initial localhost and redirect to loopback.

Known limitations
-----------------
Does not test DNS rebinding at the socket layer.

Examples
--------
python scripts/run_tests.py brisart_ai/web/tests/test_public_fetch_policy.py
"""
import unittest
from unittest.mock import patch
from brisart_ai.web.fetcher import fetch_url, _PublicOnlyRedirect

class PublicFetchPolicyTests(unittest.TestCase):
    def test_private_destination_never_opens(self):
        with patch("urllib.request.build_opener") as opener:
            result = fetch_url("http://127.0.0.1/private")
        self.assertIn("private", result.error)
        opener.assert_not_called()

    def test_redirect_to_private_address_is_rejected(self):
        handler = _PublicOnlyRedirect()
        with self.assertRaises(ValueError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1/admin")

if __name__ == "__main__": unittest.main()
