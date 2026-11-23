"""
File: v1/tests/test_path.py
Purpose
-------
Verify v1/brisart_path.py against pathlib (CPython 3.12): for both flavours
and thousands of generated segment lists, every lexical property, method,
operator and exception (type and message) must equal pathlib's; match()
must give pathlib's answer on generated paths and patterns, including
sets, ranges, newlines, drives and case options; the concrete Path content
methods must read and write like pathlib's; and the module must import
nothing.
Communication / relationships
-----------------------------
Standard library: unittest, pathlib, os, ast, tempfile, warnings (reference
only), plus support.py in this folder.
Verifies: v1/brisart_path.py.
Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED (see support.py).
Edge cases
----------
Segment lists mix drives, UNC and device prefixes, doubled separators,
dots, wildcard characters, reserved device names, combining characters and
newlines. Outcomes compare exception type and message as well as values.
Known limitations
-----------------
Agreement with pathlib is tested on generated input, not proven. Native
platform detection is tested through its helper function, not by running
on Windows.
Examples
--------
::
    python -B -m unittest discover -s v1/tests -p test_path.py
"""
import ast
import os
import pathlib
import tempfile
import unittest
import warnings

import support
import brisart_path as bp

FLAVOURS = {
    "posix": (bp.PurePosixPath, pathlib.PurePosixPath, bp.PureWindowsPath, pathlib.PureWindowsPath),
    "windows": (bp.PureWindowsPath, pathlib.PureWindowsPath, bp.PurePosixPath, pathlib.PurePosixPath),
}
ATOMS = ["a", "b", "c", ".", "..", "", "/", "\\", "//", "///", "c:", "C:", "c:/", "C:\\", "d:x", "//srv/shr",
         "\\\\srv\\shr\\", "\\\\?\\UNC\\s\\h\\x", "\\\\.\\dev", "//?/c:/", "x y", "a.b", "a.tar.gz", ".hidden",
         "..x", "a.", "*", "?", "[ab]", "con", "NUL.txt", "com1", "aux:s", "lpt\xb9", "e\u0301", "\xe9", "A",
         "B", "~", "\n", "a\nb", "k.TXT"]
NAMES = ["x", "y.z", "", "/", "a/b", "\\", "..", ".", "x.y", "c:"]
SUFFIXES = [".x", "x", ".", "", ".a.b", "/.x", "\\.x", ".t/"]


def convert(value):
    if isinstance(value, (bp.PurePath, pathlib.PurePath)):
        return ("path", type(value).__name__, str(value))
    if isinstance(value, (bp._PathParents, type(pathlib.PurePath("a").parents))):
        return ("parents", [convert(item) for item in value], len(value), repr(value))
    if isinstance(value, tuple):
        return tuple(convert(item) for item in value)
    if isinstance(value, list):
        return [convert(item) for item in value]
    return value


def outcome(function):
    try:
        return ("ok", convert(function()))
    except Exception as error:
        return ("err", type(error).__name__, str(error))


def segments(r):
    pieces = []
    for _ in range(r.randint(0, 4)):
        if r.random() < 0.6:
            pieces.append(r.choice(ATOMS))
        else:
            pieces.append("".join(r.choice(ATOMS) for _ in range(r.randint(1, 4))))
    return pieces


PLAIN = {
    "str": str, "repr": repr, "bytes": bytes, "fspath": lambda p: p.__fspath__(),
    "reduce": lambda p: (p.__reduce__()[0].__name__, p.__reduce__()[1]),
    "as_posix": lambda p: p.as_posix(), "drive": lambda p: p.drive, "root": lambda p: p.root,
    "anchor": lambda p: p.anchor, "parts": lambda p: p.parts, "name": lambda p: p.name,
    "suffix": lambda p: p.suffix, "suffixes": lambda p: p.suffixes, "stem": lambda p: p.stem,
    "parent": lambda p: p.parent, "parents": lambda p: p.parents,
    "is_absolute": lambda p: p.is_absolute(), "is_reserved": lambda p: p.is_reserved(),
    "as_uri": lambda p: p.as_uri(), "lines": lambda p: p._lines, "normcase": lambda p: p._str_normcase,
}


class LexicalTests(unittest.TestCase):
    def test_properties_and_methods_equal_pathlib(self):
        for label, (ours, theirs, other_ours, other_theirs) in FLAVOURS.items():
            r = support.rng("path-lexical-" + label)
            for _ in range(support.scaled(2500)):
                pieces = segments(r)
                made_ours, made_theirs = outcome(lambda: ours(*pieces)), outcome(lambda: theirs(*pieces))
                self.assertEqual(made_ours[:1], made_theirs[:1], pieces)
                if made_ours[0] != "ok":
                    continue
                po, pt = ours(*pieces), theirs(*pieces)
                for name, function in PLAIN.items():
                    self.assertEqual(outcome(lambda: function(po)), outcome(lambda: function(pt)), (label, name, pieces))
                for index in (0, 1, -1, -2, 5, slice(None), slice(None, None, -1), slice(1, 3)):
                    self.assertEqual(outcome(lambda: po.parents[index]), outcome(lambda: pt.parents[index]), (pieces, index))
                self.assertEqual(
                    outcome(lambda: (list(po.parents), list(reversed(po.parents)), po in po.parents, po.parent in po.parents)),
                    outcome(lambda: (list(pt.parents), list(reversed(pt.parents)), pt in pt.parents, pt.parent in pt.parents)),
                    pieces)
                name, suffix = r.choice(NAMES), r.choice(SUFFIXES)
                for label2, call in (("with_name", lambda P: P(*pieces).with_name(name)),
                                     ("with_stem", lambda P: P(*pieces).with_stem(name)),
                                     ("with_suffix", lambda P: P(*pieces).with_suffix(suffix))):
                    self.assertEqual(outcome(lambda: call(ours)), outcome(lambda: call(theirs)), (label2, pieces, name, suffix))
                self.compare_with_other(r, label, pieces, po, pt, ours, theirs, other_ours, other_theirs)

    def compare_with_other(self, r, label, pieces, po, pt, ours, theirs, other_ours, other_theirs):
        other = segments(r)
        if not other:
            return
        for walk in (False, True):
            self.assertEqual(outcome(lambda: po.relative_to(other[0], walk_up=walk)),
                             outcome(lambda: pt.relative_to(other[0], walk_up=walk)), (pieces, other, walk))
        self.assertEqual(outcome(lambda: po.is_relative_to(other[0])), outcome(lambda: pt.is_relative_to(other[0])), (pieces, other))
        self.assertEqual(outcome(lambda: po.joinpath(*other)), outcome(lambda: pt.joinpath(*other)), (pieces, other))
        self.assertEqual(outcome(lambda: po / other[0]), outcome(lambda: pt / other[0]), (pieces, other))
        self.assertEqual(outcome(lambda: other[0] / po), outcome(lambda: other[0] / pt), (pieces, other))
        self.assertEqual(outcome(lambda: po.with_segments(*other)), outcome(lambda: pt.with_segments(*other)), (pieces, other))
        qo, qt = ours(*other), theirs(*other)
        for op in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"):
            self.assertEqual(outcome(lambda: getattr(po, op)(qo)), outcome(lambda: getattr(pt, op)(qt)), (op, pieces, other))
        self.assertEqual((po == qo, hash(po) == hash(qo)), (pt == qt, hash(pt) == hash(qt)), (pieces, other))
        bo, bt = other_ours(*other), other_theirs(*other)
        self.assertEqual(outcome(lambda: ours(*pieces, bo)), outcome(lambda: theirs(*pieces, bt)), (pieces, other))
        self.assertEqual((po == bo, outcome(lambda: po < bo)), (pt == bt, outcome(lambda: pt < bt)), (pieces, other))

    def test_known_cases(self):
        P, W = bp.PurePosixPath, bp.PureWindowsPath
        self.assertEqual(P("a//b/./c").as_posix(), "a/b/c")
        self.assertEqual(str(P("")), ".")
        self.assertEqual((P("//a/b").root, P("///a").root, P("/a").root), ("//", "/", "/"))
        self.assertEqual(P("/a/b/c.tar.gz").suffixes, [".tar", ".gz"])
        self.assertEqual(P("/usr", "lib", "x.py").parents[-1], P("/"))
        self.assertEqual(W("C:/Users/J").as_posix(), "C:/Users/J")
        self.assertEqual((W("C:/Users").drive, W("C:/Users").root), ("C:", "\\"))
        self.assertEqual(W("c:/Users"), W("C:\\USERS"))
        self.assertNotEqual(W("c:/a"), P("c:/a"))
        self.assertEqual(W("//srv/shr/x").parts, ("\\\\srv\\shr\\", "x"))
        self.assertTrue(W("nul.txt").is_reserved())
        self.assertFalse(W("//srv/shr/nul").is_reserved())
        self.assertEqual(W("c:/a/b").as_uri(), "file:///c:/a/b")
        self.assertEqual(P("/a b/\xe9").as_uri(), "file:///a%20b/%C3%A9")
        self.assertEqual(P("/a/b").relative_to("/a"), P("b"))
        self.assertEqual(P("/a/b").relative_to("/c", walk_up=True), P("../a/b"))
        with self.assertRaises(ValueError):
            P("/a").relative_to("/b")
        with self.assertRaises(TypeError):
            P(b"bytes")
        with self.assertRaises(TypeError):
            P("a", foo=1)

    def test_path_like_arguments_and_pickling(self):
        class Like:
            def __init__(self, value):
                self.value = value

            def __fspath__(self):
                return self.value

        self.assertEqual(bp.PurePosixPath(Like("/x/y")).as_posix(), "/x/y")
        for bad in (Like(b"/x"), Like(5), 5, None, ["a"]):
            with self.assertRaises(TypeError):
                bp.PurePosixPath(bad)
        import pickle
        for path in (bp.PurePosixPath("/a/b"), bp.PureWindowsPath("c:/a/b")):
            self.assertEqual(pickle.loads(pickle.dumps(path)), path)
        self.assertTrue(isinstance(bp.PurePosixPath("a"), os.PathLike))
        self.assertEqual(os.fspath(bp.PurePosixPath("a", "b")), "a/b")

    def test_slots_and_instances_are_closed(self):
        path = bp.PurePosixPath("a")
        with self.assertRaises(AttributeError):
            path.extra = 1


def match_mutation(r, part):
    k = r.random()
    if k < 0.2:
        return "*"
    if k < 0.35:
        return "?" * len(part) if part else "*"
    if k < 0.5 and part:
        return part[:r.randint(0, len(part))] + "*" + part[r.randint(0, len(part)):]
    if k < 0.6 and part:
        i = r.randrange(len(part))
        return part[:i] + "[" + part[i] + "x]" + part[i + 1:]
    if k < 0.7 and part:
        i = r.randrange(len(part))
        return part[:i] + "[!" + part[i] + "]" + part[i + 1:]
    if k < 0.78 and part:
        return part.upper()
    if k < 0.85 and part:
        return "*" + part[-1:]
    if k < 0.9:
        return r.choice(["[a-z]", "[!a-z]*", "*[0-9]", "*.*", "*.[pP][yY]", "a*b*c", "[]]*", "[!]]", "*\n*", "\n"])
    return part


class MatchTests(unittest.TestCase):
    def test_generated_paths_and_patterns_equal_pathlib(self):
        for label, (ours, theirs, _, _) in FLAVOURS.items():
            r = support.rng("path-match-" + label)
            trues = 0
            for _ in range(support.scaled(12000)):
                sep = "/" if label == "posix" or r.random() < 0.5 else "\\"
                parts = [r.choice(["a", "b", "abc", "x.py", "Doc.TXT", "a b", "ab\ncd", "caf\xe9", "e\u0301", "a-b", "[x]",
                                   "*", "?", ".hid", "k.tar.gz"]) for _ in range(r.randint(1, 5))]
                prefix = r.choice(["", "", "/", "c:/", "C:\\", "//srv/shr/", "\\"])
                path = prefix + "/".join(parts)
                i = r.randrange(len(parts))
                j = r.randint(i, len(parts))
                pattern = (prefix if (i == 0 and r.random() < 0.5) else "") + \
                    sep.join(match_mutation(r, p) for p in parts[i:j + 1])
                if r.random() < 0.1:
                    pattern = prefix + sep.join(match_mutation(r, p) for p in parts)
                case = r.choice([None, True, False])
                got = outcome(lambda: ours(path).match(pattern, case_sensitive=case))
                want = outcome(lambda: theirs(path).match(pattern, case_sensitive=case))
                self.assertEqual(got, want, (label, path, pattern, case))
                trues += want == ("ok", True)
            self.assertGreater(trues, 1000)

    def test_random_pattern_alphabet(self):
        pool = ["a", "b", "*", "?", "[ab]", "[!a]", "[a-c]", "[]]", "[!]]", "[z-a]", "[", "[a", "*.py", "a*", "*a", "a*b",
                "**", "/", "\\", "//", "c:", "c:/", "x", "X", "A*", "*.TXT", "a?b", ".", "..", "[a-]", "[!-a]", "[^a]",
                "[\\]", "[[]", "[]", "[!]", "a*b*c", "*b*", "\n", "?*", "*?", "[a-c-e]", "[b-a-c]", "\xe9", "[!/]", "[a/b]"]
        for label, (ours, theirs, _, _) in FLAVOURS.items():
            r = support.rng("path-pool-" + label)
            for _ in range(support.scaled(15000)):
                pieces = [r.choice(pool[:11] + ["a", "b", "c", "x", "a.py", ".py", "A", "X.TXT", "abc", "a b"])
                          for _ in range(r.randint(0, 5))]
                if r.random() < 0.3:
                    pieces = [r.choice(["/", "c:/", "C:\\", "//srv/shr/", "\\"])] + pieces
                pattern = "/".join(r.choice(pool) for _ in range(r.randint(0, 4)))
                if r.random() < 0.2:
                    pattern = "".join(r.choice(pool) for _ in range(r.randint(1, 3)))
                case = r.choice([None, True, False])
                self.assertEqual(outcome(lambda: ours(*pieces).match(pattern, case_sensitive=case)),
                                 outcome(lambda: theirs(*pieces).match(pattern, case_sensitive=case)),
                                 (label, pieces, pattern, case))

    def test_documented_examples(self):
        P = bp.PurePosixPath
        self.assertTrue(P("a/b.py").match("*.py"))
        self.assertTrue(P("/a/b/c.py").match("b/*.py"))
        self.assertFalse(P("/a/b/c.py").match("a/*.py"))
        self.assertTrue(P("/a.py").match("/*.py"))
        self.assertFalse(P("a/b.py").match("/*.py"))
        self.assertFalse(P("a/b.PY").match("*.py"))
        self.assertTrue(P("a/b.PY").match("*.py", case_sensitive=False))
        self.assertTrue(bp.PureWindowsPath("a/b.PY").match("*.py"))
        with self.assertRaises(ValueError):
            P("a").match("")

    def test_patterns_cannot_blow_up(self):
        path = bp.PurePosixPath("/" + "a" * 400)
        for pattern in ("*a" * 40 + "b", "a*" * 40 + "b", "[a]*" * 60 + "b", "*/" * 30 + "x"):
            self.assertFalse(path.match(pattern))
        support.assert_roughly_linear(
            self, lambda k: bp.PurePosixPath("/" + "a" * (400 * k)), lambda p: p.match("*a*a*a*b"))


class ConcretePathTests(unittest.TestCase):
    def test_native_platform_detection(self):
        for location in ("C:\\Users\\J\\v1\\brisart_path.py", "c:/x/brisart_path.py", "\\\\srv\\shr\\x.py"):
            self.assertTrue(bp._looks_like_windows(location), location)
        for location in ("", "/home/j/v1/brisart_path.py", "relative/brisart_path.py", "/c:/x", "x"):
            self.assertFalse(bp._looks_like_windows(location), location)

    def test_native_classes_follow_the_detected_platform(self):
        windows = bp._NATIVE_WINDOWS
        self.assertIs(type(bp.PurePath("a")), bp.PureWindowsPath if windows else bp.PurePosixPath)
        self.assertIs(type(bp.Path("a")), bp.WindowsPath if windows else bp.PosixPath)
        foreign = bp.PosixPath if windows else bp.WindowsPath
        with self.assertRaises(NotImplementedError) as caught:
            foreign("a")
        self.assertEqual(str(caught.exception), "cannot instantiate %r on your system" % foreign.__name__)
        self.assertTrue(issubclass(bp.PosixPath, bp.PurePosixPath) and issubclass(bp.WindowsPath, bp.PureWindowsPath))

    def test_content_methods_match_pathlib(self):
        with tempfile.TemporaryDirectory() as folder:
            ours, theirs = bp.Path(folder) / "ours.txt", pathlib.Path(folder) / "theirs.txt"
            self.assertEqual(ours.write_text("caf\xe9\nline2\n", encoding="utf-8"),
                             theirs.write_text("caf\xe9\nline2\n", encoding="utf-8"))
            self.assertEqual(ours.read_bytes(), "caf\xe9\nline2\n".encode("utf-8"))
            self.assertEqual(ours.read_text(encoding="utf-8"), theirs.read_text(encoding="utf-8"))
            self.assertEqual(ours.write_bytes(b"\x00\x01\x02"), theirs.write_bytes(b"\x00\x01\x02"))
            self.assertEqual(ours.read_bytes(), b"\x00\x01\x02")
            self.assertEqual(ours.write_bytes(bytearray(b"xyz")), 3)
            self.assertEqual(ours.write_text("a\nb", encoding="utf-8", newline="\r\n"), theirs.write_text("a\nb", encoding="utf-8", newline="\r\n"))
            self.assertEqual(ours.read_bytes(), b"a\r\nb")
            with ours.open("rb") as handle:
                self.assertEqual(handle.read(1), b"a")
            with ours.open("a", encoding="utf-8") as handle:
                handle.write("!")
            self.assertEqual(ours.read_text(encoding="utf-8", errors="strict").replace("\r\n", "\n"), "a\nb!")

    def test_content_method_errors_match_pathlib(self):
        with tempfile.TemporaryDirectory() as folder:
            ours, theirs = bp.Path(folder) / "none.txt", pathlib.Path(folder) / "none.txt"
            self.assertEqual(outcome(ours.read_text)[:2], outcome(theirs.read_text)[:2])
            for call in (lambda p: p.write_text(b"bytes"), lambda p: p.write_text(5), lambda p: p.write_bytes("text"),
                         lambda p: p.write_bytes(5)):
                self.assertEqual(outcome(lambda: call(ours)), outcome(lambda: call(theirs)))
            self.assertFalse((pathlib.Path(folder) / "none.txt").exists())          # a rejected write never created it
            with self.assertRaises(FileNotFoundError):
                ours.read_bytes()
            with self.assertRaises(IsADirectoryError if os.name != "nt" else PermissionError):
                bp.Path(folder).read_bytes()

    def test_operating_system_methods_are_absent_in_v1(self):
        path = bp.Path("a")
        for name in ("exists", "is_dir", "is_file", "iterdir", "glob", "rglob", "walk", "mkdir", "rmdir", "unlink",
                     "rename", "replace", "touch", "stat", "resolve", "absolute", "cwd", "home", "expanduser"):
            self.assertFalse(hasattr(path, name), name)
        with self.assertRaises(AttributeError):
            path.exists()


class ContractTests(unittest.TestCase):
    def test_module_imports_nothing(self):
        source = (support.V1 / "brisart_path.py").read_text()
        self.assertTrue(source.isascii())
        for node in ast.walk(ast.parse(source)):
            self.assertNotIsInstance(node, (ast.Import, ast.ImportFrom))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"__import__", "eval", "exec", "compile", "globals", "locals"})

    def test_module_runs_alone_in_an_empty_namespace(self):
        path = support.V1 / "brisart_path.py"
        source = path.read_text()
        namespace = {"__name__": "alone_brisart_path", "__file__": str(path)}
        exec(compile(source, str(path), "exec"), namespace)
        self.assertEqual(namespace["_NATIVE_WINDOWS"], namespace["_looks_like_windows"](str(path)))
        namespace = {"__name__": "alone_brisart_path"}
        exec(compile(source, "<no file>", "exec"), namespace)
        self.assertEqual(namespace["_HERE"], "")
        self.assertIs(namespace["PurePath"]("a").__class__, namespace["PurePosixPath"])

    def test_public_names_equal_pathlibs(self):
        self.assertEqual(sorted(bp.__all__), sorted(pathlib.__all__))
        for name in bp.__all__:
            self.assertTrue(hasattr(bp, name))
        for name in ("PurePath", "PurePosixPath", "PureWindowsPath"):
            ours, theirs = getattr(bp, name), getattr(pathlib, name)
            for member in dir(theirs):
                if member.startswith("_") or member in ("is_junction", "from_uri"):
                    continue
                self.assertTrue(hasattr(ours, member), "%s lacks %s" % (name, member))

    def test_deprecated_extra_arguments_are_accepted_silently(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.assertEqual(bp.PurePosixPath("/a/b/c").relative_to("/a", "b"), bp.PurePosixPath("c"))
            self.assertTrue(bp.PurePosixPath("/a/b/c").is_relative_to("/a", "b"))


if __name__ == "__main__":
    unittest.main()
