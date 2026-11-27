# okuyucular.py

Bu dosya Claude dizini sürümünde betiğin okunabilir kopyasıdır. Aşağıdaki kodu değiştirmeden çalışma klasörüne `okuyucular.py` olarak yazın ve SKILL.md'deki komutla çalıştırın. Kaynak: https://github.com/savsay/antitrust-investigator/blob/main/plugins/rekabet-ihlali-inceleme/skills/rekabet-ihlali-inceleme/scripts/okuyucular.py

```python
"""Belge okuyuculari: dosyayi metne cevirir, kapsayicilari (e-posta ekleri, PST/OST, arsivler) alt belgelere acar.

Salt okunur: kaynak dosyalara yazmaz; gecici dosyalari kendi gecici klasorunde acar ve siler.
Dis araclar istege baglidir; yoksa belge "okunamadi" olarak, nedeniyle birlikte isaretlenir:
  readpst (pst-utils)      -> .pst / .ost
  tesseract (+ tur, rus)   -> gorseller ve metin katmani olmayan PDF sayfalari (OCR)
  pdftoppm / pdftotext     -> PDF sayfa goruntusu / metin katmani (pypdf yoksa)
  unrar veya 7z            -> .rar / .7z
  catdoc, xls2csv, catppt  -> eski Office (.doc / .xls / .ppt)
Python paketleri (istege bagli): python-docx, openpyxl, python-pptx, pypdf, extract-msg, tnefparse.
"""
import email, os, re, shutil, subprocess, tarfile, tempfile, unicodedata, zipfile
from email import policy
from xml.etree import ElementTree

import rekabet_tarama as RT

GORSEL = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
ARSIV = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}
OCR_ETIKET = "[OCR METNİ — alıntıyı özgün görselle karşılaştır]\n"
EN_FAZLA_DERINLIK = 6
EN_FAZLA_ALT_BELGE = 50000


def arac(ad):
    return shutil.which(ad)


def belge(etiket, metin="", yontem="", durum="islendi", neden="", ocr=False, basliklar=None, cocuklar=None):
    return {"etiket": etiket, "metin": metin, "yontem": yontem, "durum": durum, "neden": neden, "ocr": ocr,
            "basliklar": basliklar or {}, "cocuklar": cocuklar or []}


# ---------------------------------------------------------------- OCR
def ocr_dilleri():
    t = arac("tesseract")
    if not t:
        return []
    r = subprocess.run([t, "--list-langs"], capture_output=True, text=True)
    return [x.strip() for x in r.stdout.splitlines()[1:] if x.strip()]


_SESLI = set("aeıioöuüâîûyаеёиоуыэюяäéè")
_LATIN = re.compile(r"[a-zçğıöşüâîûäéè]", re.I)
_KIRIL = re.compile(r"[а-яё]", re.I)


def anlamsiz_oran(metin):
    """OCR ciktisinda sozcuk olamayacak belirteclerin orani (0-1).

    Yanlis dil modeliyle okunan metin (ornegin Kiril sayfa Latin modeliyle) sesli harfsiz, karisik alfabeli,
    rakam-harf karisimi ya da uzun sessiz harf dizili belirtecler uretir. Kisa belirtecler sayilmaz."""
    belirtecler = [b for b in re.findall(r"\S+", metin) if len(re.sub(r"\W", "", b)) >= 3]
    if not belirtecler:
        return 1.0
    kotu = 0
    for b in belirtecler:
        s = re.sub(r"[^\w]", "", b).lower()
        harf = re.sub(r"[\d_]", "", s)
        if not harf:
            continue
        karisik = bool(_LATIN.search(harf)) and bool(_KIRIL.search(harf))
        sessiz = not any(c in _SESLI for c in harf)
        uzun_sessiz = re.search(r"[^aeıioöuüâîûyаеёиоуыэюяäéè\d]{5,}", harf) is not None
        rakam_harf = bool(re.search(r"\d", s)) and bool(re.search(r"[^\W\d_]", s)) and not re.fullmatch(r"\d+[a-zа-я]{1,3}", s)
        ic_buyuk = re.search(r"[a-zа-я][A-ZА-Я]", re.sub(r"[^\w]", "", b)) is not None
        if karisik or sessiz or uzun_sessiz or rakam_harf or ic_buyuk:
            kotu += 1
    return kotu / len(belirtecler)


ANLAMSIZ_ESIK = 0.30


def ocr_gorsel(yol, diller=None):
    t = arac("tesseract")
    if not t:
        return None, "tesseract kurulu degil"
    mevcut = ocr_dilleri()
    secilen = [d for d in (diller or ["tur", "eng", "rus"]) if d in mevcut] or ["eng"]
    r = subprocess.run([t, yol, "stdout", "-l", "+".join(secilen), "--psm", "3"], capture_output=True, text=True)
    metin = r.stdout.strip()
    if not metin:
        return None, "OCR metin bulamadi (fotograf, el yazisi ya da bos sayfa olabilir)"
    oran = anlamsiz_oran(metin)
    if oran > ANLAMSIZ_ESIK:
        eksik = [d for d in ("tur", "eng", "rus") if d not in mevcut]
        ek = f"; kurulu olmayan OCR dilleri: {', '.join(eksik)}" if eksik else ""
        return None, f"OCR ciktisi anlamsiz (oran {oran:.2f} > {ANLAMSIZ_ESIK}){ek}; belge elle incelenmeli"
    return metin, f"tesseract ({'+'.join(secilen)})"


def _pdf_metin(yol):
    try:
        import logging, pypdf
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        sayfalar = [(pg.extract_text() or "") for pg in pypdf.PdfReader(yol).pages]
        return sayfalar, "pypdf"
    except ImportError:
        pass
    if arac("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", yol, "-"], capture_output=True, text=True)
        return r.stdout.split("\f"), "pdftotext"
    raise RuntimeError("PDF okuyucu yok (pypdf ya da pdftotext gerekli)")


def oku_pdf(yol, etiket):
    sayfalar, yontem = _pdf_metin(yol)
    if sayfalar and sayfalar[-1] == "" and yontem == "pdftotext":
        sayfalar = sayfalar[:-1]  # pdftotext sondaki form feed'den sonra bos oge uretir
    if sayfalar and all(len((s or "").strip()) >= 20 for s in sayfalar):
        return belge(etiket, "\n\f".join(sayfalar), yontem)
    # metin katmani yok ya da bazi sayfalar bos: bos sayfalari OCR'la
    if not arac("pdftoppm") or not arac("tesseract"):
        metin = "\n\f".join(sayfalar)
        if metin.strip():
            return belge(etiket, metin, yontem + " (bos sayfalar OCR'lanamadi: pdftoppm/tesseract yok)")
        return belge(etiket, durum="okunamadi", neden="metin katmani yok; OCR icin pdftoppm ve tesseract gerekli")
    cikti, ocrlu, sorun = [], 0, []
    with tempfile.TemporaryDirectory() as td:
        for i, s in enumerate(sayfalar, 1):
            if len((s or "").strip()) >= 20:
                cikti.append(s)
                continue
            onek = os.path.join(td, f"s{i}")
            subprocess.run(["pdftoppm", "-r", "250", "-gray", "-png", "-f", str(i), "-l", str(i), "-singlefile", yol, onek],
                           capture_output=True)
            m, neden = ocr_gorsel(onek + ".png")
            if m:
                cikti.append(OCR_ETIKET + m)
                ocrlu += 1
            else:
                cikti.append("")
                sorun.append(f"sayfa {i}: {neden}")
    metin = "\n\f".join(cikti)
    if not metin.strip():
        return belge(etiket, durum="okunamadi", neden="; ".join(sorun) or "metin yok", ocr=True)
    d = belge(etiket, metin, f"{yontem} + OCR ({ocrlu} sayfa)", ocr=ocrlu > 0)
    if sorun:
        d["neden"] = "kismen okunamadi: " + "; ".join(sorun)
    return d


# ---------------------------------------------------------------- e-posta
def _eposta_belge(m, etiket, tmp, derinlik):
    bas = {k: str(m[k]) for k in ("from", "to", "cc", "bcc", "date", "subject", "message-id", "in-reply-to") if m[k]}
    ust = "".join(f"{k.title()}: {v}\n" for k, v in bas.items()) + "\n"
    try:
        g = m.get_body(preferencelist=("plain", "html"))
        govde = g.get_content() if g else ""
        if g is not None and g.get_content_type() == "text/html":
            govde = re.sub(r"<[^>]+>", " ", govde)
    except Exception as ex:
        govde = f"[GOVDE OKUNAMADI: {ex}]"
    cocuk = []
    for i, ek in enumerate(m.iter_attachments(), 1):
        ad = ek.get_filename() or f"ek{i}{'.eml' if ek.get_content_type() == 'message/rfc822' else '.bin'}"
        ad = re.sub(r"[\\/:*?\"<>|]", "_", ad)
        try:
            if ek.get_content_type() == "message/rfc822":
                ic = ek.get_payload(0) if ek.is_multipart() else email.message_from_bytes(ek.get_payload(decode=True) or b"", policy=policy.default)
                cocuk.append(_eposta_belge(ic, f"{etiket}#{ad}", tmp, derinlik + 1))
                continue
            veri = ek.get_payload(decode=True) or b""
            p = os.path.join(tmp, f"{len(os.listdir(tmp))}_{ad}")
            with open(p, "wb") as f:
                f.write(veri)
            cocuk.append(oku(p, f"{etiket}#{ad}", derinlik + 1))
        except Exception as ex:
            cocuk.append(belge(f"{etiket}#{ad}", durum="okunamadi", neden=f"ek acilamadi: {ex}"))
    return belge(etiket, ust + govde, "eml", basliklar=bas, cocuklar=cocuk)


def oku_eml(yol, etiket, derinlik):
    m = email.message_from_bytes(open(yol, "rb").read(), policy=policy.default)
    tmp = tempfile.mkdtemp(prefix="rr_ek_")
    try:
        return _eposta_belge(m, etiket, tmp, derinlik)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def oku_pst(yol, etiket, derinlik):
    rp = arac("readpst")
    if not rp:
        return belge(etiket, durum="okunamadi", neden="PST/OST icin readpst gerekli (pst-utils / libpst)")
    td = tempfile.mkdtemp(prefix="rr_pst_")
    try:
        r = subprocess.run([rp, "-e", "-D", "-8", "-b", "-q", "-o", td, yol], capture_output=True, text=True)
        cocuk = []
        for kok, _, ds in os.walk(td):
            for d in sorted(ds, key=lambda x: (len(x), x)):
                p = os.path.join(kok, d)
                ic_etiket = f"{etiket}#{os.path.relpath(p, td).replace(os.sep, '/')}"
                cocuk.append(oku(p, ic_etiket, derinlik + 1))
        if not cocuk:
            neden = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["oge bulunamadi"]
            return belge(etiket, durum="okunamadi", neden=f"readpst: {neden[0][:200]}")
        return belge(etiket, f"[POSTA KUTUSU: {len(cocuk)} oge]", "readpst", cocuklar=cocuk)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def oku_tnef(yol, etiket, derinlik):
    try:
        import tnefparse
    except ImportError:
        return belge(etiket, durum="okunamadi", neden="winmail.dat icin tnefparse gerekli (pip install tnefparse)")
    t = tnefparse.TNEF(open(yol, "rb").read())
    govde = (t.body or b"").decode("utf-8", "replace") if isinstance(t.body, bytes) else (t.body or "")
    td = tempfile.mkdtemp(prefix="rr_tnef_")
    try:
        cocuk = []
        for ek in t.attachments:
            ad = re.sub(r"[\\/:*?\"<>|]", "_", ek.long_filename() or ek.name or "ek.bin")
            p = os.path.join(td, ad)
            open(p, "wb").write(ek.data)
            cocuk.append(oku(p, f"{etiket}#{ad}", derinlik + 1))
        return belge(etiket, govde, "tnefparse", cocuklar=cocuk)
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------- arsivler
def _guvenli_mi(kok, hedef):
    kok = os.path.realpath(kok)
    return os.path.realpath(hedef).startswith(kok + os.sep)


def oku_arsiv(yol, etiket, derinlik):
    e = yol.lower()
    td = tempfile.mkdtemp(prefix="rr_arsiv_")
    try:
        if e.endswith(".zip"):
            with zipfile.ZipFile(yol) as z:
                for i in z.infolist():
                    if i.flag_bits & 0x1:
                        return belge(etiket, durum="okunamadi", neden="parolali zip")
                    if not _guvenli_mi(td, os.path.join(td, i.filename)):
                        continue
                    z.extract(i, td)
        elif re.search(r"\.(tar|tgz|tar\.gz|tar\.bz2|tar\.xz)$", e):
            with tarfile.open(yol) as t:
                uyeler = [m for m in t.getmembers() if m.isfile() and _guvenli_mi(td, os.path.join(td, m.name))]
                t.extractall(td, members=uyeler)
        elif e.endswith((".gz", ".bz2", ".xz")):
            import bz2, gzip, lzma
            ac = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}[os.path.splitext(e)[1]]
            hedef = os.path.join(td, os.path.splitext(os.path.basename(yol))[0])
            with ac(yol, "rb") as f, open(hedef, "wb") as g:
                shutil.copyfileobj(f, g)
        elif e.endswith(".rar") and arac("unrar"):
            r = subprocess.run([arac("unrar"), "x", "-p-", "-o+", "-inul", yol, td + os.sep], capture_output=True)
            if r.returncode != 0:
                return belge(etiket, durum="okunamadi", neden="unrar acamadi (parolali ya da bozuk olabilir)")
        elif e.endswith((".7z", ".rar")) and (arac("7z") or arac("7zz")):
            r = subprocess.run([arac("7z") or arac("7zz"), "x", "-y", "-p", f"-o{td}", yol], capture_output=True)
            if r.returncode != 0:
                return belge(etiket, durum="okunamadi", neden="7z acamadi (parolali ya da bozuk olabilir)")
        else:
            return belge(etiket, durum="okunamadi", neden=f"{os.path.splitext(e)[1]} icin acici yok (unrar ya da 7z)")
        cocuk = []
        for kok, _, ds in os.walk(td):
            for d in sorted(ds):
                p = os.path.join(kok, d)
                if not _guvenli_mi(td, p) or os.path.islink(p):
                    continue
                cocuk.append(oku(p, f"{etiket}#{os.path.relpath(p, td).replace(os.sep, '/')}", derinlik + 1))
        return belge(etiket, f"[ARSIV: {len(cocuk)} dosya]", "arsiv", cocuklar=cocuk)
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------- OpenDocument, RTF
def oku_odf(yol, etiket):
    with zipfile.ZipFile(yol) as z:
        xml = z.read("content.xml")
    kok = ElementTree.fromstring(xml)
    satirlar = []
    for el in kok.iter():
        ad = el.tag.split("}")[-1]
        if ad in ("p", "h"):
            satirlar.append("".join(el.itertext()))
        elif ad == "table-cell":
            satirlar.append("".join(el.itertext()))
    return belge(etiket, "\n".join(s for s in satirlar if s.strip()), "odf")


def oku_rtf(yol, etiket):
    ham = open(yol, "rb").read().decode("latin-1")
    kod = re.search(r"\\ansicpg(\d+)", ham)
    sayfa = f"cp{kod.group(1)}" if kod else "cp1252"

    def hex_coz(m):
        return bytes([int(m.group(1), 16)]).decode(sayfa, "replace")

    def uni_coz(m):
        n = int(m.group(1))
        return chr(n + 65536 if n < 0 else n)

    t = re.sub(r"\{\\\*[^{}]*\}", "", ham)
    t = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", t)
    t = re.sub(r"\\u(-?\d+)\??", uni_coz, t)
    t = re.sub(r"\\'([0-9a-fA-F]{2})", hex_coz, t)
    t = re.sub(r"\\(par|line)\b ?", "\n", t)
    t = re.sub(r"\\tab\b ?", "\t", t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
    t = t.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    t = re.sub(r"[{}]", "", t)
    return belge(etiket, re.sub(r"\n{3,}", "\n\n", t).strip(), "rtf")


# ---------------------------------------------------------------- eski Office (.doc/.xls/.ppt)
METIN_UZANTI = {".url", ".vcf", ".ics", ".ini", ".xml", ".tsv", ".rtx"}


def oku_eski_office(yol, etiket, e):
    """catdoc paketi (catdoc, xls2csv, catppt) varsa eski ikili Office bicimlerini metne cevirir."""
    ad = {".doc": "catdoc", ".xls": "xls2csv", ".ppt": "catppt"}[e]
    t = arac(ad)
    if not t:
        return belge(etiket, durum="okunamadi", neden=f"eski Office bicimi ({e}); {ad} (catdoc paketi) gerekli ya da elle incelenmeli")
    arg = [t, "-d", "utf-8", yol] if ad != "xls2csv" else [t, "-d", "utf-8", "-q", "3", yol]
    r = subprocess.run(arg, capture_output=True)
    metin = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0 or not metin.strip():
        return belge(etiket, durum="okunamadi", neden=f"{ad} metin cikaramadi (parolali, bozuk ya da yalniz gorsel olabilir)")
    return belge(etiket, metin, ad)


# ---------------------------------------------------------------- icerikten tur tahmini
def tur_tahmin(yol):
    """Ilk baytlara bakarak uzanti tahmin eder; bilinmiyorsa None. '.ole' eski Office/OLE kapsayicisi demektir."""
    with open(yol, "rb") as f:
        bas = f.read(4096)
    if bas.startswith(b"%PDF"):
        return ".pdf"
    if bas.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(yol) as z:
                adlar = z.namelist()
        except zipfile.BadZipFile:
            return None
        for onek, uz in (("word/", ".docx"), ("xl/", ".xlsx"), ("ppt/", ".pptx")):
            if any(a.startswith(onek) for a in adlar):
                return uz
        if "content.xml" in adlar:
            return ".odt"
        return ".zip"
    for imza, uz in ((b"\x89PNG", ".png"), (b"GIF8", ".gif"), (b"\xff\xd8\xff", ".jpg"), (b"II*\x00", ".tif"),
                     (b"MM\x00*", ".tif"), (b"BM", ".bmp"), (b"{\\rtf", ".rtf"), (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", ".ole")):
        if bas.startswith(imza):
            return uz
    if bas.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        return ".html"
    if _eml_gibi(yol):
        return ".eml"
    if bas and b"\x00" not in bas:
        try:
            bas.decode("utf-8")
        except UnicodeDecodeError:
            if sum(32 <= c < 127 or c in (9, 10, 13) for c in bas) / len(bas) < 0.85:
                return None
        return ".txt"
    return None


def oku_ole(yol, etiket):
    """Uzantisi bilinmeyen OLE dosyasi: Word, Excel, PowerPoint donusturuculerini sirayla dener."""
    for e in (".doc", ".xls", ".ppt"):
        d = oku_eski_office(yol, etiket, e)
        if d["durum"] == "islendi":
            d["yontem"] += " (tur icerikten: OLE)"
            return d
    return belge(etiket, durum="okunamadi", neden="OLE kapsayicisi (eski Office ya da Outlook .msg); metin cikarilamadi, elle incelenmeli")


# ---------------------------------------------------------------- dagitici
def oku(yol, etiket=None, derinlik=0):
    """Bir dosyayi okur. Donus: belge sozlugu (cocuklar dahil)."""
    etiket = etiket or os.path.basename(yol)
    if derinlik > EN_FAZLA_DERINLIK:
        return belge(etiket, durum="okunamadi", neden="ic ice kapsayici derinligi asildi")
    e = os.path.splitext(yol)[1].lower()
    ad = os.path.basename(yol).lower()
    try:
        if e in (".pst", ".ost"):
            return oku_pst(yol, etiket, derinlik)
        if ad == "winmail.dat":
            return oku_tnef(yol, etiket, derinlik)
        if e == ".eml" or (e == "" and _eml_gibi(yol)):
            return oku_eml(yol, etiket, derinlik)
        if e in ARSIV or ad.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            return oku_arsiv(yol, etiket, derinlik)
        if e in GORSEL:
            m, neden = ocr_gorsel(yol)
            if m:
                return belge(etiket, OCR_ETIKET + m, neden, ocr=True)
            return belge(etiket, durum="okunamadi", neden=neden, ocr=True)
        if e == ".pdf":
            return oku_pdf(yol, etiket)
        if e in (".odt", ".ods", ".odp"):
            return oku_odf(yol, etiket)
        if e == ".rtf":
            return oku_rtf(yol, etiket)
        if e in (".doc", ".xls", ".ppt"):
            return oku_eski_office(yol, etiket, e)
        if e in METIN_UZANTI:
            return belge(etiket, open(yol, encoding="utf-8", errors="replace").read(), "metin")
        try:
            metin, yontem = RT.cikar(yol)
        except ValueError:
            # Uzanti yok ya da tanidik degil (ornegin uzantisiz e-posta eki): icerige bakip turu tahmin et
            tahmin = tur_tahmin(yol)
            if not tahmin or tahmin == e:
                return belge(etiket, durum="okunamadi", neden="desteklenmeyen ya da taninmayan dosya turu")
            if tahmin == ".ole":
                return oku_ole(yol, etiket)
            td = tempfile.mkdtemp(prefix="rr_tur_")
            try:
                kopya = os.path.join(td, "icerik" + tahmin)
                shutil.copyfile(yol, kopya)
                d = oku(kopya, etiket, derinlik + 1)
                d["yontem"] = (d["yontem"] + " " if d["yontem"] else "") + f"(tur icerikten: {tahmin})"
                return d
            finally:
                shutil.rmtree(td, ignore_errors=True)
        return belge(etiket, metin, yontem)
    except Exception as ex:
        return belge(etiket, durum="okunamadi", neden=f"{type(ex).__name__}: {ex}"[:240])


def _eml_gibi(yol):
    try:
        bas = open(yol, "rb").read(2048).decode("utf-8", "replace")
    except OSError:
        return False
    return bool(re.search(r"^(From|Return-Path|Received|Message-ID):", bas, re.M)) and "\n\n" in bas


def duzlestir(d, ust=None):
    """Belge agacini (ust_etiket, belge) listesine cevirir."""
    yield ust, d
    for c in d["cocuklar"]:
        yield from duzlestir(c, d["etiket"])


def doktor():
    satirlar = []
    for ad, ne in (("readpst", "PST/OST"), ("tesseract", "OCR"), ("pdftoppm", "taranmis PDF sayfa goruntusu"),
                   ("catdoc", "eski Word (.doc)"), ("xls2csv", "eski Excel (.xls)"), ("catppt", "eski PowerPoint (.ppt)"),
                   ("pdftotext", "PDF metin katmani (pypdf yoksa)"), ("unrar", "RAR"), ("7z", "7z/RAR")):
        satirlar.append(f"{ne:32} {'VAR' if arac(ad) else 'YOK'}  ({ad})")
    diller = ocr_dilleri()
    satirlar.append(f"{'OCR dilleri':32} {', '.join(d for d in diller if d in ('tur', 'eng', 'rus')) or 'YOK'}")
    if diller and "rus" not in diller:
        satirlar.append("  Uyari: Kiril (rus) OCR paketi yok; Rusca taramalar 'okunamadi' olarak isaretlenir.")
    for paket in ("docx", "openpyxl", "pptx", "pypdf", "extract_msg", "tnefparse"):
        try:
            __import__(paket)
            durum = "VAR"
        except ImportError:
            durum = "YOK"
        satirlar.append(f"{'python: ' + paket:32} {durum}")
    return "\n".join(satirlar)


if __name__ == "__main__":
    print(doktor())
```
