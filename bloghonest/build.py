#!/usr/bin/env python3
"""Blog de disseny social d'Honest — generador estatic.

Llegeix els articles numerats (01-…md a 32-…md) de ../Blog-DS i genera:
  dist/index.html            portada
  dist/articles/<slug>.html  una pagina per article
  dist/sitemap.xml, dist/robots.txt

Titulars i imatges: content.py (mateixa carpeta).
Us:   python3 build.py              web estatica a dist/
      python3 build.py --single X   una sola pagina HTML (navegacio per #) a X
Opcional: pip install markdown (si no hi es, usa un conversor intern)
"""
import html, os, re, sys, glob, datetime, random, hashlib, base64, json
from urllib.parse import quote
try:
    import markdown as _md
    def md_to_html(t): return _md.markdown(t, extensions=["extra", "sane_lists"])
except ImportError:  # sense dependencies: conversor minim (paragrafs, titols, llistes, cursiva, negreta, enllacos)
    def _inline(t):
        t = html.escape(t, quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", t)
        return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    def md_to_html(t):
        out = []
        t = re.sub(r"^(#{1,6}\s.*)$", r"\n\1\n", t, flags=re.M)
        for b in re.split(r"\n\s*\n", t.strip()):
            b = b.strip()
            m = re.match(r"^(#{1,6})\s+(.*)$", b)
            if m and "\n" not in b:
                n = len(m.group(1)); out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            elif re.match(r"^[-*+]\s", b):
                out.append("<ul>" + "".join("<li>" + _inline(re.sub(r"^[-*+]\s+", "", l)) + "</li>" for l in b.splitlines()) + "</ul>")
            elif b.startswith(">"):
                out.append("<blockquote><p>" + _inline(re.sub(r"^>\s?", "", b, flags=re.M)) + "</p></blockquote>")
            else:
                out.append("<p>" + _inline(b).replace("\n", " ") + "</p>")
        return "\n".join(out)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import content as _content
HEAD, IMG = _content.HEAD, _content.IMG
INLINE = getattr(_content, 'INLINE', {})
ARENA = getattr(_content, 'ARENA', {})
GIF = getattr(_content, 'GIF', {})       # imatge destacada animada (URL directa del GIF a Are.na)   # si un article hi es, les seves fotos venen d'Are.na

# Articles: carpeta articles/ del repo (la que edita Decap CMS); si no hi es, ../Blog-DS
SRC = os.environ.get("BLOG_SRC") or (os.path.join(HERE, "articles") if os.path.isdir(os.path.join(HERE, "articles"))
                                     else os.path.normpath(os.path.join(HERE, "..", "Blog-DS")))
OUT = os.path.join(HERE, "dist")
SITE = "https://honestpg.com/blog"   # URL base per al sitemap (canvia-la si cal)
MESOS = ["gener","febrer","març","abril","maig","juny","juliol","agost","setembre","octubre","novembre","desembre"]

# ------------------------------------------------------------------ lectura
def parse_front(txt):
    meta, body = {}, txt
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.S)
    if not m:
        return meta, body
    body = txt[m.end():]
    key = None
    for line in m.group(1).splitlines():
        if re.match(r"^\s+-\s+", line) and key:
            meta.setdefault(key, []).append(line.split("-", 1)[1].strip()); continue
        kv = re.match(r"^(\w+):\s*(.*)$", line)
        if not kv: continue
        key, val = kv.group(1), kv.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [t.strip() for t in val[1:-1].split(",") if t.strip()]
        elif val == "": meta[key] = []
        else: meta[key] = val.strip('"').strip("'")
    return meta, body

def slugify(s):
    s = s.lower()
    for a, b in (("à","a"),("è","e"),("é","e"),("í","i"),("ï","i"),("ò","o"),("ó","o"),("ú","u"),("ü","u"),("ç","c"),("l·l","ll"),("·","")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]

def _sources():
    """Articles numerats (NN-slug.md) i, despres, els nous del CMS (slug.md) per data."""
    num_files, new_files = [], []
    for path in glob.glob(os.path.join(SRC, "*.md")):
        fn = os.path.basename(path)
        if fn[:1].isupper() or fn.startswith(("post-", "_")):   # CLAUDE.md, FORMAT-POSTS.md, fitxes post-...
            continue
        m = re.match(r"^(\d+)-(.+)\.md$", fn)
        if m: num_files.append((int(m.group(1)), m.group(2), path))
        else: new_files.append(path)
    num_files.sort()
    last = max([n for n, _, _ in num_files] or [0])
    def fdate_of(p):
        m = re.search(r"^fecha_creacion:\s*['\"]?([0-9-]+)", open(p, encoding="utf-8").read(), re.M)
        return (m.group(1) if m else "9999", p)
    for i, path in enumerate(sorted(new_files, key=fdate_of)):
        num_files.append((last + 1 + i, os.path.basename(path)[:-3], path))
    return num_files

def load():
    arts = []
    for num, slug, path in _sources():
        slug = re.sub(r"-REFERENCIA$", "", slug)
        meta, body = parse_front(open(path, encoding="utf-8").read())
        body = body.strip()
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        title = meta.get("title") or (h1.group(1).strip() if h1 else slug)
        sub = ""
        m = re.match(r"^#\s+.+\n+###\s+(.+)\n", body)
        if m: sub, body = m.group(1).strip(), body[m.end():]
        elif h1: body = body[h1.end():]
        sub = meta.get("subtitol") or sub
        concept, _, form = title.partition(":")
        form = form.strip(); form = form[:1].upper() + form[1:]
        words = len(re.findall(r"\w+", body))
        html_body = md_to_html(body)
        # seccions (per a l'index lateral) amb id
        toc = []
        def h2(mm):
            t = re.sub(r"<[^>]+>", "", mm.group(1)); i = "s-" + slugify(t)
            toc.append((i, t)); return f'<h2 id="{i}">{mm.group(1)}</h2>'
        html_body = re.sub(r"<h2>(.*?)</h2>", h2, html_body)
        # primer paragraf = entrada; paragraf de definicio = destacat
        html_body = html_body.replace("<p>", '<p class="lead">', 1)
        html_body = re.sub(r"<p>(La definició[^<]*?:)", r'<p class="def">\1', html_body, count=1)
        arts.append(dict(num=num, slug=slug, title=title, concept=concept.strip(), form=form, sub=sub,
            head=meta.get("titular") or HEAD.get(num, title), img=IMG.get(num), own=meta.get("imatge") or "",
            tags=[t for t in meta.get("tags", []) if t != "disseny-social"],
            date=meta.get("fecha_creacion", ""), mins=max(1, round(words / 220)), words=words,
            fonts=meta.get("fonts", []), html=html_body, toc=toc))
    return arts

def fdate(d):
    try: y, m, dd = d.split("-"); return f"{int(dd)} {MESOS[int(m)-1]} {y}"
    except Exception: return d

def tagname(t): return t.replace("-", " ")
def e(s): return html.escape(s or "", quote=True)
DRE = re.compile(r"^https?://(www\.)?")
def dom(u): return DRE.sub("", u).split("/")[0]

# ------------------------------------------------------------------ imatges
# Castells en verd: composicio generativa (es mostra si la foto no carrega)
BG='#35754b'; GROUND='#2a6140'
TONES=['#1c4a2c','#23573a','#5c9670','#8fbb9c','#c6dfcd','#eef6f0']
def art_svg(seed, W=1600, H=900):
    r = random.Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
    base = H*0.84
    out = [f'<svg class="art" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>', f'<rect y="{base:.0f}" width="{W}" height="{H-base:.0f}" fill="{GROUND}"/>']
    if r.random() < .7:
        cr = min(W,H)*r.uniform(.07,.12)
        out.append(f'<circle cx="{W*r.uniform(.12,.88):.0f}" cy="{H*r.uniform(.14,.3):.0f}" r="{cr:.0f}" fill="{r.choice(TONES[3:])}"/>')
    unit = min(W,H)*r.uniform(.13,.17); ncol = max(2, int(W/(unit*1.9)))
    x = W*0.06; last = None
    for i in range(ncol):
        w = unit*r.choice([1,1,1.5,2])
        if x+w > W*0.96: break
        y = base; n = r.randint(1,4)
        for k in range(n):
            c = r.choice([t for t in TONES if t != last]); last = c; top = (k == n-1)
            kind = r.choice(['rect','sq','circ','arch'] + (['tri','dome','cyl'] if top else []))
            if kind == 'rect': hh = unit*r.choice([.5,.75,1]); out.append(f'<rect x="{x:.0f}" y="{y-hh:.0f}" width="{w:.0f}" height="{hh:.0f}" fill="{c}"/>')
            elif kind == 'sq': hh = w; out.append(f'<rect x="{x:.0f}" y="{y-hh:.0f}" width="{w:.0f}" height="{hh:.0f}" fill="{c}"/>')
            elif kind == 'circ': hh = w; out.append(f'<circle cx="{x+w/2:.0f}" cy="{y-w/2:.0f}" r="{w/2:.0f}" fill="{c}"/>')
            elif kind == 'arch':
                hh = unit*r.choice([.75,1]); rr = min(w*.3,hh*.6); cx = x+w/2
                out.append(f'<path d="M{x:.0f} {y-hh:.0f}H{x+w:.0f}V{y:.0f}H{cx+rr:.0f}A{rr:.0f} {rr:.0f} 0 0 0 {cx-rr:.0f} {y:.0f}H{x:.0f}Z" fill="{c}"/>')
            elif kind == 'tri': hh = w*r.choice([.8,1.1]); out.append(f'<path d="M{x:.0f} {y:.0f}L{x+w/2:.0f} {y-hh:.0f}L{x+w:.0f} {y:.0f}Z" fill="{c}"/>')
            elif kind == 'dome': hh = w/2; out.append(f'<path d="M{x:.0f} {y:.0f}A{w/2:.0f} {w/2:.0f} 0 0 1 {x+w:.0f} {y:.0f}Z" fill="{c}"/>')
            else: hh = unit*1.2; out.append(f'<rect x="{x+w*.2:.0f}" y="{y-hh:.0f}" width="{w*.6:.0f}" height="{hh:.0f}" fill="{c}"/>')
            y -= hh
            if kind in ('circ','tri','dome'): break
        x += w + unit*r.choice([.15,.35,.6,1])
    out.append('</svg>')
    return ''.join(out)

def arena_url(key, width=1400):
    # mateixa especificacio que fa servir are.na a la pagina de cada bloc: ja esta a la cache del CDN i carrega rapid
    spec = {"bucket": "arena_images", "key": key,
            "edits": {"resize": {"width": 1200, "height": 1200, "fit": "inside", "withoutEnlargement": True},
                      "webp": {"quality": 75}, "jpeg": {"quality": 75}, "rotate": None}}
    return "https://images.are.na/" + base64.b64encode(json.dumps(spec, separators=(",", ":")).encode()).decode()

def img_url(fn, width=1280):
    return "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(fn) + f"?width={width}"
def img_page(fn):
    return "https://commons.wikimedia.org/wiki/File:" + quote(fn.replace(" ", "_"))

def photo(a, cls="", width=1280, eager=False, caption=True):
    """Foto de Wikimedia en duotono verd; si no carrega, castell generatiu."""
    svg = art_svg(a["slug"])
    if a.get("own"):   # imatge pujada des del CMS (camp «imatge»)
        load = 'fetchpriority="high"' if eager else 'loading="lazy"'
        return (f'<figure class="ph {cls}"><div class="duo">{svg}<img src="{e(a["own"])}" alt="{e(a["head"])}" '
                f'{load} decoding="async" onerror="this.parentNode.classList.add(\'off\')"></div></figure>')
    gif = GIF.get(a["num"])
    if gif:
        bid, url, alt = gif
        cap = (f'<figcaption>GIF via <a href="https://www.are.na/block/{bid}" target="_blank" rel="noopener">Are.na ↗</a></figcaption>'
               if caption else "")
        load = 'fetchpriority="high"' if eager else 'loading="lazy"'
        return (f'<figure class="ph gif {cls}"><div class="duo">{svg}'
                f'<img src="{e(url)}" alt="{e(alt)}" {load} decoding="async" '
                f'onerror="this.parentNode.classList.add(\'off\')"></div>{cap}</figure>')
    ar = ARENA.get(a["num"], {}).get("h")
    if ar:
        bid, key, alt, pos = ar
        cap = (f'<figcaption>Imatge via <a href="https://www.are.na/block/{bid}" target="_blank" rel="noopener">Are.na ↗</a></figcaption>'
               if caption else "")
        load = 'fetchpriority="high"' if eager else 'loading="lazy"'
        return (f'<figure class="ph {cls}"><div class="duo">{svg}'
                f'<img src="{e(arena_url(key, max(width, 1200)))}" alt="{e(alt)}" {load} decoding="async" style="object-position:{pos}" '
                f'onerror="this.parentNode.classList.add(\'off\')"></div>{cap}</figure>')
    if not a["img"]:
        return f'<figure class="ph {cls}"><div class="duo off">{svg}</div></figure>'
    fn, autor, lic, alt, pos = a["img"]
    cap = (f'<figcaption>Foto: {e(autor)} · {e(lic)} · <a href="{e(img_page(fn))}" target="_blank" rel="noopener">Wikimedia Commons ↗</a></figcaption>'
           if caption else "")
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<figure class="ph {cls}"><div class="duo">{svg}'
            f'<img src="{e(img_url(fn, width))}" alt="{e(alt)}" {load} decoding="async" style="object-position:{pos}" '
            f'onerror="this.parentNode.classList.add(\'off\')"></div>{cap}</figure>')

def inline_fig(f):
    if f[0] == "arena" and f[1] == "local":   # imatge propia dins blog-web/img/
        _, _, path, cap, v, w = f
        v = " v" if v == "v" else ""
        return (f'<figure class="inl{v}"><img src="../{e(path)}" alt="{e(cap)}" loading="lazy" decoding="async">'
                f'<figcaption><b>{e(cap)}</b></figcaption></figure>')
    if f[0] == "arena":
        _, bid, key, cap, v, w = f
        v = " v" if v == "v" else ""
        small = f' style="max-width:{w}px;margin:0 auto"' if w < 900 and not v else ""
        return (f'<figure class="inl{v}"><img src="{e(arena_url(key, 1600))}" alt="{e(cap)}"{small} loading="lazy" decoding="async" '
                f'onerror="this.parentNode.remove()"><figcaption><b>{e(cap)}</b> '
                f'<a href="https://www.are.na/block/{bid}" target="_blank" rel="noopener">Via Are.na ↗</a></figcaption></figure>')
    fn, autor, lic, cap = f[:4]
    v = " v" if len(f) > 4 and f[4] == "v" else ""
    return (f'<figure class="inl{v}"><img src="{e(img_url(fn, 1400))}" alt="{e(cap)}" loading="lazy" decoding="async" '
            f'onerror="this.parentNode.remove()"><figcaption><b>{e(cap)}</b> Foto: {e(autor)} · {e(lic)} · '
            f'<a href="{e(img_page(fn))}" target="_blank" rel="noopener">Wikimedia Commons ↗</a></figcaption></figure>')

# ------------------------------------------------------------------ estil
CSS = r"""
:root{--ink:#1f3350;--mute:#6b7689;--paper:#fff;--g:#35754b;--b:#2d4b7e;--r:#c23b2e;--y:#e9c73f;
--box:#eef0f3;--btn:#191919;--m:clamp(16px,4vw,48px);--air:clamp(40px,6vw,80px)}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:24px}
body{margin:0;background:var(--paper);color:var(--ink);font:400 17px/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit;text-decoration:none}
a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid var(--r);outline-offset:3px}
.skip{position:absolute;left:-999px;top:8px;background:var(--btn);color:#fff;padding:10px 16px;border-radius:999px;z-index:20}
.skip:focus{left:var(--m)}
.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute);font-weight:500;margin:0}
.L1,.L5{color:var(--g)}.L2{color:var(--b)}.L3,.L6{color:var(--r)}.L4{color:var(--y)}
h1,h2,h3{text-wrap:balance}

/* capcalera */
.top{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:clamp(16px,3vw,40px);
padding:10px var(--m);border-bottom:1px solid var(--ink)}
.logo{font-size:24px;font-weight:500;letter-spacing:-.03em;line-height:1;white-space:nowrap}
.pg{display:inline-block;vertical-align:super;margin-left:.08em;line-height:1;white-space:nowrap;font-size:.42em;
font-weight:500;letter-spacing:.02em;color:var(--mute)}
.pgfloat{color:var(--mute)}
.menu{display:flex;gap:clamp(14px,2.4vw,32px);font-size:15px}
.menu a{transition:color .2s}
.menu a:hover,.menu a[aria-current]{color:var(--r)}
.cta{display:inline-flex;gap:.5em;align-items:center;background:var(--btn);color:#fff;border-radius:999px;
padding:8px 18px;font-size:13px;font-weight:600;transition:background .2s}
.cta:hover{background:var(--r)}
@media(max-width:620px){.top{grid-template-columns:1fr auto}.cta{display:none}.menu{font-size:14px}}
.mq{overflow:hidden;background:var(--g);color:#fff;white-space:nowrap;user-select:none}
.mq-track{display:inline-flex;align-items:center;padding:11px 0;animation:mq 48s linear infinite;will-change:transform}
.mq span{font-size:13px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;padding:0 22px}
.mq i{display:inline-block;width:8px;height:8px;flex:none;background:#fff!important}
.mq:hover .mq-track{animation-play-state:paused}
@keyframes mq{to{transform:translateX(-50%)}}
@media(prefers-reduced-motion:reduce){.mq-track{animation:none}}
.progress{position:fixed;left:0;top:0;height:3px;width:100%;background:var(--g);transform-origin:0 50%;transform:scaleX(0);z-index:30}

/* fotos: colors originals; castell verd si no carreguen */
.ph{margin:0}
.duo{position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--box)}
.duo .art{position:absolute;inset:0;width:100%;height:100%;display:none}
.duo.off .art{display:block}
.duo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;
transition:transform .6s ease}
.duo.off img{display:none}
.ph.gif .duo{background:var(--box)}
.ph.gif .duo img{object-fit:contain;padding:5%}
a:hover .duo img{transform:scale(1.04)}
.ph figcaption{font-size:12px;color:var(--mute);margin-top:8px;line-height:1.4}
.ph figcaption a{border-bottom:1px solid currentColor}
.ph figcaption a:hover{color:var(--r)}
.duo.off+figcaption{display:none}
@media(prefers-reduced-motion:reduce){.duo img{transition:none}}

/* portada */
.hero{padding:clamp(28px,4vw,56px) var(--m) 0;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 24px}
.blogtitle{margin:0;font-weight:700;font-size:clamp(26px,3vw,40px);line-height:1;letter-spacing:-.04em}
.display{font-weight:400;font-size:clamp(44px,10.5vw,168px);line-height:.8;letter-spacing:-.05em;margin:.2em 0 0;margin-left:-.04em}
.lede{font-size:clamp(20px,2.2vw,28px);line-height:1.25;margin:0;max-width:22em}
.meta-row{display:flex;flex-wrap:wrap;gap:8px 24px;margin-top:20px}
@media(max-width:900px){.hero{grid-template-columns:1fr}}

.feat{margin:clamp(28px,3.5vw,48px) var(--m) 0;display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:clamp(20px,3vw,48px);
align-items:start}
.feat>div{border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);padding:12px 0 clamp(20px,2.4vw,32px)}
.feat .k{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px}
.feat h2{margin:0;font-weight:700;font-size:clamp(30px,3.8vw,56px);line-height:.98;letter-spacing:-.045em;transition:color .2s}
.feat p{font-size:clamp(17px,1.5vw,20px);line-height:1.4;margin:.9em 0 0;max-width:28em}
.feat .go{display:inline-block;margin-top:1.4em;font-weight:700}
.feat:hover h2{color:var(--r)}
@media(max-width:900px){.feat{grid-template-columns:1fr}}

.tools{padding:0 var(--m);margin-top:var(--air)}
.sechead{border-top:2px solid var(--ink);padding-top:12px;display:flex;justify-content:space-between;gap:16px;
font-size:12px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:0}
.sechead span+span{color:var(--mute);font-weight:500}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0;align-items:center}
.chip{font-family:inherit;font-size:13px;font-weight:500;line-height:1;border:1px solid var(--ink);background:transparent;color:var(--ink);
border-radius:999px;padding:9px 14px;cursor:pointer;transition:background .2s,color .2s,border-color .2s}
.chip:hover{border-color:var(--r);color:var(--r)}
.chip[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.search{margin-left:auto;font-family:inherit;font-size:15px;line-height:1;color:var(--ink);border:0;border-bottom:1px solid var(--ink);
padding:9px 0;width:min(240px,100%);background:transparent;border-radius:0}
.search::placeholder{color:var(--mute)}
@media(max-width:760px){.search{margin-left:0;width:100%;order:-1;margin-bottom:6px}}

.grid{list-style:none;margin:clamp(24px,3vw,40px) 0 0;padding:0 var(--m);display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
gap:clamp(36px,4vw,56px) clamp(20px,2.4vw,36px)}
.card a{display:block}
.card .k{display:flex;justify-content:space-between;gap:12px;border-top:1px solid var(--ink);margin-top:14px;padding-top:10px}
.card h3{margin:.45em 0 0;font-weight:700;font-size:clamp(21px,1.9vw,27px);line-height:1.08;letter-spacing:-.03em;transition:color .2s}
.card p{margin:.6em 0 0;color:var(--mute);font-size:15px;line-height:1.4}
.card a:hover h3{color:var(--r)}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.grid{grid-template-columns:1fr}}
.empty{padding:40px var(--m);color:var(--mute)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.grid.top3{margin-top:clamp(36px,4vw,56px)}
.feat-label{margin:clamp(24px,3vw,40px) var(--m) 0}
.feat-label+.feat{margin-top:14px}
#list:not(.filtering) li[data-top]{display:none}

/* article */
.art-head{padding:var(--air) var(--m) 0}
.crumb{display:flex;gap:10px 18px;flex-wrap:wrap}
.crumb a:hover{color:var(--r)}
.h1{font-weight:700;font-size:clamp(36px,6vw,88px);line-height:.95;letter-spacing:-.045em;margin:.35em 0 .3em;max-width:15em}
.dek{font-size:clamp(20px,2.3vw,28px);line-height:1.3;max-width:30em;margin:0}
.byline{display:flex;flex-wrap:wrap;gap:10px clamp(24px,4vw,56px);border-top:2px solid var(--ink);margin-top:clamp(28px,3.5vw,48px);padding-top:12px}
.byline b{display:block;font-size:15px;font-weight:400;color:var(--ink);text-transform:none;letter-spacing:0;margin-top:4px}
.hero-ph{margin:clamp(28px,3.5vw,48px) var(--m) 0}
.hero-ph .duo{aspect-ratio:21/9;max-height:78vh}
@media(max-width:620px){.hero-ph .duo{aspect-ratio:4/3}}

.body{padding:clamp(36px,5vw,72px) var(--m) 0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,38rem) minmax(0,1fr);gap:clamp(24px,4vw,64px)}
.toc{grid-column:1;justify-self:end;width:min(100%,240px);position:sticky;top:32px;align-self:start}
.toc ol{list-style:none;margin:12px 0 0;padding:0;counter-reset:t}
.toc li{border-top:1px solid var(--ink)}
.toc li:last-child{border-bottom:1px solid var(--ink)}
.toc a{display:block;padding:10px 0;font-size:14px;line-height:1.3;color:var(--mute);transition:color .2s}
.toc a:hover,.toc a.on{color:var(--ink)}
.toc a.on{font-weight:700}
.toc .left{margin-top:18px;font-size:12px;color:var(--mute);letter-spacing:.08em;text-transform:uppercase}
.prose{grid-column:2;font-size:19px;line-height:1.62}
.prose p{margin:0 0 1.1em}
.prose .lead{font-size:clamp(21px,2vw,24px);line-height:1.45;letter-spacing:-.01em}
.prose .def{font-size:clamp(22px,2.2vw,28px);font-weight:700;line-height:1.25;letter-spacing:-.025em;
border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);padding:.8em 0;margin:1.6em 0}
.prose h2{font-size:clamp(26px,3vw,38px);font-weight:700;line-height:1.05;letter-spacing:-.035em;
border-top:2px solid var(--ink);padding-top:.6em;margin:2em 0 .8em}
.prose em{font-style:italic}
.prose a{border-bottom:1px solid currentColor}
.prose a:hover{color:var(--r)}
.prose blockquote{margin:1.4em 0;padding-left:1em;border-left:2px solid var(--ink)}
.prose ul,.prose ol{padding-left:1.2em;margin:0 0 1.1em}
.prose hr{border:0;border-top:1px solid var(--ink);margin:2em 0}
.prose .inl{margin:2.2em 0 2.4em}
.prose .inl img{display:block;width:100%;height:auto;background:var(--box)}
.prose .inl.v img{width:auto;max-width:100%;max-height:78vh;margin:0 auto}
.prose .inl figcaption{font-size:14px;line-height:1.45;color:var(--mute);margin-top:10px;border-top:1px solid var(--ink);padding-top:8px}
.prose .inl figcaption b{font-weight:400;color:var(--ink)}
.prose .inl figcaption a{border:0;white-space:nowrap}
@media(min-width:1100px){.prose .inl:not(.v){margin-left:-8%;margin-right:-8%}}
.endmark{display:inline-block;width:.55em;height:.55em;margin-left:.3em;background:var(--g);vertical-align:.05em}
@media(max-width:1100px){.body{grid-template-columns:1fr}.toc{display:none}.prose{grid-column:1;max-width:38rem;margin:0 auto;width:100%}}
@media(max-width:620px){.prose{font-size:18px}}

.aside{padding:var(--air) var(--m) 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:clamp(24px,4vw,64px)}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.tags a{border:1px solid var(--ink);border-radius:999px;padding:7px 12px;font-size:13px;font-weight:500;transition:color .2s,border-color .2s}
.tags a:hover{color:var(--r);border-color:var(--r)}
.fonts{list-style:none;margin:14px 0 0;padding:0;font-size:14px}
.fonts li{border-top:1px solid var(--ink);padding:9px 0}
.fonts li:last-child{border-bottom:1px solid var(--ink)}
.fonts a{display:flex;justify-content:space-between;gap:12px;color:var(--mute);transition:color .2s}
.fonts a span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fonts a:hover{color:var(--r)}
@media(max-width:760px){.aside{grid-template-columns:1fr}}

.more{padding:var(--air) var(--m) 0}
.more .grid{padding:0;margin-top:20px}
.pager{margin:var(--air) var(--m) 0;display:grid;grid-template-columns:1fr 1fr;border-top:2px solid var(--ink)}
.pager a{padding:18px 0 4px;display:block}
.pager a+a{text-align:right;border-left:1px solid var(--ink);padding-left:16px}
.pager a:first-child{padding-right:16px}
.pager b{display:block;font-size:clamp(18px,2vw,26px);line-height:1.1;letter-spacing:-.03em;margin-top:10px;transition:color .2s}
.pager a:hover b{color:var(--r)}

/* peu (igual que honestpg.com) */
.site-foot{margin-top:clamp(72px,10vw,140px);padding:64px var(--m) 28px;border-top:2px solid var(--ink)}
.fcols{display:grid;grid-template-columns:1.4fr 1fr 1fr .8fr;gap:32px;align-items:start}
.fcols>div{padding-bottom:40px}
.flogo{font-size:clamp(52px,5.2vw,86px);font-weight:500;letter-spacing:-.04em;line-height:1;display:inline-block}
.flogo .pg{font-size:.2em;vertical-align:top;margin-top:.5em}
.fabout p{margin:22px 0 0;color:#5b6474;line-height:1.6;max-width:22em}
.fh{font-size:12px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#5b6474;margin:0 0 14px}
.site-foot ul{list-style:none;margin:0;padding:0}
.site-foot ul li{margin-bottom:12px}
.fcontact ul li{margin-bottom:8px}
.site-foot a:hover{color:var(--g)}
.fsupport{margin-top:28px;display:flex;align-items:center;gap:16px}
.fsupport .fh{margin:0}
.fsupport img{display:block;width:96px;height:auto}
.site-foot .flink{display:inline-flex;align-items:baseline;gap:10px;margin-top:18px;color:var(--ink);padding:0 0 6px;border-bottom:1px solid var(--ink);font-size:17px;font-weight:500}
.site-foot .flink .arr{display:inline-block;animation:arrnudge 1.6s ease-in-out infinite}
.site-foot .flink:hover{color:var(--g);border-color:var(--g)}
@keyframes arrnudge{0%,100%{transform:translateX(0)}50%{transform:translateX(4px)}}
.flegal{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px 24px;border-top:1px solid #e3e5ea;padding-top:22px;font-size:14px;color:#5b6474}
.flegal nav{display:flex;flex-wrap:wrap;gap:22px}
.social{display:flex;gap:12px}
.social a{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border:1px solid var(--ink);border-radius:50%;color:var(--ink)}
.social a:hover{background:var(--ink);color:#fff}
.fcols{grid-template-columns:1.4fr 1fr .65fr 1.15fr}
/* castells (joc de construccio aleatori, com a honestpg.com) */
.castle{display:flex;align-self:center;padding:0 0 40px;overflow:hidden}
.cbox3{position:relative;width:100%;aspect-ratio:420/240}
.pc{position:absolute;display:block;opacity:0;transform:translateY(-260px)}
.castle.build .pc{animation:cdrop3 .7s cubic-bezier(.3,1.45,.5,1) forwards}
@keyframes cdrop3{0%{opacity:0;transform:translateY(-260px)}15%{opacity:1}100%{opacity:1;transform:translateY(0)}}
.pc.sh-tri{clip-path:polygon(50% 0,100% 100%,0 100%)}
.pc.sh-ball{border-radius:50%}
.pc.sh-semi{border-radius:999px 999px 0 0}
.pc.sh-pent{clip-path:polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%)}
.pc.sh-hex{clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)}
.pc.sh-cyl{border-radius:10% 10% 6% 6%/6% 6% 4% 4%}
.pc.sh-pawn{border-radius:48% 48% 6% 6%/16% 16% 3% 3%}
.pc.sh-arch{-webkit-mask:radial-gradient(circle at 50% 100%,transparent 34%,#000 35%);mask:radial-gradient(circle at 50% 100%,transparent 34%,#000 35%)}
@media(prefers-reduced-motion:reduce){.pc{opacity:1;transform:none}.castle.build .pc{animation:none}}
@media(max-width:1000px){.fcols{grid-template-columns:1fr 1fr}.castle{grid-column:1/-1;max-width:380px;margin:0 auto;width:100%}}
@media(max-width:860px){.site-foot .fcontact,.site-foot .fnav,.site-foot .castle{display:none}.fcols{grid-template-columns:1fr}
.flegal{display:grid;grid-template-columns:1fr auto;row-gap:16px;column-gap:12px}.flegal>span{grid-column:1;grid-row:1}.flegal .social{grid-column:2;grid-row:1;justify-self:end}.flegal nav{grid-column:1/-1;grid-row:2;gap:16px}}
@media(prefers-reduced-motion:reduce){.site-foot .flink .arr{animation:none}}
"""

JS = r"""
(function(){
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  /* PG -> PLAYGROUND: text flotant, no mou res */
  var FULL='PLAYGROUND';
  [].forEach.call(document.querySelectorAll('.pg'),function(node){
    var host=node.closest('.logo,.flogo')||node.parentElement, t=[], orig=node.textContent;
    var fl=document.createElement('span'); fl.className='pgfloat'; fl.setAttribute('aria-hidden','true');
    fl.style.cssText='position:absolute;pointer-events:none;z-index:9;white-space:nowrap;line-height:1';
    fl.textContent=orig; document.body.appendChild(fl); node.style.color='transparent';
    function place(){var r=node.getBoundingClientRect(),cs=getComputedStyle(node);
      fl.style.left=(r.left+scrollX)+'px'; fl.style.top=(r.top+scrollY)+'px';
      fl.style.font=cs.font; fl.style.letterSpacing=cs.letterSpacing;}
    place(); addEventListener('resize',place); addEventListener('load',place); addEventListener('honest:route',place); if(window.ResizeObserver) new ResizeObserver(place).observe(document.body);
    host.addEventListener('mouseenter',function(){t.forEach(clearTimeout);t=[];place();
      if(reduce){fl.textContent=FULL;return;} fl.textContent='';
      for(var i=0;i<FULL.length;i++)(function(i){t.push(setTimeout(function(){fl.textContent=FULL.slice(0,i+1)},i*50))})(i);});
    host.addEventListener('mouseleave',function(){t.forEach(clearTimeout);t=[];fl.textContent=orig;});
  });
  /* salt de lletres */
  if(!reduce){[].forEach.call(document.querySelectorAll('.jump'),function(el){
    var s=el.textContent; el.setAttribute('aria-label',s); el.textContent='';
    s.split('').forEach(function(c){var sp=document.createElement('span');sp.setAttribute('aria-hidden','true');sp.textContent=c===' '?' ':c;el.appendChild(sp);});
    el.addEventListener('mouseenter',function(){[].forEach.call(el.children,function(sp){sp.style.transform='translateY('+(Math.random()*6-3).toFixed(1)+'px)';});});
    el.addEventListener('mouseleave',function(){[].forEach.call(el.children,function(sp){sp.style.transform='';});});
  });}


  /* castells del peu: construccio aleatoria que cau en arribar-hi */
  (function(){
    var box=document.querySelector('.site-foot .cbox3'); if(!box) return;
    var W=420,H=240,C=['var(--g)','var(--b)','var(--r)','var(--y)'];
    function R(a,b){return a+Math.random()*(b-a)} function I(a,b){return Math.floor(R(a,b+1))} function P(a){return a[Math.floor(Math.random()*a.length)]}
    function col(not){var c;do{c=P(C)}while(c===not);return c}
    var pcs=[];function add(x,y,w,h,c,sh){pcs.push({x:x,y:y,w:w,h:h,c:c,sh:sh||''});return c}
    function roof(x,y,w,prev){var t=P(['tri','tri','cone','ball','semi','none']);var c=col(prev);
      if(t==='tri'){var rw=w+I(8,20),rh=Math.min(I(34,56),H-y);if(rh>18)add(x-(rw-w)/2,y,rw,rh,c,'sh-tri')}
      else if(t==='cone'){var cw=w*0.7,ch=Math.min(I(40,60),H-y);if(ch>18)add(x+(w-cw)/2,y,cw,ch,c,'sh-tri')}
      else if(t==='ball'){var d=Math.min(w*0.8,40);if(y+d<=H)add(x+(w-d)/2,y,d,d,c,'sh-ball')}
      else if(t==='semi'){add(x,y,w,w/2,c,'sh-semi')}}
    function tower(x){var w=I(40,58),y=0,n=I(2,4),prev=null;for(var i=0;i<n;i++){var h=P([w,w,w/2,w*1.3]);if(y+h>H-50)break;prev=add(x,y,w,h,col(prev),P(['','','','sh-cyl']));y+=h}roof(x,y,w,prev);return w}
    function arch(x){var cw=I(34,46),gap=I(50,80),lh=P([cw,cw*1.4]),legs=I(1,2),y=0,a=col(),b=col(a);
      for(var k=0;k<legs;k++){var cc=k%2?b:a;add(x,y,cw,lh,cc,'');add(x+cw+gap,y,cw,lh,cc,'');y+=lh}
      var bw=cw*2+gap+I(0,12),bx=x-(bw-(cw*2+gap))/2,bh=P([26,34,40]);var bc=col(b);add(bx,y,bw,bh,bc,P(['','','sh-arch']));y+=bh;
      if(Math.random()<.8){var tw=I(40,56);var tx=x+(cw*2+gap-tw)/2;if(Math.random()<.5){var cc2=add(tx,y,tw,tw,col(bc),'');roof(tx,y+tw,tw,cc2)}else roof(tx,y,tw,bc)}
      if(Math.random()<.5){var d=gap*0.7;add(x+cw+(gap-d)/2,0,d,d/2,col(bc),'sh-semi')}
      return cw*2+gap}
    function pawn(x){var w=I(26,36),h=I(70,110);add(x,0,w,h,col(),'sh-pawn');var d=w*1.25;add(x-(d-w)/2,h-4,d,d,col(),'sh-ball');return w+6}
    function cone(x){var w=I(50,74),bh=I(30,48),c=add(x,0,w,bh,col(),P(['sh-pent','sh-hex','']));var cw=w*R(.45,.7),ch=I(40,70);add(x+(w-cw)/2,bh,cw,ch,col(c),'sh-tri');return w}
    function stairs(x){var w=I(30,40),n=I(2,4),prev=null;for(var i=0;i<n;i++){for(var j=0;j<=i;j++)prev=add(x+i*w,j*w,w,w,col(prev),'')}if(Math.random()<.6)roof(x+(n-1)*w,n*w,w,prev);return n*w}
    function dome(x){var w=I(56,80),bh=I(30,50),c=add(x,0,w,bh,col(),'');add(x,bh,w,w/2,col(c),'sh-semi');return w}
    var G=[tower,tower,arch,pawn,cone,stairs,dome],x=0,used=[],guard=0;
    while(x<W-40&&guard++<200){var g=P(G);if(used.length&&g===used[used.length-1])continue;var start=pcs.length,w=g(x);
      var maxX=0;for(var i=start;i<pcs.length;i++)maxX=Math.max(maxX,pcs[i].x+pcs[i].w);
      if(maxX>W){pcs.length=start;if(used.length>=3)break;used.push(g);continue}
      used.push(g);x=maxX+I(10,22)}
    if(!pcs.length) return;
    var minX=Math.min.apply(null,pcs.map(function(p){return p.x})),maxX2=Math.max.apply(null,pcs.map(function(p){return p.x+p.w})),off=(W-(maxX2-minX))/2-minX;
    var html='';pcs.forEach(function(p,i){var y=Math.min(p.y,H-p.h);html+='<i class="pc '+p.sh+'" style="left:'+((p.x+off)/W*100).toFixed(2)+'%;bottom:'+(y/H*100).toFixed(2)+'%;width:'+(p.w/W*100).toFixed(2)+'%;height:'+(p.h/H*100).toFixed(2)+'%;background:'+p.c+';animation-delay:'+(i*0.12).toFixed(2)+'s"></i>'});
    box.innerHTML=html;
    var c=box.closest('.castle');
    function chk(){var r=c.getBoundingClientRect(),h=innerHeight;if(r.top<h-r.height*.35&&r.bottom>0)c.classList.add('build');else if(r.top>h)c.classList.remove('build');}
    addEventListener('scroll',chk,{passive:true});addEventListener('resize',chk);addEventListener('honest:route',function(){c.classList.remove('build');setTimeout(chk,60)});chk();addEventListener('load',chk);if(window.ResizeObserver)new ResizeObserver(chk).observe(document.body);
  })();

  /* barra de lectura + seccio activa + temps restant */
  var bar=document.querySelector('.progress');
  function article(){ return [].filter.call(document.querySelectorAll('article.view, article.post'),function(a){return !a.hidden})[0]; }
  function onScroll(){
    var a=article(); if(!bar) return;
    if(!a){bar.style.transform='scaleX(0)';return;}
    var p=a.querySelector('.prose'), r=p.getBoundingClientRect(), h=r.height-innerHeight*0.6;
    var f=Math.max(0,Math.min(1,(-r.top+innerHeight*0.25)/Math.max(1,h)));
    bar.style.transform='scaleX('+f.toFixed(3)+')';
    var links=a.querySelectorAll('.toc a[href^="#s-"]'), cur=null;
    [].forEach.call(links,function(l){var t=document.getElementById(l.getAttribute('href').slice(1)); if(t&&t.getBoundingClientRect().top<innerHeight*0.35) cur=l;});
    [].forEach.call(links,function(l){l.classList.toggle('on',l===cur)});
    var left=a.querySelector('.left'); if(left){var m=Math.max(0,Math.ceil(+left.dataset.min*(1-f))); left.textContent=m?('Queden '+m+' min'):'Llegit';}
  }
  addEventListener('scroll',onScroll,{passive:true}); addEventListener('resize',onScroll); addEventListener('honest:route',onScroll); onScroll();
  document.addEventListener('click',function(ev){var l=ev.target.closest('.toc a[href^="#s-"]'); if(!l) return; ev.preventDefault();
    var t=document.getElementById(l.getAttribute('href').slice(1)); if(t) t.scrollIntoView({behavior:reduce?'auto':'smooth'});});

  /* filtres de la portada */
  var list=document.getElementById('list'); if(!list) return;
  var items=[].slice.call(list.children), chips=[].slice.call(document.querySelectorAll('.chip')),
      q=document.getElementById('q'), count=document.getElementById('count'), empty=document.getElementById('empty'), tag='';
  function norm(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');}
  function apply(){var term=norm(q.value.trim()),n=0,f=!!(tag||term);list.classList.toggle('filtering',f);
    items.forEach(function(li){var ok=(!tag||(' '+li.dataset.tags+' ').indexOf(' '+tag+' ')>-1)&&(!term||norm(li.textContent).indexOf(term)>-1);
      li.hidden=!ok; if(ok&&(f||!li.hasAttribute('data-top')))n++;});
    count.textContent=n+(n===1?' article':' articles'); empty.hidden=n>0;}
  chips.forEach(function(c){c.addEventListener('click',function(){tag=c.dataset.tag;
    chips.forEach(function(o){o.setAttribute('aria-pressed',o===c?'true':'false')}); apply();});});
  q.addEventListener('input',apply);
  window.honestFilter=function(t){var c=chips.filter(function(x){return x.dataset.tag===t})[0];
    if(c){c.click();} else {chips[0].click(); q.value=t.replace(/-/g,' '); apply();}
    document.getElementById('filtres').scrollIntoView();};
  var h=decodeURIComponent(location.hash.slice(1)); if(h.indexOf('tema-')===0) setTimeout(function(){honestFilter(h.slice(5))},0);
})();
"""

ROUTER = r"""
(function(){
  var views=[].slice.call(document.querySelectorAll('.view'));
  function show(){
    var h=location.hash.slice(1), el=null, filt=null;
    if(h.indexOf('tema-')===0){filt=h.slice(5);} else if(h && h!=='top'){el=document.getElementById('v-'+h); if(!el) return;}
    if(!el) el=document.getElementById('v-index');
    views.forEach(function(v){v.hidden=v!==el});
    var a=el.querySelector('.h1'); document.title=a?a.textContent+' · Honest':'Blog de disseny social · Honest';
    document.querySelector('.menu a').toggleAttribute('aria-current', el.id==='v-index');
    if(filt&&window.honestFilter) honestFilter(filt); else window.scrollTo(0,0);
    dispatchEvent(new Event('honest:route'));
  }
  addEventListener('hashchange',show); show();
})();
"""

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
           "%3Crect width='16' height='16' fill='%2335754b'/%3E%3C/svg%3E")
LOGO = ('<span class="L1">H</span><span class="L2">o</span><span class="L3">n</span><span class="L4">e</span>'
        '<span class="L5">s</span><span class="L6">t</span><sup class="pg" aria-label="Playground">PG</sup>')

CLAIMS = [
    "Blog de disseny social d'Honest",
    "Assaigs sobre com dissenyar amb la gent i per a la gent",
    "Criteris, casos i preguntes incòmodes",
    "Des de Mallorca, per al tercer sector",
    "El disseny també decideix qui hi cap",
]
_SQ = ["var(--g)", "var(--b)", "var(--r)", "var(--y)"]
def _mq_run():
    return "".join(f'<span>{e(c)}</span><i style="background:{_SQ[i % 4]}"></i>' for i, c in enumerate(CLAIMS))
MARQUEE = ('<div class="mq" aria-label="' + e(" · ".join(CLAIMS)) + '"><div class="mq-track" aria-hidden="true">'
           + _mq_run() + _mq_run() + '</div></div>')

# ------------------------------------------------------------------ enllacos segons el mode
class Links:
    def __init__(self, single, depth=0):
        self.single, self.depth = single, depth
    def home(self):  return "#top" if self.single else ("../" * self.depth) + "index.html"
    def art(self, s): return "#" + s if self.single else ("" if self.depth else "articles/") + s + ".html"
    def tag(self, t): return "#tema-" + t if self.single else ("../" * self.depth) + "index.html#tema-" + t

# ------------------------------------------------------------------ peces
def card(a, L, tag="li", top=False):
    return (f'<{tag} class="card"{" data-top" if top else ""} data-tags="{e(" ".join(a["tags"]))}"><a href="{L.art(a["slug"])}">'
            f'{photo(a, width=800, caption=False)}'
            f'<div class="k eyebrow"><span>{a["num"]:02d} · {e(a["concept"])}</span><span>{a["mins"]} min</span></div>'
            f'<h3>{e(a["head"])}</h3><p>{e(a["form"])}</p></a></{tag}>')

def index_body(arts, L):
    counts = {}
    for a in arts:
        for t in a["tags"]: counts[t] = counts.get(t, 0) + 1
    top = [t for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if c >= 2][:12]
    chips = '<button class="chip" type="button" data-tag="" aria-pressed="true">Tots</button>' + "".join(
        f'<button class="chip" type="button" data-tag="{e(t)}" aria-pressed="false">{e(tagname(t))}</button>' for t in top)
    f = arts[0]
    total = sum(a["mins"] for a in arts)
    return f"""
<h1 class="sr-only">Blog de disseny social</h1>
<p class="eyebrow feat-label">Articles destacats</p>
<a class="feat" href="{L.art(f['slug'])}">
  {photo(f, width=1280, eager=True, caption=False)}
  <div><div class="k eyebrow"><span>{f['num']:02d} · {e(f['concept'])}</span><span>{f['mins']} min</span></div>
  <h2>{e(f['head'])}</h2><p>{e(f['sub'] or f['form'])}</p></div>
</a>
<ul class="grid top3">{''.join(card(a, L) for a in arts[1:4])}</ul>
<section class="tools" id="filtres" aria-label="Filtres">
  <h2 class="sechead"><span>Més articles</span><span id="count">{max(0, len(arts) - 4)} articles</span></h2>
  <div class="filters">{chips}<input class="search" id="q" type="search" placeholder="Cerca…" aria-label="Cerca articles"></div>
</section>
<ul class="grid" id="list">{''.join(card(a, L, top=(i < 4)) for i, a in enumerate(arts))}</ul>
<p class="empty" id="empty" hidden>Cap article no coincideix amb la cerca.</p>
"""

def related(a, arts, n=3):
    sc = []
    for b in arts:
        if b is a: continue
        s = len(set(a["tags"]) & set(b["tags"]))
        sc.append((-s, abs(b["num"] - a["num"]), b))
    return [b for _, _, b in sorted(sc, key=lambda x: (x[0], x[1]))[:n]]

def article_body(a, arts, L):
    i = arts.index(a)
    prev = arts[i-1] if i > 0 else None
    nxt = arts[i+1] if i < len(arts)-1 else None
    tags = "".join(f'<a href="{L.tag(t)}">{e(tagname(t))}</a>' for t in a["tags"])
    fonts = ""
    if a["fonts"]:
        it = "".join(f'<li><a href="{e(u)}" rel="noopener" target="_blank"><span>{e(dom(u))}</span><span aria-hidden="true">↗</span></a></li>' for u in a["fonts"])
        fonts = f'<div><h2 class="sechead"><span>Fonts</span></h2><ul class="fonts">{it}</ul></div>'
    toc = "".join(f'<li><a href="#{i_}">{e(t)}</a></li>' for i_, t in a["toc"])
    p = f'<a href="{L.art(prev["slug"])}"><span class="eyebrow">← Anterior · {prev["num"]:02d}</span><b>{e(prev["head"])}</b></a>' if prev else "<span></span>"
    n = f'<a href="{L.art(nxt["slug"])}"><span class="eyebrow">Següent · {nxt["num"]:02d} →</span><b>{e(nxt["head"])}</b></a>' if nxt else "<span></span>"
    prose = a["html"]
    figs = INLINE.get(a["num"], [])
    if a["num"] in ARENA:
        figs = [("arena",) + ARENA[a["num"]][k] for k in ("a", "b") if ARENA[a["num"]].get(k)]
    h2s = [m.start() for m in re.finditer(r"<h2 ", prose)]
    for fig, pos in sorted(zip(figs, h2s[1:3]), key=lambda x: -x[1]):
        prose = prose[:pos] + inline_fig(fig) + prose[pos:]
    prose = re.sub(r"</p>\s*$", '<span class="endmark" aria-hidden="true"></span></p>', prose.strip())
    return f"""
  <header class="art-head">
    <div class="crumb eyebrow"><a href="{L.home()}">← Blog</a><span>{a['num']:02d} · {e(a['concept'])}</span></div>
    <h1 class="h1">{e(a['head'])}</h1>
    <p class="dek">{e(a['sub'] or a['form'])}</p>
    <div class="byline eyebrow">
      <div>Text<b>Manuel Bauzà Ramis</b></div><div>Data<b>{e(fdate(a['date']))}</b></div>
      <div>Lectura<b>{a['mins']} min</b></div><div>Tema<b>{e(a['concept'])}: {e(a['form'].lower())}</b></div>
    </div>
  </header>
  {photo(a, cls="hero-ph", width=1600, eager=True)}
  <div class="body">
    <nav class="toc" aria-label="En aquest article"><h2 class="sechead"><span>En aquest article</span></h2><ol>{toc}</ol>
      <p class="left" data-min="{a['mins']}">{a['mins']} min</p></nav>
    <div class="prose">{prose}</div>
  </div>
  <aside class="aside">
    <div><h2 class="sechead"><span>Temes</span></h2><div class="tags">{tags}</div></div>
    {fonts}
  </aside>
  <section class="more"><h2 class="sechead"><span>Continua llegint</span></h2>
    <ul class="grid">{''.join(card(b, L) for b in related(a, arts))}</ul></section>
  <nav class="pager" aria-label="Articles">{p}{n}</nav>
"""

def shell(title, desc, main, L, canonical="", extra_js=""):
    home = L.home()
    return f"""<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{f'<link rel="canonical" href="{e(canonical)}">' if canonical else ''}
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">Salta al contingut</a>
<div class="progress" aria-hidden="true"></div>
<header class="top" id="top">
  <a class="logo" href="{home}" aria-label="Honest — blog">{LOGO}</a>
  <nav class="menu" aria-label="Principal"><a href="{home}">Blog de disseny social</a><a href="https://www.honestpg.com/">honestpg.com ↗</a></nav>
  <a class="cta" href="https://www.honestpg.com/contacte/"><span>Col·laboram?</span><span aria-hidden="true">→</span></a>
</header>
{MARQUEE}
<main id="main">
{main}
</main>
<footer class="site-foot">
<div class="fcols">
 <div class="fabout"><a class="flogo" href="https://www.honestpg.com/">{LOGO}</a><p>A Honest som un estudi creatiu sense ànim de lucre, creiem que les coses es poden fer diferent.</p><div class="fsupport"><p class="fh">Amb el suport de</p><img decoding="async" loading="lazy" src="https://www.honestpg.com/img/logos/colonya.png" alt="Fundació Guillem Cifre de Colonya · Colonya Caixa Pollença"></div></div>
 <div class="fcontact"><p class="fh">Treballem junts</p><ul><li><a href="mailto:hola@honest.cat">hola@honest.cat</a></li><li>C. Corall 12 A<br>07600 Platja de Palma</li></ul><a class="flink" href="https://www.honestpg.com/contacte/"><span>Col·laboram?</span><span class="arr" aria-hidden="true">→</span></a></div>
 <div class="fnav"><p class="fh">Navegació</p><ul><li><a href="https://www.honestpg.com/qui-som/">Qui som</a></li><li><a href="https://www.honestpg.com/que-fem/">Què feim</a></li><li><a href="https://www.honestpg.com/projectes/">Projectes</a></li><li><a href="https://www.honestpg.com/honest-lap/">Honest.Lap</a></li><li><a href="{home}">Blog de disseny social</a></li></ul></div>
 <div class="castle" aria-hidden="true"><div class="cbox3"></div></div>
</div>
<div class="flegal"><span>© {datetime.date.today().year} Associació Honest · CIF G22446975<br>Núm. de registre 311000012112</span><nav aria-label="Legal"><a href="https://www.honestpg.com/transparencia/">Transparència</a><a href="https://www.honestpg.com/avis-legal/">Avís legal</a><a href="https://www.honestpg.com/cookies/">Política de galetes</a><a href="https://www.honestpg.com/privacitat/">Privacitat</a></nav><div class="social"><a href="https://www.instagram.com/honest_playground/" target="_blank" aria-label="Instagram d’Honest" rel="noopener"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg></a><a href="https://www.linkedin.com/company/associaci%C3%B3-honest/" target="_blank" aria-label="LinkedIn d’Honest" rel="noopener"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.5h4V21H3zM9.5 9.5h3.8v1.6h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.1c0-1.22-.02-2.78-1.7-2.78-1.7 0-1.96 1.33-1.96 2.7V21h-4z"/></svg></a><a href="https://www.youtube.com/@HonestAssociaci%C3%B3" target="_blank" aria-label="YouTube d’Honest" rel="noopener"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8zM9.7 15.1V8.9l5.8 3.1z"/></svg></a></div></div>
</footer>
<script>{JS}</script>{extra_js}
</body>
</html>"""

# ------------------------------------------------------------------ sortida
def build_static(arts):
    os.makedirs(os.path.join(OUT, "articles"), exist_ok=True)
    import shutil
    for d in ("img", "admin"):   # imatges propies i panell de Decap CMS
        if os.path.isdir(os.path.join(HERE, d)):
            shutil.copytree(os.path.join(HERE, d), os.path.join(OUT, d), dirs_exist_ok=True)
    L0 = Links(False, 0)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(
        shell("Blog de disseny social · Honest", "Assaigs de Manuel Bauzà Ramis sobre disseny social.",
              index_body(arts, L0), L0, SITE + "/"))
    L1 = Links(False, 1)
    for a in arts:
        main = f'<article class="post">{article_body(a, arts, L1)}</article>'
        open(os.path.join(OUT, "articles", a["slug"] + ".html"), "w", encoding="utf-8").write(
            shell(a["head"] + " · Honest", a["sub"] or a["form"], main, L1, f"{SITE}/articles/{a['slug']}.html"))
    urls = [SITE + "/"] + [f"{SITE}/articles/{a['slug']}.html" for a in arts]
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    main404 = (f'<section class="hero"><div><p class="eyebrow">Error 404</p><h1 class="display">No hi<br>és</h1></div>'
               f'<div><p class="lede">Aquesta pàgina no existeix o ha canviat de lloc.</p>'
               f'<p style="margin-top:24px"><a class="cta" href="/index.html">Torna al blog →</a></p></div></section>')
    open(os.path.join(OUT, "404.html"), "w", encoding="utf-8").write(
        shell("Pàgina no trobada · Honest", "Pàgina no trobada", main404, L0))
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    print(f"{len(arts)} articles -> {OUT}")

def build_single(arts, path):
    L = Links(True)
    main = f'<section class="view" id="v-index">{index_body(arts, L)}</section>' + "".join(
        f'<article class="view" id="v-{a["slug"]}" hidden>{article_body(a, arts, L)}</article>' for a in arts)
    page = shell("Blog de disseny social · Honest", "Blog de disseny social d'Honest", main, L, extra_js=f"<script>{ROUTER}</script>")
    open(path, "w", encoding="utf-8").write(page)
    print(f"pagina unica -> {path} ({len(page)//1024} KB)")

if __name__ == "__main__":
    arts = load()
    if len(sys.argv) > 2 and sys.argv[1] == "--single":
        build_single(arts, sys.argv[2])
    else:
        build_static(arts)
