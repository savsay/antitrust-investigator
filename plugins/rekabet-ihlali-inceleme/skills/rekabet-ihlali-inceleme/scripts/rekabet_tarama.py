"""Rekabet riski on-tarama (triage). Salt okunur; kaynak dosyalari degistirmez.
Cikti bir okuma kuyrugudur, bulgu degildir."""
import argparse, csv, email, hashlib, json, os, re, unicodedata
from email import policy
from functools import lru_cache

@lru_cache(maxsize=None)
def _f(c):
    if c in "İIı": return "i"
    d = unicodedata.normalize("NFD", c)[0].lower()
    return d if len(d) == 1 else c
def fold(s):  # Turkce/Kiril katlama; uzunluk korunur -> ofsetler orijinal metinle ayni
    return "".join(_f(c) for c in s)

K = {  # kavram -> kok/ifade (regex). TR / EN / RU
 "TARAF": [r"rakip", r"rakib", r"competitor", r"diger (firma|sirket|isveren)", r"other (employer|firm|company)",
           r"karsi taraf", r"other party", r"\b[a-z] sirketi", r"company [a-z]\b", r"konsorsiyum", r"consortium",
           r"ortak proje", r"joint project", r"совместн\w* проект", r"tedarikci", r"supplier", r"поставщик",
           r"dernek", r"\buye", r"katilimci", r"association", r"members", r"ассоциац", r"участник",
           r"hedef sirket", r"satin alinacak sirket", r"target company", r"конкурент",
           r"друг(ой|им|ого) (компан|работодател|фирм)", r"партнер"],
 "MUTABAKAT": [r"anlas", r"mutabik", r"kabul ett", r"uzlas", r"onayla", r"teyit", r"agreed", r"\bagree", r"arrangement",
           r"accepted", r"confirm", r"birlikte", r"together", r"ikimiz de", r"both of us", r"we both", r"karsilikli",
           r"centilmen", r"gentlemen", r"iki taraf", r"her iki", r"ikisi de", r"both parties", r"обе стороны",
           r"договорил", r"договор[её]нн", r"соглас", r"вместе", r"подтверд", r"оба\b"],
 "FIYAT": [r"fiyat", r"\bzam(m\w*|lar\w*|li\w*)?\b", r"iskonto", r"indirim", r"marj", r"price", r"pricing", r"discount",
           r"margin", r"increase", r"цен", r"повыш", r"скидк", r"марж"],
 "IHALE": [r"ihale", r"teklif", r"tender", r"\bbid", r"kazansin", r"let \w+ win", r"cekil", r"withdraw", r"тендер",
           r"заявк", r"предложени", r"выигра"],
 "PAZAR": [r"bolge", r"musteri", r"territor", r"customer", r"region", r"north", r"south", r"kuzey", r"guney",
           r"регион", r"клиент", r"территор", r"север", r"юг"],
 "ARZ": [r"uretim", r"kapasite", r"production", r"output", r"capacity", r"\barz\b", r"производ", r"мощност"],
 "ISGUCU": [r"calisan", r"ucret", r"maas", r"muhendis", r"personel", r"ise al", r"almayacak", r"employee", r"\bhire",
           r"hiring", r"wage", r"\bpay\b", r"salar", r"staff", r"poach", r"сотрудник", r"зарплат", r"наним", r"найм",
           r"работник", r"инженер", r"transfer", r"переход"],
 "DIKEY": [r"bayi", r"asgari (satis )?fiyat", r"altinda sat", r"sevkiyat", r"dealer", r"resale", r"distribut",
           r"дилер", r"минимальн", r"поставк", r"перепрод", r"munhasir", r"exclusiv", r"эксклюзив",
           r"rekabet etmeme", r"non-?compet", r"en cok kayrilan", r"\bmfn\b", r"parity", r"паритет"],
 "HAKIM": [r"maliyet\w* altinda", r"below (our |its )?cost", r"ниже\s+\w*\s*(затрат|себестоим)", r"disla", r"exclu(de|sion)",
           r"zorlan", r"struggle", r"трудно", r"вытесн", r"bundl", r"tying", r"baglantili satis", r"sadakat indirim",
           r"loyalty rebate", r"tedarik(i)? (kes|redd)", r"refus\w* to supply"],
 "GIZLI_BILGI": [r"gizli", r"confidential", r"teklif tablo", r"bid table", r"maliyet tablo", r"cost table",
           r"gelecek (ay|hafta|ceyrek|donem|yil)", r"next (week|month|quarter|year)", r"future", r"yayimlanmamis",
           r"конфиденц", r"следующ", r"будущ"],
 "GIZLEME": [r"aramizda kalsin", r"telefonla konus", r"mail atma", r"maile? yazma", r"e-?postaya yazma", r"yazmayalim",
           r"yaziya dokme", r"yazili olmasin", r"\bsil\b", r"\bsilin", r"delete", r"whatsapp", r"signal\b",
           r"kisisel (mail|e-?posta)", r"between us", r"off the record", r"in writing", r"удал", r"между нами"],
 # Ortulu dil: konuyu adlandirmadan ortak bilgiye yaslanan ifadeler. Tek basina sinyal degildir;
 # karsi tarafla ya da gizleme diliyle birlikte gecerse temanin saklandigi ihtimaliyle kuyruga alinir.
 "ORTULU": [r"her zamanki gibi", r"malum (konu|mesele|is)", r"bildigin (konu|mesele|is)", r"o (konu|mesele)\b",
           r"konustugumuz (gibi|konu|sekilde)", r"bahsettigimiz (gibi|konu)", r"eski usul", r"bizim usul",
           r"yuz yuze (konus|anlat|gorus)", r"detaylari (yuz yuze|gorusunce|bulusunca)", r"sira (sizde|sende|bizde|onlarda)",
           r"bu (sefer|tur|ay|kez) (siz|sen|biz|onlar)\b", r"\d+([.,]\d+)? (olsun|uzerinde kal|altina inme|den asagi inme|ten asagi inme)",
           r"as usual", r"the usual (way|arrangement|deal|understanding)", r"as we discussed", r"what we discussed",
           r"you know what i mean", r"the thing we (talked|spoke) about", r"(your|our|their) turn", r"in person",
           r"face to face", r"как обычно", r"по-старому", r"тот самый (вопрос|тем)", r"известн\w* (вопрос|тем)",
           r"при встрече", r"(ваша|наша|их) очередь"],
 "BAGLAM_AZALTICI": [r"reddett", r"reddedil", r"refused", r"rejected", r"egitim ornegi", r"training example",
           r"hukuk ekib", r"legal team", r"hukuk degerlendirme", r"legal review", r"bagimsiz", r"independent",
           r"kamuya acik", r"public", r"ekonomik butunluk", r"economic unit", r"отклон", r"отказ", r"учебн",
           r"юрид", r"юрист", r"независим", r"публичн", r"опубликов", r"kullanilmadi", r"not used",
           r"не использов", r"grup sirket", r"group compan", r"компаний группы", r"confirmed by legal"],
 "ERISIM": [r"avukat", r"counsel", r"attorney", r"hukuk musavir", r"privilege", r"kisisel e-?posta", r"personal email",
           r"gmail", r"hotmail", r"hukuki yetki", r"legal authori", r"адвокат", r"личн"],
}
TEMA = ["FIYAT", "IHALE", "PAZAR", "ARZ", "ISGUCU", "DIKEY", "HAKIM"]
RX = {k: re.compile("|".join(fold(x) for x in v)) for k, v in K.items()}  # kaliplar da katlanir

def kavramlar(t):
    f = fold(t); return {k for k, r in RX.items() if r.search(f)}

def seviye(c, ozel=False):
    tema = c & set(TEMA)
    if "ERISIM" in c: return "ERISIM"          # icerigi analiz etme; hukuka yonlendir
    if ozel: return "A"                        # kullanicinin verdigi terim gecti
    if tema and (("TARAF" in c and ({"MUTABAKAT", "GIZLI_BILGI", "ORTULU"} & c)) or "GIZLEME" in c): return "A"
    if tema and ({"TARAF", "MUTABAKAT", "GIZLI_BILGI"} & c or ("DIKEY" in c and "FIYAT" in c)): return "B"
    if "ORTULU" in c and ({"TARAF", "GIZLEME"} & c): return "B"   # tema adlandirilmamis olabilir; okunmali
    if tema: return "C"
    return None

CUMLE = re.compile(r"[^.!?\n]+[.!?]*")
def tara(metin, ozel_rx=None, pencere=3):
    cs = [(m.start(), m.end()) for m in CUMLE.finditer(metin) if m.group().strip()]
    out, i = [], 0
    while i < len(cs):
        s, e = cs[i][0], cs[min(i + pencere, len(cs)) - 1][1]
        parca = metin[s:e]; c = kavramlar(parca)
        sv = seviye(c, bool(ozel_rx and ozel_rx.search(fold(parca))))
        if sv: out.append({"seviye": sv, "start_char": s, "end_char": e, "kavramlar": ";".join(sorted(c)),
                           "baglam_azaltici": "BAGLAM_AZALTICI" in c, "metin": parca.strip()[:600]})
        i += max(1, pencere - 1)  # bir cumle ortusen pencereler
    return out

def _eml(b):
    m = email.message_from_bytes(b, policy=policy.default)
    bas = f"From: {m['from']}\nTo: {m['to']}\nCc: {m['cc']}\nDate: {m['date']}\nSubject: {m['subject']}\n\n"
    g = m.get_body(preferencelist=("plain", "html")); txt = g.get_content() if g else ""
    ekler = [p.get_filename() for p in m.iter_attachments() if p.get_filename()]
    return bas + re.sub(r"<[^>]+>", " ", txt) + (f"\n[EKLER: {', '.join(ekler)}]" if ekler else "")
def _msg(p):
    import extract_msg; m = extract_msg.Message(p)
    return f"From: {m.sender}\nTo: {m.to}\nDate: {m.date}\nSubject: {m.subject}\n\n{m.body or ''}"
def _docx(p):
    import docx; d = docx.Document(p)
    return "\n".join([x.text for x in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])
def _xlsx(p):
    import openpyxl; wb = openpyxl.load_workbook(p, data_only=False); out = []
    for ws in wb.worksheets:  # gizli sayfalar, formuller ve yorumlar dahil
        out.append(f"## Sayfa: {ws.title} ({ws.sheet_state})")
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None: out.append(f"{c.coordinate}: {c.value}")
                if c.comment: out.append(f"{c.coordinate} [YORUM]: {c.comment.text}")
    return "\n".join(out)
def _pptx(p):
    import pptx; pr = pptx.Presentation(p)
    return "\n".join(sh.text_frame.text for s in pr.slides for sh in s.shapes if sh.has_text_frame)
def _pdf(p):
    try:
        import pypdf; return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(p).pages)
    except ImportError:
        import subprocess; return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout
def cikar(p):
    e = os.path.splitext(p)[1].lower()
    if e in (".txt", ".csv", ".md", ".json", ".log"): return open(p, encoding="utf-8", errors="replace").read(), "metin"
    if e in (".html", ".htm"): return re.sub(r"<[^>]+>", " ", open(p, encoding="utf-8", errors="replace").read()), "html"
    if e == ".eml": return _eml(open(p, "rb").read()), "eml"
    if e == ".msg": return _msg(p), "extract_msg"
    if e == ".docx": return _docx(p), "python-docx"
    if e in (".xlsx", ".xlsm"): return _xlsx(p), "openpyxl"
    if e == ".pptx": return _pptx(p), "python-pptx"
    if e == ".pdf": return _pdf(p), "pypdf/pdftotext"
    raise ValueError("desteklenmeyen tur (pst/zip once ayri klasore acilmali)")

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kok"); ap.add_argument("--terimler", default="")
    ap.add_argument("--cikti", default="isabetler.csv"); ap.add_argument("--envanter", default="envanter.csv")
    a = ap.parse_args()
    ozel = [fold(t.strip()) for t in a.terimler.split(",") if t.strip()]
    ozel_rx = re.compile("|".join(re.escape(t) for t in ozel)) if ozel else None
    isabet, envanter_satirlari = [], []
    for kok, _, dosyalar in os.walk(a.kok):
        for ad in sorted(dosyalar):
            p = os.path.join(kok, ad); k = {"document_id": os.path.relpath(p, a.kok), "boyut": os.path.getsize(p)}
            try:
                k["sha256"] = sha256(p); metin, yontem = cikar(p)
                k.update(yontem=yontem, karakter=len(metin), durum="islendi" if metin.strip() else "BOS/OCR GEREKLI")
                for h in tara(metin, ozel_rx):
                    isabet.append({"document_id": k["document_id"], "sha256": k["sha256"], **h})
            except Exception as ex:
                k.update(durum=f"ISLENEMEDI: {type(ex).__name__}: {ex}"[:200])
            envanter_satirlari.append(k)
    sira = {"ERISIM": 0, "A": 1, "B": 2, "C": 3}
    isabet.sort(key=lambda h: (sira[h["seviye"]], h["document_id"], h["start_char"]))
    for yol, satirlar in ((a.cikti, isabet), (a.envanter, envanter_satirlari)):
        alanlar = sorted({x for s in satirlar for x in s}) or ["bos"]
        with open(yol, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=alanlar); w.writeheader(); w.writerows(satirlar)
    print(json.dumps({"dosya": len(envanter_satirlari), "islenemeyen": sum(not str(e.get("durum", "")).startswith("islendi") for e in envanter_satirlari),
                      "isabet": {s: sum(h["seviye"] == s for h in isabet) for s in sira}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
