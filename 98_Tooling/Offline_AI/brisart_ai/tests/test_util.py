"""
File: brisart_ai/tests/test_util.py

Purpose
-------
Exercise tokenization, hashes and normalization utilities.

Protected scenarios: TestTokenize verifies basic tokenization; TestTokenize verifies
stopwords removed; TestTokenize verifies none input returns empty list; TestTokenize
verifies empty string returns empty list; TestTokenize verifies single char words
excluded.

Protected scenarios: TestStableHash verifies matches real hashlib sha256; TestStableHash
verifies deterministic; TestStableHash verifies different inputs differ; TestFileHash
verifies matches hashlib for file contents; TestFileHash verifies streams large file
correctly.

Protected scenarios: TestSplitSentences verifies splits on sentence boundaries;
TestSplitSentences verifies too short sentences dropped; TestSplitSentences verifies
empty text returns empty list; TestSplitSentences verifies none returns empty list;
TestNormalizeUrl verifies empty string returns empty.

Protected scenarios: TestNormalizeUrl verifies schemeless url gets https prepended;
TestNormalizeUrl verifies scheme and host lowercased; TestNormalizeUrl verifies path
percent encoding normalized; TestNormalizeUrl verifies fragment stripped; TestSameSite
verifies same host different scheme is same site.

Protected scenarios: TestSameSite verifies different hosts not same site; TestSameSite
verifies case insensitive comparison; TestTermVariantsAndFrames verifies regular plurals
both directions; TestTermVariantsAndFrames verifies no bad strips;
TestTermVariantsAndFrames verifies question frame.

Protected scenarios: TestTermVariantsAndFrames verifies title tokens split file names.

Communication / relationships
-----------------------------
Uses small text samples and temporary files.

Direct project imports: brisart_ai.util.

The cases use self.assertEqual, self.assertNotIn, self.assertIn, self.assertNotEqual,
self.assertTrue, self.assertFalse to check returned values, persisted state or raised
errors. The suite is run through scripts/run_tests.py so Native API discovery happens
before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Regular word variants, URL normalization and sentence splitting.

Regression coverage includes TestSameSite.test_different_hosts_not_same_site,
TestSameSite.test_case_insensitive_comparison,
TestTermVariantsAndFrames.test_regular_plurals_both_directions,
TestTermVariantsAndFrames.test_no_bad_strips,
TestTermVariantsAndFrames.test_question_frame,
TestTermVariantsAndFrames.test_title_tokens_split_file_names.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_util.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/tests/test_util.py -k
test_stopwords_removed.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from brisart_ai.util import file_hash, normalize_url, same_site, split_sentences, stable_hash, tokenize


class TestTokenize(unittest.TestCase):
    def test_basic_tokenization(self):
        self.assertEqual(tokenize("Hello, World! Co-founder"), ["hello", "world", "co-founder"])

    def test_stopwords_removed(self):
        tokens = tokenize("the cat and the dog")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertIn("cat", tokens)
        self.assertIn("dog", tokens)

    def test_none_input_returns_empty_list(self):
        self.assertEqual(tokenize(None), [])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize(""), [])

    def test_single_char_words_excluded(self):
        tokens = tokenize("a b I x")
        self.assertEqual(tokens, [])


class TestStableHash(unittest.TestCase):
    def test_matches_real_hashlib_sha256(self):
        value = "test string with café unicode"
        expected = hashlib.sha256(value.encode("utf-8")).hexdigest()
        self.assertEqual(stable_hash(value), expected)

    def test_deterministic(self):
        self.assertEqual(stable_hash("same input"), stable_hash("same input"))

    def test_different_inputs_differ(self):
        self.assertNotEqual(stable_hash("a"), stable_hash("b"))


class TestFileHash(unittest.TestCase):
    def test_matches_hashlib_for_file_contents(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.txt"
            content = b"file content for hashing" * 100
            path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            self.assertEqual(file_hash(path), expected)

    def test_streams_large_file_correctly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "large.bin"
            content = bytes((i % 256) for i in range(3 * 1024 * 1024))  # 3MB, spans multiple 1MB chunks
            path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            self.assertEqual(file_hash(path), expected)


class TestSplitSentences(unittest.TestCase):
    def test_splits_on_sentence_boundaries(self):
        text = "This is one sentence that is long enough to pass the length filter here. " \
               "This is another sentence that is also long enough to pass the filter here."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 2)

    def test_too_short_sentences_dropped(self):
        text = "Hi. " + "A" * 50 + " sentence long enough to pass through the length filter here today."
        sentences = split_sentences(text)
        self.assertTrue(all(len(s) >= 30 for s in sentences))

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(split_sentences(""), [])

    def test_none_returns_empty_list(self):
        self.assertEqual(split_sentences(None), [])


class TestNormalizeUrl(unittest.TestCase):
    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_url(""), "")

    def test_schemeless_url_gets_https_prepended(self):
        self.assertEqual(normalize_url("example.com/x"), "https://example.com/x")

    def test_scheme_and_host_lowercased(self):
        result = normalize_url("HTTPS://Example.COM/A")
        self.assertTrue(result.startswith("https://example.com"))

    def test_path_percent_encoding_normalized(self):
        result = normalize_url("https://example.com/A%20b")
        self.assertIn("%20", result)

    def test_fragment_stripped(self):
        result = normalize_url("https://example.com/x#fragment")
        self.assertNotIn("#", result)


class TestSameSite(unittest.TestCase):
    def test_same_host_different_scheme_is_same_site(self):
        self.assertTrue(same_site("http://a.com/x", "https://a.com/y"))

    def test_different_hosts_not_same_site(self):
        self.assertFalse(same_site("http://a.com", "http://b.com"))

    def test_case_insensitive_comparison(self):
        self.assertTrue(same_site("http://Example.com", "http://example.COM"))



class TestTermVariantsAndFrames(unittest.TestCase):
    def test_regular_plurals_both_directions(self):
        from brisart_ai.util import term_variants
        self.assertIn("lawsuit", term_variants("lawsuits"))
        self.assertIn("lawsuits", term_variants("lawsuit"))
        self.assertIn("policy", term_variants("policies"))
        self.assertIn("policies", term_variants("policy"))
        self.assertIn("box", term_variants("boxes"))
        self.assertIn("matches", term_variants("match"))

    def test_no_bad_strips(self):
        from brisart_ai.util import term_variants
        self.assertNotIn("clas", term_variants("class"))
        self.assertEqual(term_variants("ab"), {"ab"})
        self.assertEqual(term_variants("x11"), {"x11"})

    def test_question_frame(self):
        from brisart_ai.util import expand_query_terms, query_frame_terms
        self.assertEqual(query_frame_terms("how do lawsuits work?"), {"work"})
        self.assertEqual(query_frame_terms("how does it work"), set())
        self.assertEqual(query_frame_terms("where do I find work"), set())
        terms = expand_query_terms("how do lawsuits work?")
        self.assertIn("lawsuit", terms)
        self.assertNotIn("work", terms)

    def test_title_tokens_split_file_names(self):
        from brisart_ai.util import title_tokens
        self.assertEqual(title_tokens("LEGAL_SIMULATION.md"), ["legal", "simulation", "md"])

if __name__ == "__main__":
    unittest.main()

