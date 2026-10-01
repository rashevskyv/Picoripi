"""Empirical consistency check of translation_prompts/glossary.json (no Qt)."""
import json, re, sys, unicodedata, collections
from difflib import SequenceMatcher

PATH = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/pico/translation_prompts/glossary.json"
d = json.load(open(PATH, encoding="utf-8"))

def norm(v):  # == GlossaryManager.normalize_term
    v = unicodedata.normalize("NFKD", v or "")
    v = "".join(c for c in v if not unicodedata.combining(c)).lower().replace("#", " ")
    return re.sub(r"\s+", " ", v).strip()

def canon(v):  # stronger: strip punctuation, articles, plural -s/-es, possessive 's
    v = norm(v)
    v = re.sub(r"[^\w\s]", " ", v)
    toks = [t for t in v.split() if t not in {"the", "a", "an", "of"}]
    out = []
    for t in toks:
        t = re.sub(r"'s$", "", t)
        if len(t) > 4 and t.endswith("ies"): t = t[:-3] + "y"
        elif len(t) > 4 and t.endswith("es") and t[-3] in "sxz": t = t[:-2]
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"): t = t[:-1]
        out.append(t)
    return " ".join(out)

def first_tr(t):
    return (t or "").split(";")[0].strip()

def uk_stem(w):
    w = w.lower().strip("«»\"'()")
    for e in ("ями","ами","ові","еві","ого","ому","ими","ів","ям","ам","ах","ях","ою","ею","ий","ій","ом","ем","а","е","и","і","о","у","я","ь","ю"):
        if len(w) - len(e) >= 4 and w.endswith(e): return w[:-len(e)]
    return w

print(f"entries: {len(d)}")
print("sections:", dict(collections.Counter(e.get('section') for e in d)))
print("status values:", dict(collections.Counter(e.get('status','') for e in d)))
print("with notes:", sum(1 for e in d if e.get('notes')), " with {{TERM}} in notes:", sum(1 for e in d if '{{TERM}}' in (e.get('notes') or '')))
print("multi-translation (';'):", sum(1 for e in d if ';' in (e.get('translation') or '')))
print("empty translation:", sum(1 for e in d if not (e.get('translation') or '').strip()))

# 1. exact-duplicate originals / normalize_term duplicates
by_exact = collections.Counter(e['original'] for e in d)
print("\n[1] exact duplicate originals:", sum(1 for k,v in by_exact.items() if v>1))
by_norm = collections.defaultdict(list)
for e in d: by_norm[norm(e['original'])].append(e)
dups = {k:v for k,v in by_norm.items() if len(v)>1}
print("    normalize_term duplicates:", len(dups))
for k,v in dups.items(): print("     ", [ (e['original'], e['translation'], e.get('section')) for e in v])

# 2. canonical (case/plural/article/punct) collisions
by_canon = collections.defaultdict(list)
for e in d: by_canon[canon(e['original'])].append(e)
cdups = {k:v for k,v in by_canon.items() if len(v)>1}
print(f"\n[2] canonical-form collisions (case/plural/article/punct): {len(cdups)} groups, {sum(len(v) for v in cdups.values())} entries")
diff_tr = 0
for k,v in cdups.items():
    trs = {uk_stem(first_tr(e['translation']).split()[0]) if first_tr(e['translation']) else '' for e in v}
    flag = "  <-- DIFFERENT TRANSLATION" if len(trs)>1 else ""
    if flag: diff_tr += 1
    print("     ", [ (e['original'], e['translation'], e.get('section')) for e in v], flag)
print("    ...of which translation differs by stem:", diff_tr)

# 3. term families: entries sharing a capitalised source token (e.g. Hylia / Hylian / Lake Hylia)
tok_index = collections.defaultdict(list)
for e in d:
    for t in set(re.findall(r"[A-Za-z][A-Za-z'\-]{3,}", e['original'])):
        tok_index[t.lower()].append(e)
STOP = {"the","and","with","from","great","small","little","king","queen","lord","sword","shield","boots","mask","bottle","key","ring","wand","rod","magic","piece","pieces","forest","mountain","cave","lake","house","shop","town","village","room","north","south","east","west"}
fam = {t:v for t,v in tok_index.items() if len(v)>1 and t not in STOP}
print(f"\n[3] shared-token families (token >=4 chars, excluding generic words): {len(fam)}")
inconsistent = []
for t,v in sorted(fam.items(), key=lambda kv:-len(kv[1])):
    # how is the token rendered in each translation? collect uk stems of all translation words, look for a shared one
    renders = collections.Counter()
    for e in v:
        words = [uk_stem(w) for w in re.findall(r"[А-ЯІЇЄҐа-яіїєґ'’]{4,}", first_tr(e['translation']))]
        renders.update(set(words))
    shared = [w for w,c in renders.items() if c >= 2]
    if not shared:
        inconsistent.append((t, [(e['original'], e['translation']) for e in v]))
print("    families with NO shared Ukrainian stem across members (candidate divergent rendering):", len(inconsistent))
for t, members in inconsistent[:40]:
    print(f"     {t}: {members}")

# 4. same translation stem -> different originals (collisions on the target side)
by_tr = collections.defaultdict(list)
for e in d:
    k = " ".join(uk_stem(w) for w in first_tr(e['translation']).lower().split())
    if k: by_tr[k].append(e)
tdups = {k:v for k,v in by_tr.items() if len({e['original'] for e in v})>1}
print(f"\n[4] same translation (stemmed) used for different originals: {len(tdups)}")
for k,v in list(tdups.items())[:30]: print("     ", k, "<-", [e['original'] for e in v])

# 5. near-duplicates per possible_duplicate_pairs heuristic
def key(e): return "".join(ch for ch in e['original'].casefold() if ch.isalnum())
pairs=[]
for i,l in enumerate(d):
    lk=key(l)
    if len(lk)<4: continue
    for r in d[i+1:]:
        if l.get('section') and r.get('section') and l['section']!=r['section']: continue
        rk=key(r)
        if lk==rk or len(rk)<4 or lk[:2]!=rk[:2] or abs(len(lk)-len(rk))>3: continue
        if SequenceMatcher(None,lk,rk).ratio()>=0.88: pairs.append((l['original'],r['original']))
print(f"\n[5] possible_duplicate_pairs() heuristic hits: {len(pairs)}")
for p in pairs[:30]: print("     ", p)

# 6. substring containment: a shorter term wholly inside a longer one (matching precedence)
norms = [(norm(e['original']), e) for e in d]
contained = 0; ex=[]
for a,ea in norms:
    for b,eb in norms:
        if a!=b and re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)", b):
            contained += 1
            if len(ex)<25: ex.append((ea['original'], '⊂', eb['original'], '|', ea['translation'], '/', eb['translation']))
print(f"\n[6] term-inside-longer-term pairs (both will be injected by find_matches): {contained}")
for x in ex: print("     ", *x)
