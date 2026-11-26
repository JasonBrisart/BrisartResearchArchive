"""
File: scripts/benchmark_retrieval.py

Purpose
-------
Compare offline document ranking on the installed Python source library.

This Linux-only tool compares the application’s Brisart ranking with benchmark-only
retrieval baselines on an installed Python source corpus. It is not an application
dependency or an alternative runtime engine.

Public operations: block ().

Communication / relationships
-----------------------------
Brisart and the benchmark-only SQLite FTS5, TF-IDF and ripgrep modes run one process at
a time.

Each mode indexes the same source texts and writes per-query rankings. A seccomp filter
denies socket and connection syscalls before corpus indexing and validates IPv4 and IPv6
denial.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Concrete calls within this file include sqlite3.connect.

Settings / parameters
---------------------
The mode selects a ranker; BRISART_NATIVE_API applies only to the two Brisart modes.

Call signatures: block().

Edge cases
----------
Socket denial must be enforced and probed before searching; prepare regenerates the
query set.

The designated declaration file is one labeled target, not a human relevance judgment.
The benchmark does not measure answer truth, desktop behavior or performance on an
independent research library.

Explicit exception branches or raised errors in this file include PermissionError,
RuntimeError.

Known limitations
-----------------
Linux only. The declaring file is the labeled target; answer quality and GUI are not
measured.

Developer tooling is not part of the normal desktop request path. Benchmark-only
dependencies do not become runtime requirements of the offline research assistant.

Examples
--------
python benchmark_retrieval.py Offline_AI

For a concrete entry point, inspect `block`; invoke it through the existing application entry
point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
"""
import ast, ctypes as C, errno, hashlib, json, os, re, socket, sqlite3, sys, sysconfig, time
from pathlib import Path

def block():
    lib=C.CDLL('libseccomp.so.2'); lib.seccomp_init.restype=C.c_void_p
    lib.seccomp_rule_add.argtypes=[C.c_void_p,C.c_uint32,C.c_int,C.c_uint]
    lib.seccomp_load.argtypes=[C.c_void_p]; lib.seccomp_release.argtypes=[C.c_void_p]
    ctx=lib.seccomp_init(0x7fff0000)
    assert ctx
    for name in (b'socket',b'socketpair',b'connect',b'sendto',b'sendmsg',b'sendmmsg',b'io_uring_setup'):
        n=lib.seccomp_syscall_resolve_name(name)
        assert n>=0 and lib.seccomp_rule_add(ctx,0x50000|errno.EPERM,n,0)==0
    assert lib.seccomp_load(ctx)==0
    lib.seccomp_release(ctx)
    for family in (socket.AF_INET,socket.AF_INET6):
        try:
            with socket.socket(family,socket.SOCK_STREAM): pass
        except PermissionError as e: assert e.errno==errno.EPERM
        else: raise RuntimeError('socket not blocked')

block()
root=Path(__file__).resolve().parent
mode=sys.argv[1]
stdlib=Path(sysconfig.get_path('stdlib'))
files=sorted(p for p in stdlib.glob('*.py') if 500<p.stat().st_size<44000 and p.name!='this.py')
docs={p.name:p.read_text(encoding='utf-8') for p in files}
if mode=='prepare':
    from collections import Counter
    symbols=[]
    for name,text in docs.items():
        for node in ast.parse(text).body:
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and not node.name.startswith('_'):
                summary=(ast.get_docstring(node) or '').splitlines()
                if summary and len(summary[0].split())>=5:
                    symbols.append((name,node.name,summary[0]))
    counts=Counter(symbol for _,symbol,_ in symbols); cases=[]
    for name,symbol,summary in [item for item in symbols if counts[item[1]]==1][:120]:
        cases.extend([('identifier',f'Where is {symbol} defined?',name),('docstring',summary,name)])
        if symbol.isalpha() and len(symbol)>=6 and symbol.islower() and symbol[-2]!=symbol[-3]:
            cases.append(('typo',symbol[:-3]+symbol[-2]+symbol[-3]+symbol[-1],name))
    (root/'queries.json').write_text(json.dumps(cases,indent=2)); print(len(docs),len(cases));sys.exit()
cases=json.loads((root/'queries.json').read_text())
if mode in ('baseline','Offline_AI'):
    sys.path[:0]=[str(root/mode),str(Path(os.environ['BRISART_NATIVE_API']).resolve())]
    from brisart_ai.knowledge.index import Index
    from brisart_ai.knowledge.ranker import search
    idx=Index(':memory:')
    for name,text in docs.items(): idx.add_source('file',name,name,text,extension='py')
    def lookup(q): return [r['location'] for r in search(idx,q,10,source_type='file')]
elif mode=='ripgrep':
    import subprocess, tempfile
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    scratch=tempfile.TemporaryDirectory()
    for name,text in docs.items(): (Path(scratch.name)/name).write_text(text,encoding='utf8')
    def lookup(q):
        words=[word for word in dict.fromkeys(re.findall(r'[a-z0-9]+',q.lower())) if word not in ENGLISH_STOP_WORDS]
        if not words: return []
        result=subprocess.run(['rg','--no-config','--count-matches','--ignore-case','--word-regexp',
                               '-e','|'.join(words),'.'],cwd=scratch.name,capture_output=True,text=True)
        if result.returncode not in (0,1): raise RuntimeError(result.stderr)
        counts=[(int(count),Path(name).name) for name,count in (line.rsplit(':',1) for line in result.stdout.splitlines())]
        return [name for _,name in sorted(counts,key=lambda pair:(-pair[0],pair[1]))[:10]]
else:
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
    if mode=='tfidf':
        vector=TfidfVectorizer(stop_words='english',ngram_range=(1,2),sublinear_tf=True)
        matrix=vector.fit_transform([name+'\n'+text for name,text in docs.items()]); names=list(docs)
        def lookup(q):
            scores=(matrix @ vector.transform([q]).T).toarray().ravel()
            return [names[i] for i in sorted(range(len(scores)),key=lambda i:(-scores[i],i)) if scores[i]>0][:10]
    else:
        db=sqlite3.connect(':memory:'); tok='porter unicode61' if mode=='porter' else 'unicode61'
        db.execute(f"create virtual table t using fts5(path UNINDEXED,title,body,tokenize='{tok}')")
        db.executemany('insert into t values (?,?,?)',[(name,name,text) for name,text in docs.items()])
        def lookup(q):
            words=[word for word in dict.fromkeys(re.findall(r'[a-z0-9]+',q.lower())) if word not in ENGLISH_STOP_WORDS]
            return [row[0] for row in db.execute('select path from t where t match ? order by bm25(t,0,2,1),rowid limit 10',(' OR '.join(f'"{word}"' for word in words),))] if words else []
results=[]
for kind,query,target in cases:
    t=time.perf_counter(); found=lookup(query); ms=(time.perf_counter()-t)*1000
    results.append(dict(kind=kind,query=query,target=target,rank=(found.index(target)+1 if target in found else None),results=found,ms=ms))
(root/f'{mode}.json').write_text(json.dumps(dict(documents=len(docs), sha256=hashlib.sha256(json.dumps(docs).encode()).hexdigest(),python=sys.version,sqlite=sqlite3.sqlite_version,network='seccomp; IPv4 and IPv6 socket probes denied',results=results),indent=2))

