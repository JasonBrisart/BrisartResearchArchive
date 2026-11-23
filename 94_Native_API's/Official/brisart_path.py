"""
File: v1/brisart_path.py

Purpose
-------
BrisartPath -- a from-spec, pure-Python implementation of the pathlib
path model (CPython 3.12), replacing pathlib.PurePath, PurePosixPath,
PureWindowsPath, Path, PosixPath and WindowsPath in Brisart Research
Archive tooling. v1 is a behavioural copy: names, return types, results
and exception types and messages follow pathlib 3.12 wherever this
module can reproduce them without importing anything.

Public interface:

- PurePath(*segments) -- Platform-neutral base. Calling PurePath(...)
  returns a PureWindowsPath or a PurePosixPath for the native platform.

- PurePosixPath(*segments), PureWindowsPath(*segments) -- The two lexical
  path flavours; both work on any platform.

- Path(*segments), PosixPath(*segments), WindowsPath(*segments) --
  Concrete paths. A PosixPath cannot be created on Windows or a
  WindowsPath on POSIX (NotImplementedError), as in pathlib.

- Lexical members shared by every path: drive, root, anchor, parts, name,
  suffix, suffixes, stem, parent, parents, as_posix(), as_uri(),
  is_absolute(), is_reserved(), is_relative_to(), relative_to(),
  with_name(), with_stem(), with_suffix(), with_segments(), joinpath(),
  match(), "/" and "str(path)", repr(), hashing, equality and ordering,
  os.fspath() support through __fspath__, bytes(path) and pickling.

- Path I/O (the part that needs no import): open(), read_text(),
  read_bytes(), write_text(), write_bytes(), all through the built-in
  open().

Design notes:

pathlib is the reference, so v1 keeps its structure: a path stores its raw
segments, splits them lazily into drive, root and a tail of components,
and rebuilds its string from those parts. The two platform "flavours"
(ntpath and posixpath in the original) are two small objects inside this
file that supply separators, splitroot, splitdrive, join and case
folding. Nothing is imported, so the file can be copied into any tool on
its own; the cost is that everything pathlib gets from other modules is
written out here:

1. match() in pathlib compiles the pattern with fnmatch and re. Here the
   same pattern rules (the "*" component that needs at least one
   character, fnmatch sets and ranges, "?", the path text with separators
   swapped for newlines, anchored matching for patterns with a drive or
   root and right-to-left matching for relative ones) run on a small
   backtracking matcher with the same atomic "star then fixed text"
   groups that fnmatch.translate produces. Failed (node, position) pairs
   are remembered, so matching never goes exponential.

2. as_uri() percent-encodes with its own table (letters, digits and
   "_.-~/" stay as they are), the same set urllib.parse.quote_from_bytes
   leaves alone.

3. The parents sequence is its own small class with the pathlib behaviour
   (negative indexes, slices returning tuples, len, iteration, in).

4. The native platform cannot be read from os.name, so it is inferred
   from this file's own location: a drive letter or a leading double
   backslash means Windows, anything else POSIX. See Edge cases.

Communication / relationships
-----------------------------

Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on other API modules. The
built-in open() is used for file content; no os, io, sys, re, fnmatch,
functools, warnings or urllib code is used. Behaviour is cross-checked
against pathlib on both flavours, including its exceptions, by
v1/tests/test_path.py (tests may import the standard library; this
module may not).

Settings / parameters
---------------------

- Flavour -- Chosen by the class: PurePosixPath and PosixPath use "/";
  PureWindowsPath and WindowsPath use "\\" as separator, accept "/" as an
  alternative separator and compare case-insensitively (str.lower()).

- case_sensitive -- match() only. None (default) follows the flavour;
  True or False overrides it.

- walk_up -- relative_to() only. False (default) refuses to produce ".."
  parts; True allows them.

- mode, buffering, encoding, errors, newline -- open() and the text
  helpers; passed to the built-in open() unchanged.

Edge cases
----------

- Empty segments and "." components vanish: PurePath("a//b/./c") is
  a/b/c, PurePath("") is ".", and a "." at the start of a relative path
  is dropped too. ".." components are never collapsed.

- POSIX keeps exactly two leading slashes as the root "//" and collapses
  one, three or more into "/". Windows treats "//server/share" and the
  "?/UNC" and device forms as a drive, gives "c:" and "c:/" different
  roots, and adds "./" in front of a relative first component that would
  read as a drive.

- Joining: the last absolute segment wins; on Windows a segment with a
  different drive discards what came before.

- Comparison and hashing use the case-folded text of the flavour; paths of
  different flavours are never equal and cannot be ordered.

- PurePath("a") / PureWindowsPath("b") converts the other path to its
  as_posix() text first, as pathlib does.

- Arguments must be str or objects whose __fspath__ returns str; bytes
  raise TypeError.

- The native flavour comes from this file's location: if it is loaded
  where __file__ does not exist, the native flavour is POSIX. Use
  PurePosixPath or PureWindowsPath explicitly when that matters.

- bytes(path) and as_uri() encode with UTF-8; surrogateescape is used on
  POSIX and surrogatepass on Windows, matching the usual file system
  encoding on each.

Known limitations
-----------------

- Path has only open(), read_text(), read_bytes(), write_text() and
  write_bytes(). Everything else in pathlib that asks the operating
  system (stat, exists, is_dir, is_file, iterdir, glob, rglob, walk,
  mkdir, rmdir, unlink, rename, replace, touch, chmod, resolve, absolute,
  cwd, home, expanduser, owner, group, readlink, symlink_to and
  friends) is not provided, because it cannot be written without an
  import. Calling one raises AttributeError.

- Path does not accept keyword arguments and is not a context manager;
  pathlib 3.12 allows both only with a DeprecationWarning, and no warning
  can be issued here. relative_to() and is_relative_to() accept the
  deprecated extra positional arguments but do not warn.

- isinstance(path.parents, collections.abc.Sequence) is False, and
  isinstance(path, os.PathLike) is True only because PathLike recognises
  __fspath__.

- Case folding uses str.lower() on Windows paths and simple upper and
  lower comparison in match(); the Windows API compares with its own
  table, and the re module in pathlib has a few more case-insensitive
  equivalences, so rare non-ASCII names can differ.

- Sets in match() patterns that contain characters other than ASCII are
  compared by code point after case folding.

- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------

Run with the v1 folder on sys.path (for example, from inside v1/).
::
    from brisart_path import PurePosixPath, PureWindowsPath
    p = PurePosixPath("/usr") / "lib" / "python3.12" / "site.py"
    assert (p.name, p.suffix, p.stem) == ("site.py", ".py", "site")
    assert p.parent == PurePosixPath("/usr/lib/python3.12")
    assert p.parents[-1] == PurePosixPath("/")
    assert p.match("*.py") and p.match("/usr/*/*/site.py")
    assert p.relative_to("/usr").as_posix() == "lib/python3.12/site.py"
    assert p.with_suffix(".txt").as_uri() == "file:///usr/lib/python3.12/site.txt"
    w = PureWindowsPath("C:/Users/Jason/Docs")
    assert (w.drive, w.root, w.anchor) == ("C:", chr(92), "C:" + chr(92))
    assert w == PureWindowsPath("c:/users/jason/DOCS")
    assert w.parts[0] == "C:" + chr(92) and w.parts[-1] == "Docs"
    assert PureWindowsPath("con.txt").is_reserved()
    assert PurePosixPath("a//b/./c").as_posix() == "a/b/c"
    try:
        PurePosixPath("/a").relative_to("/b")
    except ValueError:
        pass
"""
_WIN_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} |
    {"COM" + c for c in "123456789\xb9\xb2\xb3"} |
    {"LPT" + c for c in "123456789\xb9\xb2\xb3"}
)
_URL_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~/")


# --------------------------------------------------------------------------- native platform

def _looks_like_windows(location):
    """True when a file location looks like a Windows path: a drive letter and colon, or a UNC prefix."""
    if location[:2] == "\\\\":
        return True
    return len(location) >= 2 and location[1] == ":" and location[0].isalpha()


try:
    _HERE = __file__
except NameError:
    _HERE = ""
_NATIVE_WINDOWS = _looks_like_windows(_HERE)


# --------------------------------------------------------------------------- flavours

class _PosixFlavour:
    """What posixpath supplies to pathlib: separators, splitroot, join and case rules."""
    sep = "/"
    altsep = None

    def normcase(self, s):
        return s

    def isabs(self, s):
        return s.startswith("/")

    def splitroot(self, p):
        if p[:1] != "/":
            return "", "", p
        if p[1:2] != "/" or p[2:3] == "/":
            return "", "/", p[1:]
        return "", p[:2], p[2:]

    def splitdrive(self, p):
        return "", p

    def join(self, a, *p):
        path = a
        for b in p:
            if b.startswith("/"):
                path = b
            elif not path or path.endswith("/"):
                path += b
            else:
                path += "/" + b
        return path


class _NtFlavour:
    """What ntpath supplies to pathlib: separators, splitroot, join and case rules."""
    sep = "\\"
    altsep = "/"

    def normcase(self, s):
        return s.replace("/", "\\").lower()

    def isabs(self, s):
        s = s[:3].replace("/", "\\")
        return s.startswith("\\") or s.startswith(":\\", 1)

    def splitroot(self, p):
        normp = p.replace("/", "\\")
        if normp[:1] == "\\":
            if normp[1:2] == "\\":
                # UNC drives (\\server\share, \\?\UNC\server\share) and device drives (\\.\device, \\?\device)
                start = 8 if normp[:8].upper() == "\\\\?\\UNC\\" else 2
                index = normp.find("\\", start)
                if index == -1:
                    return p, "", ""
                index2 = normp.find("\\", index + 1)
                if index2 == -1:
                    return p, "", ""
                return p[:index2], p[index2:index2 + 1], p[index2 + 1:]
            return "", p[:1], p[1:]
        if normp[1:2] == ":":
            if normp[2:3] == "\\":
                return p[:2], p[2:3], p[3:]
            return p[:2], "", p[2:]
        return "", "", p

    def splitdrive(self, p):
        drive, root, tail = self.splitroot(p)
        return drive, root + tail

    def join(self, path, *paths):
        result_drive, result_root, result_path = self.splitroot(path)
        for p in paths:
            p_drive, p_root, p_path = self.splitroot(p)
            if p_root:
                if p_drive or not result_drive:
                    result_drive = p_drive
                result_root = p_root
                result_path = p_path
                continue
            elif p_drive and p_drive != result_drive:
                if p_drive.lower() != result_drive.lower():
                    result_drive = p_drive
                    result_root = p_root
                    result_path = p_path
                    continue
                result_drive = p_drive
            if result_path and result_path[-1] not in "\\/":
                result_path = result_path + "\\"
            result_path = result_path + p_path
        if (result_path and not result_root and
                result_drive and result_drive[-1:] not in ":\\/"):
            return result_drive + "\\" + result_path
        return result_drive + result_root + result_path


_POSIX = _PosixFlavour()
_NT = _NtFlavour()
_NATIVE = _NT if _NATIVE_WINDOWS else _POSIX


def _is_case_sensitive(flavour):
    return flavour.normcase("Aa") == "Aa"


# --------------------------------------------------------------------------- pattern matching for match()

_STAR = "*"      # fnmatch star followed by nothing that can be skipped: ".*"
_PLUS = "+"      # a whole component "*": ".+"
_ATOMIC = "@"    # "(?>.*?fixed)": the first place fixed text matches, never backtracked
_SWAP_SEP_AND_NEWLINE = {
    "/": {ord("/"): "\n", ord("\n"): "/"},
    "\\": {ord("\\"): "\n", ord("\n"): "\\"},
}
_NODE_CACHE = {}


def _parse_set(stuff):
    """Read the body of a regular-expression set the way fnmatch writes it: escapes, then x-y ranges."""
    items = []                                   # (character, was_escaped)
    i = 0
    while i < len(stuff):
        if stuff[i] == "\\" and i + 1 < len(stuff):
            items.append((stuff[i + 1], True))
            i += 2
        else:
            items.append((stuff[i], False))
            i += 1
    chars = []
    ranges = []
    k = 0
    while k < len(items):
        char = items[k][0]
        if k + 2 < len(items) and items[k + 1] == ("-", False):
            ranges.append((char, items[k + 2][0]))
            k += 3
        else:
            chars.append(char)
            k += 1
    return tuple(chars), tuple(ranges)


def _translate(pat):
    """fnmatch.translate() for one pattern part, as a list of matcher nodes instead of regex text."""
    res = []
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        i = i + 1
        if c == "*":
            if not res or res[-1] is not _STAR:
                res.append(_STAR)
        elif c == "?":
            res.append(("any",))
        elif c == "[":
            j = i
            if j < n and pat[j] == "!":
                j = j + 1
            if j < n and pat[j] == "]":
                j = j + 1
            while j < n and pat[j] != "]":
                j = j + 1
            if j >= n:
                res.append(("c", "["))
            else:
                stuff = pat[i:j]
                if "-" not in stuff:
                    stuff = stuff.replace("\\", "\\\\")
                else:
                    chunks = []
                    k = i + 2 if pat[i] == "!" else i + 1
                    while True:
                        k = pat.find("-", k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k + 1
                        k = k + 3
                    chunk = pat[i:j]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += "-"
                    for k in range(len(chunks) - 1, 0, -1):
                        if chunks[k - 1][-1] > chunks[k][0]:
                            chunks[k - 1] = chunks[k - 1][:-1] + chunks[k][1:]
                            del chunks[k]
                    stuff = "-".join(s.replace("\\", "\\\\").replace("-", "\\-") for s in chunks)
                i = j + 1
                if not stuff:
                    res.append(("never",))
                elif stuff == "!":
                    res.append(("any",))
                else:
                    negated = stuff[0] == "!"
                    if negated:
                        stuff = stuff[1:]
                    chars, ranges = _parse_set(stuff)
                    res.append(("set", negated, chars, ranges))
        else:
            res.append(("c", c))
    nodes = []
    i, n = 0, len(res)
    while i < n and res[i] is not _STAR:
        nodes.append(res[i])
        i += 1
    while i < n:
        i += 1                                   # the star
        if i == n:
            nodes.append((_STAR,))
            break
        fixed = []
        while i < n and res[i] is not _STAR:
            fixed.append(res[i])
            i += 1
        if i == n:
            nodes.append((_STAR,))
            nodes.extend(fixed)
        else:
            nodes.append((_ATOMIC, tuple(fixed)))
    return nodes


def _compile_lines(pattern_lines):
    """Matcher nodes for a pattern whose separators were swapped with newlines."""
    nodes = _NODE_CACHE.get(pattern_lines)
    if nodes is None:
        nodes = []
        for part in pattern_lines.splitlines(keepends=True):
            if part == "*\n":
                nodes.append((_PLUS,))
                nodes.append(("c", "\n"))
            elif part == "*":
                nodes.append((_PLUS,))
            else:
                nodes.extend(_translate(part))
        if len(_NODE_CACHE) >= 256:
            _NODE_CACHE.clear()
        _NODE_CACHE[pattern_lines] = nodes
    return nodes


def _same_char(a, b, fold):
    if a == b:
        return True
    return fold and (a.lower() == b.lower() or a.upper() == b.upper())


def _in_range(c, lo, hi):
    return lo <= c <= hi


def _node_matches(node, c, fold):
    kind = node[0]
    if kind == "c":
        return _same_char(c, node[1], fold)
    if kind == "any":
        return c != "\n"
    if kind == "set":
        variants = (c, c.lower(), c.upper()) if fold else (c,)
        found = False
        for v in variants:
            if v in node[2]:
                found = True
                break
            for lo, hi in node[3]:
                if _in_range(v, lo, hi):
                    found = True
                    break
            if found:
                break
        return found != node[1]
    return False                                 # "never"


def _run(nodes, text, starts, fold):
    """True if the nodes match text from one of the start positions through to its end."""
    n = len(text)
    total = len(nodes)
    failed = set()

    def go(i, p):
        while i < total:
            node = nodes[i]
            kind = node[0]
            if kind == _STAR or kind == _PLUS:
                if (i, p) in failed:
                    return False
                limit = p
                while limit < n and text[limit] != "\n":
                    limit += 1
                q = limit
                lowest = p + 1 if kind == _PLUS else p
                while q >= lowest:
                    if go(i + 1, q):
                        return True
                    q -= 1
                failed.add((i, p))
                return False
            if kind == _ATOMIC:
                fixed = node[1]
                size = len(fixed)
                q = p
                while True:
                    if q + size <= n:
                        ok = True
                        for k in range(size):
                            if not _node_matches(fixed[k], text[q + k], fold):
                                ok = False
                                break
                        if ok:
                            p = q + size
                            break
                    if q >= n or text[q] == "\n":
                        return False
                    q += 1
                i += 1
                continue
            if p < n and _node_matches(node, text[p], fold):
                p += 1
                i += 1
            else:
                return False
        return p == n

    for start in starts:
        if go(0, start):
            return True
    return False


def _match_lines(pattern_lines, lines, case_sensitive, anchored):
    nodes = _compile_lines(pattern_lines)
    fold = not case_sensitive
    if anchored:
        return _run(nodes, lines, (0,), fold)
    starts = [p for p in range(len(lines) + 1) if p == 0 or lines[p - 1] == "\n"]
    return _run(nodes, lines, starts, fold)


# --------------------------------------------------------------------------- small helpers

def _fspath(arg):
    """os.fspath() for the two argument kinds this module accepts: str/bytes and objects with __fspath__."""
    if isinstance(arg, (str, bytes)):
        return arg
    method = getattr(type(arg), "__fspath__", None)
    if method is None:
        raise TypeError("expected str, bytes or os.PathLike object, not " + type(arg).__name__)
    result = method(arg)
    if isinstance(result, (str, bytes)):
        return result
    raise TypeError("expected %s.__fspath__() to return str or bytes, not %s"
                    % (type(arg).__name__, type(result).__name__))


def _fsencode(text):
    return text.encode("utf-8", "surrogatepass" if _NATIVE_WINDOWS else "surrogateescape")


def _quote_bytes(raw):
    return "".join([chr(b) if (b < 128 and chr(b) in _URL_SAFE) else "%%%02X" % b for b in raw])


class _PathParents:
    """This object provides sequence-like access to the logical ancestors
    of a path.  Don't try to construct it yourself."""
    __slots__ = ("_path", "_drv", "_root", "_tail")

    def __init__(self, path):
        self._path = path
        self._drv = path.drive
        self._root = path.root
        self._tail = path._tail

    def __len__(self):
        return len(self._tail)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return tuple(self[i] for i in range(*idx.indices(len(self))))
        if idx >= len(self) or idx < -len(self):
            raise IndexError(idx)
        if idx < 0:
            idx += len(self)
        return self._path._from_parsed_parts(self._drv, self._root, self._tail[:-idx - 1])

    def __iter__(self):
        i = 0
        try:
            while True:
                yield self[i]
                i += 1
        except IndexError:
            return

    def __reversed__(self):
        for i in reversed(range(len(self))):
            yield self[i]

    def __contains__(self, value):
        for v in self:
            if v is value or v == value:
                return True
        return False

    def index(self, value, start=0, stop=None):
        if start is not None and start < 0:
            start = max(len(self) + start, 0)
        if stop is not None and stop < 0:
            stop += len(self)
        i = start
        while stop is None or i < stop:
            try:
                v = self[i]
            except IndexError:
                break
            if v is value or v == value:
                return i
            i += 1
        raise ValueError

    def count(self, value):
        return sum(1 for v in self if v is value or v == value)

    def __repr__(self):
        return "<{}.parents>".format(type(self._path).__name__)


# --------------------------------------------------------------------------- pure paths

class PurePath(object):
    """Base class for manipulating paths without I/O.

    PurePath represents a filesystem path and offers operations which
    don't imply any actual filesystem I/O.  Depending on your system,
    instantiating a PurePath will return either a PurePosixPath or a
    PureWindowsPath object.  You can also instantiate either of these classes
    directly, regardless of your system.
    """

    __slots__ = (
        "_raw_paths",
        "_drv", "_root", "_tail_cached",
        "_str",
        "_str_normcase_cached",
        "_parts_normcase_cached",
        "_lines_cached",
        "_hash",
    )
    _flavour = _NATIVE

    def __new__(cls, *args, **kwargs):
        """Construct a PurePath from one or several strings and or existing
        PurePath objects.  The strings and path objects are combined so as
        to yield a canonicalized path, which is incorporated into the
        new PurePath object.
        """
        if cls is PurePath:
            cls = PureWindowsPath if _NATIVE_WINDOWS else PurePosixPath
        return object.__new__(cls)

    def __reduce__(self):
        return (self.__class__, self.parts)

    def __init__(self, *args):
        paths = []
        for arg in args:
            if isinstance(arg, PurePath):
                if arg._flavour is not self._flavour:
                    paths.append(arg.as_posix())
                else:
                    paths.extend(arg._raw_paths)
            else:
                try:
                    path = _fspath(arg)
                except TypeError:
                    path = arg
                if not isinstance(path, str):
                    raise TypeError(
                        "argument should be a str or an os.PathLike "
                        "object where __fspath__ returns a str, "
                        "not %r" % type(path).__name__)
                paths.append(path)
        self._raw_paths = paths

    def with_segments(self, *pathsegments):
        """Construct a new path object from any number of path-like objects.
        Subclasses may override this method to customize how new path objects
        are created from methods like `iterdir()`.
        """
        return type(self)(*pathsegments)

    @classmethod
    def _parse_path(cls, path):
        if not path:
            return "", "", []
        sep = cls._flavour.sep
        altsep = cls._flavour.altsep
        if altsep:
            path = path.replace(altsep, sep)
        drv, root, rel = cls._flavour.splitroot(path)
        if not root and drv.startswith(sep) and not drv.endswith(sep):
            drv_parts = drv.split(sep)
            if len(drv_parts) == 4 and drv_parts[2] not in "?.":
                root = sep                       # e.g. //server/share
            elif len(drv_parts) == 6:
                root = sep                       # e.g. //?/unc/server/share
        parsed = [str(x) for x in rel.split(sep) if x and x != "."]
        return drv, root, parsed

    def _load_parts(self):
        paths = self._raw_paths
        if len(paths) == 0:
            path = ""
        elif len(paths) == 1:
            path = paths[0]
        else:
            path = self._flavour.join(*paths)
        drv, root, tail = self._parse_path(path)
        self._drv = drv
        self._root = root
        self._tail_cached = tail

    def _from_parsed_parts(self, drv, root, tail):
        path_str = self._format_parsed_parts(drv, root, tail)
        path = self.with_segments(path_str)
        path._str = path_str or "."
        path._drv = drv
        path._root = root
        path._tail_cached = tail
        return path

    @classmethod
    def _format_parsed_parts(cls, drv, root, tail):
        if drv or root:
            return drv + root + cls._flavour.sep.join(tail)
        elif tail and cls._flavour.splitdrive(tail[0])[0]:
            tail = ["."] + tail
        return cls._flavour.sep.join(tail)

    def __str__(self):
        """Return the string representation of the path, suitable for
        passing to system calls."""
        try:
            return self._str
        except AttributeError:
            self._str = self._format_parsed_parts(self.drive, self.root, self._tail) or "."
            return self._str

    def __fspath__(self):
        return str(self)

    def as_posix(self):
        """Return the string representation of the path with forward (/)
        slashes."""
        f = self._flavour
        return str(self).replace(f.sep, "/")

    def __bytes__(self):
        """Return the bytes representation of the path.  This is only
        recommended to use under Unix."""
        return _fsencode(str(self))

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.as_posix())

    def as_uri(self):
        """Return the path as a 'file' URI."""
        if not self.is_absolute():
            raise ValueError("relative path can't be expressed as a file URI")
        drive = self.drive
        if len(drive) == 2 and drive[1] == ":":
            prefix = "file:///" + drive          # a path on a local drive => file:///c:/a/b
            path = self.as_posix()[2:]
        elif drive:
            prefix = "file:"                     # a path on a network drive => file://host/share/a/b
            path = self.as_posix()
        else:
            prefix = "file://"                   # a POSIX path => file:///etc/hosts
            path = str(self)
        return prefix + _quote_bytes(_fsencode(path))

    @property
    def _str_normcase(self):
        try:
            return self._str_normcase_cached
        except AttributeError:
            if _is_case_sensitive(self._flavour):
                self._str_normcase_cached = str(self)
            else:
                self._str_normcase_cached = str(self).lower()
            return self._str_normcase_cached

    @property
    def _parts_normcase(self):
        try:
            return self._parts_normcase_cached
        except AttributeError:
            self._parts_normcase_cached = self._str_normcase.split(self._flavour.sep)
            return self._parts_normcase_cached

    @property
    def _lines(self):
        # The path text with separators and newlines swapped, for pattern matching.
        try:
            return self._lines_cached
        except AttributeError:
            path_str = str(self)
            if path_str == ".":
                self._lines_cached = ""
            else:
                self._lines_cached = path_str.translate(_SWAP_SEP_AND_NEWLINE[self._flavour.sep])
            return self._lines_cached

    def __eq__(self, other):
        if not isinstance(other, PurePath):
            return NotImplemented
        return self._str_normcase == other._str_normcase and self._flavour is other._flavour

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(self._str_normcase)
            return self._hash

    def __lt__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._parts_normcase < other._parts_normcase

    def __le__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._parts_normcase <= other._parts_normcase

    def __gt__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._parts_normcase > other._parts_normcase

    def __ge__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._parts_normcase >= other._parts_normcase

    @property
    def drive(self):
        """The drive prefix (letter or UNC path), if any."""
        try:
            return self._drv
        except AttributeError:
            self._load_parts()
            return self._drv

    @property
    def root(self):
        """The root of the path, if any."""
        try:
            return self._root
        except AttributeError:
            self._load_parts()
            return self._root

    @property
    def _tail(self):
        try:
            return self._tail_cached
        except AttributeError:
            self._load_parts()
            return self._tail_cached

    @property
    def anchor(self):
        """The concatenation of the drive and root, or ''."""
        return self.drive + self.root

    @property
    def name(self):
        """The final path component, if any."""
        tail = self._tail
        if not tail:
            return ""
        return tail[-1]

    @property
    def suffix(self):
        """
        The final component's last suffix, if any.

        This includes the leading period. For example: '.txt'
        """
        name = self.name
        i = name.rfind(".")
        if 0 < i < len(name) - 1:
            return name[i:]
        return ""

    @property
    def suffixes(self):
        """
        A list of the final component's suffixes, if any.

        These include the leading periods. For example: ['.tar', '.gz']
        """
        name = self.name
        if name.endswith("."):
            return []
        name = name.lstrip(".")
        return ["." + suffix for suffix in name.split(".")[1:]]

    @property
    def stem(self):
        """The final path component, minus its last suffix."""
        name = self.name
        i = name.rfind(".")
        if 0 < i < len(name) - 1:
            return name[:i]
        return name

    def with_name(self, name):
        """Return a new path with the file name changed."""
        if not self.name:
            raise ValueError("%r has an empty name" % (self,))
        f = self._flavour
        if not name or f.sep in name or (f.altsep and f.altsep in name) or name == ".":
            raise ValueError("Invalid name %r" % (name))
        return self._from_parsed_parts(self.drive, self.root, self._tail[:-1] + [name])

    def with_stem(self, stem):
        """Return a new path with the stem changed."""
        return self.with_name(stem + self.suffix)

    def with_suffix(self, suffix):
        """Return a new path with the file suffix changed.  If the path
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the path.
        """
        f = self._flavour
        if f.sep in suffix or f.altsep and f.altsep in suffix:
            raise ValueError("Invalid suffix %r" % (suffix,))
        if suffix and not suffix.startswith(".") or suffix == ".":
            raise ValueError("Invalid suffix %r" % (suffix))
        name = self.name
        if not name:
            raise ValueError("%r has an empty name" % (self,))
        old_suffix = self.suffix
        if not old_suffix:
            name = name + suffix
        else:
            name = name[:-len(old_suffix)] + suffix
        return self._from_parsed_parts(self.drive, self.root, self._tail[:-1] + [name])

    def relative_to(self, other, /, *_deprecated, walk_up=False):
        """Return the relative path to another path identified by the passed
        arguments.  If the operation is not possible (because this is not
        related to the other path), raise ValueError.

        The *walk_up* parameter controls whether `..` may be used to resolve
        the path.
        """
        other = self.with_segments(other, *_deprecated)
        for step, path in enumerate([other] + list(other.parents)):
            if self.is_relative_to(path):
                break
            elif not walk_up:
                raise ValueError(f"{str(self)!r} is not in the subpath of {str(other)!r}")
            elif path.name == "..":
                raise ValueError(f"'..' segment in {str(other)!r} cannot be walked")
        else:
            raise ValueError(f"{str(self)!r} and {str(other)!r} have different anchors")
        parts = [".."] * step + self._tail[len(path._tail):]
        return self.with_segments(*parts)

    def is_relative_to(self, other, /, *_deprecated):
        """Return True if the path is relative to another path or False."""
        other = self.with_segments(other, *_deprecated)
        return other == self or other in self.parents

    @property
    def parts(self):
        """A tuple giving access to the components in the filesystem path."""
        if self.drive or self.root:
            return (self.drive + self.root,) + tuple(self._tail)
        return tuple(self._tail)

    def joinpath(self, *pathsegments):
        """Combine this path with one or several arguments, and return a
        new path representing either a subpath (if all arguments are relative
        paths) or a totally different path (if one of the arguments is
        anchored).
        """
        return self.with_segments(self, *pathsegments)

    def __truediv__(self, key):
        try:
            return self.joinpath(key)
        except TypeError:
            return NotImplemented

    def __rtruediv__(self, key):
        try:
            return self.with_segments(key, self)
        except TypeError:
            return NotImplemented

    @property
    def parent(self):
        """The logical parent of the path."""
        drv = self.drive
        root = self.root
        tail = self._tail
        if not tail:
            return self
        return self._from_parsed_parts(drv, root, tail[:-1])

    @property
    def parents(self):
        """A sequence of this path's logical parents."""
        return _PathParents(self)

    def is_absolute(self):
        """True if the path is absolute (has both a root and, if applicable,
        a drive)."""
        if self._flavour is _NT:
            return bool(self.drive and self.root)
        for path in self._raw_paths:
            if path.startswith("/"):
                return True
        return False

    def is_reserved(self):
        """Return True if the path contains one of the special names reserved
        by the system, if any."""
        if self._flavour is _POSIX or not self._tail:
            return False
        if self.drive.startswith("\\\\"):
            return False                         # UNC paths are never reserved
        name = self._tail[-1].partition(".")[0].partition(":")[0].rstrip(" ")
        return name.upper() in _WIN_RESERVED_NAMES

    def match(self, path_pattern, *, case_sensitive=None):
        """
        Return True if this path matches the given pattern.
        """
        if not isinstance(path_pattern, PurePath):
            path_pattern = self.with_segments(path_pattern)
        if case_sensitive is None:
            case_sensitive = _is_case_sensitive(self._flavour)
        pattern_lines = path_pattern._lines
        _compile_lines(pattern_lines)
        if path_pattern.drive or path_pattern.root:
            return _match_lines(pattern_lines, self._lines, case_sensitive, True)
        elif path_pattern._tail:
            return _match_lines(pattern_lines, self._lines, case_sensitive, False)
        else:
            raise ValueError("empty pattern")


class PurePosixPath(PurePath):
    """PurePath subclass for non-Windows systems.

    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _POSIX
    __slots__ = ()


class PureWindowsPath(PurePath):
    """PurePath subclass for Windows systems.

    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    _flavour = _NT
    __slots__ = ()


# --------------------------------------------------------------------------- concrete paths

class Path(PurePath):
    """PurePath subclass that can read and write files.

    Depending on your system, instantiating a Path will return either a
    PosixPath or a WindowsPath object. You can also instantiate a PosixPath
    or WindowsPath directly, but cannot instantiate a WindowsPath on a POSIX
    system or vice versa. Only content access is provided in v1: open(),
    read_text(), read_bytes(), write_text() and write_bytes().
    """
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        if cls is Path:
            cls = WindowsPath if _NATIVE_WINDOWS else PosixPath
        return object.__new__(cls)

    def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        """
        Open the file pointed to by this path and return a file object, as
        the built-in open() function does.
        """
        return open(self, mode, buffering, encoding, errors, newline)

    def read_bytes(self):
        """
        Open the file in bytes mode, read it, and close the file.
        """
        with self.open(mode="rb") as f:
            return f.read()

    def read_text(self, encoding=None, errors=None):
        """
        Open the file in text mode, read it, and close the file.
        """
        with self.open(mode="r", encoding=encoding, errors=errors) as f:
            return f.read()

    def write_bytes(self, data):
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        view = memoryview(data)                  # type-check for the buffer interface before truncating the file
        with self.open(mode="wb") as f:
            return f.write(view)

    def write_text(self, data, encoding=None, errors=None, newline=None):
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str):
            raise TypeError("data must be str, not %s" % data.__class__.__name__)
        with self.open(mode="w", encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)


class PosixPath(Path, PurePosixPath):
    """Path subclass for non-Windows systems.

    On a POSIX system, instantiating a Path should return this object.
    """
    __slots__ = ()

    if _NATIVE_WINDOWS:
        def __new__(cls, *args, **kwargs):
            raise NotImplementedError("cannot instantiate %r on your system" % cls.__name__)


class WindowsPath(Path, PureWindowsPath):
    """Path subclass for Windows systems.

    On a Windows system, instantiating a Path should return this object.
    """
    __slots__ = ()

    if not _NATIVE_WINDOWS:
        def __new__(cls, *args, **kwargs):
            raise NotImplementedError("cannot instantiate %r on your system" % cls.__name__)


__all__ = [
    "PurePath",
    "PurePosixPath",
    "PureWindowsPath",
    "Path",
    "PosixPath",
    "WindowsPath",
]
