import re, sys, zlib
data = open(sys.argv[1],'rb').read()
out=[]
for m in re.finditer(rb'stream\r?\n', data):
    start = m.end()
    end = data.find(b'endstream', start)
    if end < 0: continue
    raw = data[start:end]
    try: s = zlib.decompress(raw)
    except Exception: s = raw
    out.append(s)
blob = b'\n'.join(out)
# text-showing operators: (..) Tj   and  [(..)..] TJ
txt=[]
for m in re.finditer(rb'\((?:\\.|[^\\()])*\)', blob):
    t = m.group(0)[1:-1]
    t = re.sub(rb'\\([()\\])', rb'\1', t)
    if t.strip(): txt.append(t.decode('latin-1'))
print("---- extracted text runs ----")
for t in txt: print(repr(t))
