# vaka.py

Bu dosya Claude dizini sürümünde betiğin okunabilir kopyasıdır. Aşağıdaki kodu değiştirmeden çalışma klasörüne `vaka.py` olarak yazın ve SKILL.md'deki komutla çalıştırın. Kaynak: https://github.com/savsay/antitrust-investigator/blob/main/plugins/rekabet-ihlali-inceleme/skills/rekabet-ihlali-inceleme/scripts/vaka.py

```python
"""Vaka defteri: yetki kapisi, okuma defteri, sinyal ve bulgu dogrulamasi, geri tarama, rapor.

Amac: "okudum" demeyi degil, okumayi kanitlamak. Her belge parcalara bolunur; her parca gosterildiginde
tek kullanimlik bir onay kodu uretilir ve parca ancak o kodla isaretlenebilir. Uc gosterge ayri tutulur:
  1) kuyruk          - her parca isaretlendi mi
  2) okuma kapsami   - okunamayan parca/belge kaldi mi
  3) sinyal karari   - her sinyal bir bulguya baglandi ya da gerekceyle kapatildi mi
Hicbiri digerinin yerine gecmez. Rapor, eksik olan her gosterge icin KISMI damgasi tasir.

Yalniz standart kutuphane (+ okuyucular.py ve rekabet_tarama.py). Kaynak dosyalara yazmaz; yalniz vaka
klasorune (vaka.db, rapor/) yazar. Komutlar icin:  python3 vaka.py -h
"""
import argparse, csv, datetime as dt, fnmatch, hashlib, json, math, os, random, re, secrets, sqlite3, sys

BURADA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURADA)
import rekabet_tarama as RT  # noqa: E402

def _ref_klasoru():
    """references klasoru: REKABET_REF ortam degiskeni > betigin ust klasoru > calisma klasoru.
    Claude dizini surumunde betik calisma klasorune yazilir; o zaman REKABET_REF=<skill>/references verilir."""
    adaylar = [os.environ.get("REKABET_REF", ""), os.path.join(os.path.dirname(BURADA), "references"),
               os.path.join(BURADA, "references"), os.path.join(os.getcwd(), "references")]
    for k in adaylar:
        if k and any(os.path.exists(os.path.join(k, f"kontroller.{u}")) for u in ("csv", "json")):
            return k
    return adaylar[1]


REF = _ref_klasoru()
PARCA_BOYU = 3000
SURUM = "1.3.0"

EYLEMLER = {"teklif", "ret", "kabul", "uygulama", "bilgi_paylasimi", "talimat", "silme", "engelleme", "sapma",
            "karar", "taahhut", "sozlesme"}
EK_KATEGORI = {"KOMSU": "Komsu risk (sartname/taahhut sapmasi, ruşvet, haksiz rekabet; rekabet ihlali degil)",
               "GUVENLIK": "Belgeye gomulu talimat ya da istem enjeksiyonu (uygulanmaz, raporlanir)",
               "ERISIM": "Avukat yazismasi / kisisel hesap / yetki disi icerik isareti"}
SUREC_AILESI = {"MT", "HM", "VT", "OP"}
KABUL_RX = re.compile(r"anlas(?!ama|mad|may)|mutabik|uzlas(?!ama|mad|may)|kabul ett|\bagreed|\baccepted|reached an agreement|"
                      r"договорил|согласил")
KOSUL_RX = re.compile(r"kosul|sart(li|iyla)|conditional|условн")
AKTARIM_RX = re.compile(r"aktar|gore|duydug|reported|according to|hearsay|по словам|сообщил")
RET_RX = re.compile(r"reddet|reddedil|kabul etmedi|kabul etmiyor|katilmiyoruz|istemiyoruz|refus|reject|declin|отказ|отклон")
YONLENDIRME_RX = re.compile(r"denetim komite|bagimsiz|audit committee|independent|outside counsel|yonetim kurulu")
IMTIYAZ_RX = re.compile(r"avukat[- ]?muvekkil|attorney[- ]client|privileged (and|&) confidential|legally privileged|"
                        r"адвокатск\w* тайн")
RISK_SIRASI = {"ERISIM": 0, "A": 1, "B": 2, "C": 3, None: 4}


# ---------------------------------------------------------------- yardimcilar
def simdi():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def hata(mesaj, kod=2):
    print(f"HATA: {mesaj}", file=sys.stderr)
    sys.exit(kod)


def katla(s):
    return RT.fold(s or "")


def sha256_dosya(p):
    return RT.sha256(p)


def json_oku(yol):
    try:
        return json.load(open(yol, encoding="utf-8-sig"))
    except FileNotFoundError:
        hata(f"JSON dosyasi yok: {yol}")
    except json.JSONDecodeError as ex:
        hata(f"JSON okunamadi ({yol}): {ex}")


def tablo(ad):
    """references/<ad>.csv ya da (Claude dizini surumu) <ad>.json; ikisi de satir sozlukleri listesi verir."""
    yol = os.path.join(REF, ad + ".csv")
    if os.path.exists(yol):
        with open(yol, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    yol = os.path.join(REF, ad + ".json")
    if os.path.exists(yol):
        return json.load(open(yol, encoding="utf-8"))
    hata(f"katalog bulunamadi: {REF}/{ad}.csv|json (REKABET_REF=<skill klasoru>/references verin)", 3)


def katalog():
    kontrol = {r["control_id"]: r for r in tablo("kontroller")}
    kaynak = {r[list(r)[0]]: r for r in tablo("kaynaklar")}
    aileler = {k.split("-")[0] for k in kontrol} - SUREC_AILESI
    return kontrol, kaynak, aileler | set(EK_KATEGORI)


def aile(k):
    return (k or "").split("-")[0].upper()


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    o = (p + z * z / (2 * n)) / (1 + z * z / n)
    return (max(0.0, o - m), min(1.0, o + m))


# ---------------------------------------------------------------- veritabani
SEMA = """
CREATE TABLE IF NOT EXISTS meta (anahtar TEXT PRIMARY KEY, deger TEXT);
CREATE TABLE IF NOT EXISTS belge (id TEXT PRIMARY KEY, ust TEXT, kaynak TEXT, etiket TEXT, sha256 TEXT, boyut INTEGER,
  yontem TEXT, durum TEXT, neden TEXT, ocr INTEGER DEFAULT 0, tarih TEXT, basliklar TEXT, karakter INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS parca (id TEXT PRIMARY KEY, belge TEXT, sira INTEGER, toplam INTEGER, bas INTEGER, son INTEGER,
  metin TEXT, durum TEXT DEFAULT 'bekliyor', onay TEXT, gosterim INTEGER DEFAULT 0, isci TEXT, isci_zaman TEXT,
  on_seviye TEXT, rastgele INTEGER DEFAULT 0, yeniden_neden TEXT);
CREATE TABLE IF NOT EXISTS isaret (no INTEGER PRIMARY KEY AUTOINCREMENT, parca TEXT, karar TEXT, notu TEXT, zaman TEXT);
CREATE TABLE IF NOT EXISTS sinyal (id TEXT PRIMARY KEY, parca TEXT, kategori TEXT, alinti TEXT, bas INTEGER, son INTEGER,
  notu TEXT, durum TEXT DEFAULT 'acik', bulgu TEXT, gerekce TEXT, sorumlu TEXT, hedef_tarih TEXT, zaman TEXT);
CREATE TABLE IF NOT EXISTS kod (id TEXT PRIMARY KEY, ifade TEXT, hipotez TEXT, dayanak TEXT, parca TEXT, zaman TEXT);
CREATE TABLE IF NOT EXISTS bulgu (id TEXT PRIMARY KEY, veri TEXT, zaman TEXT);
CREATE TABLE IF NOT EXISTS gunluk (no INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT, komut TEXT, ayrinti TEXT);
"""


def baglan(vaka, yeni=False):
    yol = os.path.join(vaka, "vaka.db")
    if not yeni and not os.path.exists(yol):
        hata(f"vaka bulunamadi: {vaka} (once 'vaka.py ac' calistirin)")
    os.makedirs(vaka, exist_ok=True)
    db = sqlite3.connect(yol)
    db.row_factory = sqlite3.Row
    db.executescript(SEMA)
    if not yeni and not meta(db, "olusturma"):
        hata(f"vaka acilisi tamamlanmamis: {vaka} ('vaka.py ac' yetki bilgileriyle yeniden calistirin)", 4)
    return db


def meta(db, k, v=None):
    if v is None:
        r = db.execute("SELECT deger FROM meta WHERE anahtar=?", (k,)).fetchone()
        return r["deger"] if r else ""
    db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, v))


def gunluk(db, komut, ayrinti=""):
    db.execute("INSERT INTO gunluk (zaman, komut, ayrinti) VALUES (?,?,?)", (simdi(), komut, ayrinti[:2000]))


def sonraki_kimlik(db, tablo, onek, genislik):
    n = db.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0] + 1
    while True:
        k = f"{onek}{n:0{genislik}d}"
        if not db.execute(f"SELECT 1 FROM {tablo} WHERE id=?", (k,)).fetchone():
            return k
        n += 1


def kapi_acik_mi(db):
    if meta(db, "sentetik") == "1":
        return True
    return all(meta(db, k).strip() for k in ("yetki", "amac", "kapsam"))


# ---------------------------------------------------------------- ac
def k_ac(a):
    # Kapi veritabani olusmadan once: reddedilen istek arkasinda vaka dosyasi birakmaz.
    if not a.sentetik and not ((a.yetki or "").strip() and (a.amac or "").strip() and (a.kapsam or "").strip()):
        hata("yetki kapisi: --yetki, --amac ve --kapsam zorunludur (gercek veri). Kullaniciya sorun; uydurmayin.", 4)
    db = baglan(a.vaka, yeni=True)
    if meta(db, "olusturma"):
        hata("bu klasorde zaten bir vaka var")
    for k in ("ad", "yetki", "amac", "kapsam", "talep_eden", "ust_yonetim", "muhatap", "veri_kaynagi"):
        meta(db, k, getattr(a, k) or "")
    meta(db, "avukat_alan", ",".join(x.strip().lower() for x in (a.avukat_alan or "").split(",") if x.strip()))
    meta(db, "haric", ",".join(x.strip() for x in (a.haric or "").split(",") if x.strip()))
    meta(db, "ihbarci", ",".join(x.strip() for x in (a.ihbarci or "").split(",") if x.strip()))
    meta(db, "sentetik", "1" if a.sentetik else "0")
    meta(db, "olusturma", simdi())
    meta(db, "surum", SURUM)
    gunluk(db, "ac", json.dumps({k: getattr(a, k) for k in ("ad", "yetki", "amac", "kapsam")}, ensure_ascii=False))
    db.commit()
    print(f"Vaka acildi: {a.vaka}" + ("  [SENTETIK]" if a.sentetik else ""))


# ---------------------------------------------------------------- yukle
def parcala(metin, boy=PARCA_BOYU):
    if len(metin) <= boy:
        return [(0, len(metin))]
    out, i = [], 0
    while i < len(metin):
        j = min(len(metin), i + boy)
        if j < len(metin):
            alt = metin.rfind("\n\n", i + boy // 2, j)
            if alt < 0:
                alt = max(metin.rfind(". ", i + boy // 2, j), metin.rfind("\n", i + boy // 2, j))
            if alt > i:
                j = alt + 1
        out.append((i, j))
        i = j
    return out


def imtiyazli_mi(d, avukat_alanlari):
    bas = " ".join(d["basliklar"].get(k, "") for k in ("from", "to", "cc", "bcc")).lower()
    for alan in avukat_alanlari:
        if alan and re.search(r"@" + re.escape(alan) + r"\b", bas):
            return f"avukat alan adi: {alan}"
    if IMTIYAZ_RX.search(katla(d["metin"][:4000])):
        return "avukat-muvekkil gizliligi ibaresi"
    return ""


def k_yukle(a):
    import okuyucular as O
    db = baglan(a.vaka)
    if not kapi_acik_mi(db):
        hata("yetki kapisi kapali: yetki, amac, kapsam kaydi yok", 4)
    avukat = [x for x in meta(db, "avukat_alan").split(",") if x]
    haric = [x for x in meta(db, "haric").split(",") if x]
    say = {"belge": 0, "parca": 0, "ayrildi": 0, "okunamadi": 0, "atlandi": 0}
    for kok in a.yollar:
        if not os.path.exists(kok):
            hata(f"yol yok: {kok}")
        dosyalar = [kok] if os.path.isfile(kok) else [os.path.join(k, d) for k, _, ds in os.walk(kok) for d in sorted(ds)]
        taban = os.path.dirname(os.path.abspath(kok)) if os.path.isfile(kok) else os.path.abspath(kok)
        for p in sorted(dosyalar):
            goreli = os.path.relpath(os.path.abspath(p), taban).replace(os.sep, "/")
            h = sha256_dosya(p)
            if db.execute("SELECT 1 FROM belge WHERE kaynak=? AND sha256=? AND ust IS NULL", (os.path.abspath(p), h)).fetchone():
                say["atlandi"] += 1
                continue
            if any(fnmatch.fnmatch(goreli, g) or fnmatch.fnmatch("/" + goreli, g) for g in haric):
                bid = sonraki_kimlik(db, "belge", "B", 4)
                db.execute("INSERT INTO belge (id, ust, kaynak, etiket, sha256, boyut, yontem, durum, neden) VALUES (?,?,?,?,?,?,?,?,?)",
                           (bid, None, os.path.abspath(p), goreli, h, os.path.getsize(p), "", "ayrildi", "kapsam disi desen (--haric)"))
                say["belge"] += 1
                say["ayrildi"] += 1
                continue
            agac = O.oku(p, goreli)
            kimlik = {}
            for ust_etiket, d in O.duzlestir(agac):
                bid = sonraki_kimlik(db, "belge", "B", 4)
                kimlik[d["etiket"]] = bid
                ust = kimlik.get(ust_etiket) if ust_etiket else None
                ust_durum = db.execute("SELECT durum FROM belge WHERE id=?", (ust,)).fetchone()["durum"] if ust else ""
                durum, neden = d["durum"], d["neden"]
                if ust_durum == "ayrildi":
                    durum, neden = "ayrildi", "ust belge ayrildi (ek ve alt belgeler de ayrilir)"
                elif durum == "islendi":
                    gerekce = imtiyazli_mi(d, avukat)
                    if gerekce:
                        durum, neden = "ayrildi", gerekce
                    elif not d["metin"].strip():
                        durum, neden = "okunamadi", d["neden"] or "bos metin"
                tarih = d["basliklar"].get("date", "")
                db.execute("INSERT INTO belge (id, ust, kaynak, etiket, sha256, boyut, yontem, durum, neden, ocr, tarih, basliklar, karakter)"
                           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (bid, ust, os.path.abspath(p) if ust is None else None, d["etiket"], h if ust is None else
                            hashlib.sha256(d["metin"].encode("utf-8")).hexdigest(), os.path.getsize(p) if ust is None else len(d["metin"]),
                            d["yontem"], durum, neden, int(d["ocr"]), tarih, json.dumps(d["basliklar"], ensure_ascii=False),
                            len(d["metin"]) if durum == "islendi" else 0))
                say["belge"] += 1
                if durum == "ayrildi":
                    say["ayrildi"] += 1
                    continue
                if durum != "islendi":
                    say["okunamadi"] += 1
                    continue
                if d["metin"].startswith("[POSTA KUTUSU:") or d["metin"].startswith("[ARSIV:"):
                    continue  # kapsayicinin kendisi okunacak icerik tasimaz
                araliklar = parcala(d["metin"])
                for i, (s, e) in enumerate(araliklar, 1):
                    metin = d["metin"][s:e]
                    seviyeler = [h["seviye"] for h in RT.tara(metin)]
                    sv = min(seviyeler, key=lambda x: RISK_SIRASI[x]) if seviyeler else None
                    db.execute("INSERT INTO parca (id, belge, sira, toplam, bas, son, metin, on_seviye) VALUES (?,?,?,?,?,?,?,?)",
                               (f"{bid}-P{i:03d}", bid, i, len(araliklar), s, e, metin, sv))
                    say["parca"] += 1
            db.commit()
    gunluk(db, "yukle", json.dumps(say))
    db.commit()
    print(json.dumps(say, ensure_ascii=False))


# ---------------------------------------------------------------- okuma dongusu
def parca_goster(db, p, rastgele=False):
    onay = secrets.token_hex(3).upper()
    db.execute("UPDATE parca SET onay=?, gosterim=gosterim+1, rastgele=CASE WHEN ? THEN 1 ELSE rastgele END WHERE id=?",
               (onay, int(rastgele), p["id"]))
    b = db.execute("SELECT * FROM belge WHERE id=?", (p["belge"],)).fetchone()
    ocr = " [OCR METNİ]" if b["ocr"] else ""
    ust = f" | ust: {b['ust']}" if b["ust"] else ""
    print(f"===== {p['id']}  ({b['etiket']}{ust} | parca {p['sira']}/{p['toplam']} | karakter {p['bas']}-{p['son']}"
          f"{' | on-tarama: ' + p['on_seviye'] if p['on_seviye'] else ''}{' | YENIDEN: ' + (p['yeniden_neden'] or '') if p['durum'] == 'yeniden' else ''}){ocr}")
    if p["on_seviye"] == "ERISIM":
        print("!! ERISIM: avukat yazismasi, kisisel hesap ya da yetki disi icerik isareti. Icerigi analiz etmeden once erisim "
              "yetkisini dogrulayin; yetki yoksa karar 'kapsam_disi' ve gerekceyle isaretleyip hukuka yonlendirin.")
    print(p["metin"])
    print(f"[[ONAY: {onay}]]")
    print()


def k_sonraki(a):
    db = baglan(a.vaka)
    simdi_t = dt.datetime.now().astimezone()
    sinir = (simdi_t - dt.timedelta(minutes=30)).isoformat(timespec="seconds")
    kosul = "durum='yeniden'" if a.yeniden else "durum IN ('bekliyor','yeniden')"
    isci_kosul = "" if not a.isci else " AND (isci IS NULL OR isci=? OR isci_zaman<?)"
    parametre = [a.isci, sinir] if a.isci else []
    satirlar = db.execute(f"SELECT * FROM parca WHERE {kosul}{isci_kosul}", parametre).fetchall()
    if not satirlar:
        print("Kuyruk bos: bekleyen ya da yeniden okunacak parca yok.")
        return
    if a.rastgele:
        satirlar = random.sample(list(satirlar), min(a.n, len(satirlar)))
    else:
        satirlar = sorted(satirlar, key=lambda p: (p["durum"] != "yeniden", RISK_SIRASI.get(p["on_seviye"], 4), p["belge"], p["sira"]))[:a.n]
    for p in satirlar:
        if a.isci:
            db.execute("UPDATE parca SET isci=?, isci_zaman=? WHERE id=?", (a.isci, simdi(), p["id"]))
        parca_goster(db, p, a.rastgele)
    db.commit()
    kalan = db.execute("SELECT COUNT(*) FROM parca WHERE durum IN ('bekliyor','yeniden')").fetchone()[0]
    print(f"-- Kalan: {kalan} parca. Her parcayi sonuna kadar okuyun; isaret kaydina parcanin ONAY kodunu yazin.")


def k_goster(a):
    db = baglan(a.vaka)
    p = db.execute("SELECT * FROM parca WHERE id=?", (a.kimlik,)).fetchone()
    if p:
        parca_goster(db, p)
        db.commit()
        return
    b = db.execute("SELECT * FROM belge WHERE id=?", (a.kimlik,)).fetchone()
    if not b:
        hata(f"boyle bir parca/belge yok: {a.kimlik}")
    if b["durum"] == "ayrildi":
        hata(f"{a.kimlik} ayrilmis (kisitli) belge; icerigi gosterilmez. Neden: {b['neden']}")
    for p in db.execute("SELECT * FROM parca WHERE belge=? ORDER BY sira", (a.kimlik,)):
        parca_goster(db, p)
    db.commit()


def k_isaretle(a):
    db = baglan(a.vaka)
    _, _, kategoriler = katalog()
    kayitlar = json_oku(a.json)
    kayitlar = kayitlar if isinstance(kayitlar, list) else [kayitlar]
    hatalar, tamam = [], 0
    for i, r in enumerate(kayitlar, 1):
        pid = r.get("parca", "")
        p = db.execute("SELECT * FROM parca WHERE id=?", (pid,)).fetchone()
        if not p:
            hatalar.append(f"#{i} {pid}: boyle bir parca yok")
            continue
        if p["durum"] not in ("bekliyor", "yeniden"):
            hatalar.append(f"#{i} {pid}: parca zaten '{p['durum']}' (yeniden okunmasi gerekiyorsa 'ara --yeniden-ac' kullanin)")
            continue
        if not p["onay"]:
            hatalar.append(f"#{i} {pid}: parca henuz gosterilmedi; once 'sonraki' ya da 'goster' ile okuyun")
            continue
        if str(r.get("onay", "")).strip().upper() != p["onay"]:
            hatalar.append(f"#{i} {pid}: onay kodu tutmuyor; parcayi yeniden gosterip sonuna kadar okuyun")
            continue
        karar = r.get("karar", "")
        notu = (r.get("not") or "").strip()
        sinyaller = r.get("sinyaller") or []
        if karar not in ("temiz", "sinyal", "okunamadi", "kapsam_disi"):
            hatalar.append(f"#{i} {pid}: karar temiz|sinyal|okunamadi|kapsam_disi olmali")
            continue
        if karar in ("okunamadi", "kapsam_disi") and len(notu) < 10:
            hatalar.append(f"#{i} {pid}: '{karar}' karari gerekce ister (not, en az 10 karakter)")
            continue
        if karar == "sinyal" and not sinyaller:
            hatalar.append(f"#{i} {pid}: 'sinyal' kararinda en az bir sinyal gerekir")
            continue
        if karar != "sinyal" and sinyaller:
            hatalar.append(f"#{i} {pid}: sinyal kaydi varken karar 'sinyal' olmali")
            continue
        sorun = []
        for s in sinyaller:
            kat = (s.get("kategori") or "").upper()
            alinti = s.get("alinti") or ""
            if aile(kat) not in kategoriler:
                sorun.append(f"gecersiz kategori '{kat}' (gecerli: {', '.join(sorted(kategoriler))})")
            if not alinti.strip() or alinti not in p["metin"]:
                sorun.append(f"alinti parcada birebir yok: {alinti[:60]!r}")
        if sorun:
            hatalar.append(f"#{i} {pid}: " + "; ".join(sorun))
            continue
        yeni = {"temiz": "incelendi", "sinyal": "incelendi", "okunamadi": "okunamadi", "kapsam_disi": "kapsam_disi"}[karar]
        db.execute("UPDATE parca SET durum=?, onay=NULL, isci=NULL, yeniden_neden=NULL WHERE id=?", (yeni, pid))
        db.execute("INSERT INTO isaret (parca, karar, notu, zaman) VALUES (?,?,?,?)", (pid, karar, notu, simdi()))
        for s in sinyaller:
            sid = sonraki_kimlik(db, "sinyal", "S-", 4)
            bas = p["metin"].find(s["alinti"])
            db.execute("INSERT INTO sinyal (id, parca, kategori, alinti, bas, son, notu, zaman) VALUES (?,?,?,?,?,?,?,?)",
                       (sid, pid, s["kategori"].upper(), s["alinti"], bas, bas + len(s["alinti"]), s.get("not", ""), simdi()))
        tamam += 1
    gunluk(db, "isaretle", f"{tamam} kayit, {len(hatalar)} hata")
    db.commit()
    print(f"Islenen: {tamam}  Reddedilen: {len(hatalar)}")
    for h in hatalar:
        print("  RED " + h)
    if hatalar:
        sys.exit(1)


# ---------------------------------------------------------------- gostergeler
def gostergeler(db):
    c = lambda q, *p: db.execute(q, p).fetchone()[0]  # noqa: E731
    g = {
        "parca_toplam": c("SELECT COUNT(*) FROM parca"),
        "bekleyen": c("SELECT COUNT(*) FROM parca WHERE durum='bekliyor'"),
        "yeniden": c("SELECT COUNT(*) FROM parca WHERE durum='yeniden'"),
        "incelendi": c("SELECT COUNT(*) FROM parca WHERE durum='incelendi'"),
        "okunamayan_parca": c("SELECT COUNT(*) FROM parca WHERE durum='okunamadi'"),
        "kapsam_disi_parca": c("SELECT COUNT(*) FROM parca WHERE durum='kapsam_disi'"),
        "elle_belge": c("SELECT COUNT(*) FROM belge WHERE durum='okunamadi'"),
        "ayrilan_belge": c("SELECT COUNT(*) FROM belge WHERE durum='ayrildi'"),
        "belge_toplam": c("SELECT COUNT(*) FROM belge"),
        "acik_sinyal": c("SELECT COUNT(*) FROM sinyal WHERE durum='acik'"),
        "sinyal_toplam": c("SELECT COUNT(*) FROM sinyal"),
        "bulgu": c("SELECT COUNT(*) FROM bulgu"),
    }
    g["kuyruk_tamam"] = g["bekleyen"] == 0 and g["yeniden"] == 0 and g["parca_toplam"] > 0
    g["kapsam_tam"] = g["kuyruk_tamam"] and g["okunamayan_parca"] == 0 and g["elle_belge"] == 0
    g["sinyal_tamam"] = g["acik_sinyal"] == 0
    return g


def k_durum(a):
    db = baglan(a.vaka)
    g = gostergeler(db)
    ok = lambda b: "TAMAM" if b else "EKSIK"  # noqa: E731
    print(f"Vaka: {meta(db, 'ad') or a.vaka}{'  [SENTETIK]' if meta(db, 'sentetik') == '1' else ''}")
    print(f"Belgeler: {g['belge_toplam']} (ayrilan {g['ayrilan_belge']}, elle ele alinacak {g['elle_belge']})")
    print(f"1) Kuyruk          : {ok(g['kuyruk_tamam'])}  bekleyen={g['bekleyen']} yeniden={g['yeniden']} incelendi={g['incelendi']}/{g['parca_toplam']}")
    print(f"2) Okuma kapsami   : {ok(g['kapsam_tam'])}  okunamayan parca={g['okunamayan_parca']} elle ele alinacak belge={g['elle_belge']} "
          f"kapsam disi parca={g['kapsam_disi_parca']}")
    print(f"3) Sinyal karari   : {ok(g['sinyal_tamam'])}  acik sinyal={g['acik_sinyal']} / {g['sinyal_toplam']}  bulgu={g['bulgu']}")
    elle = db.execute("SELECT id, etiket, neden FROM belge WHERE durum='okunamadi'").fetchall()
    if elle:
        print("Elle ele alinacak belgeler:")
        for b in elle:
            print(f"  {b['id']}  {b['etiket']}  -- {b['neden']}")
    ayr = db.execute("SELECT id, etiket, neden FROM belge WHERE durum='ayrildi' AND (ust IS NULL OR ust NOT IN (SELECT id FROM belge WHERE durum='ayrildi'))").fetchall()
    if ayr:
        print("Ayrilan (kisitli) belgeler — icerik okunmadi, hukuka:")
        for b in ayr:
            print(f"  {b['id']}  {b['etiket']}  -- {b['neden']}")
    if not (g["kuyruk_tamam"] and g["kapsam_tam"] and g["sinyal_tamam"]):
        print("Not: 'kuyruk bitti' ≠ 'tamami okundu' ≠ 'riskler eksiksiz raporlandi'. Eksik gostergeyle rapor KISMI damgasi tasir.")


# ---------------------------------------------------------------- arama, kod, hafiza
def ara_isabetler(db, ifade, duzenli):
    rx = re.compile(katla(ifade) if duzenli else re.escape(katla(ifade)))
    for p in db.execute("SELECT p.* FROM parca p JOIN belge b ON b.id=p.belge WHERE b.durum='islendi'"):
        m = rx.search(katla(p["metin"]))
        if m:
            yield p, m.start(), m.end()


def geri_tara(db, ifade, duzenli, neden):
    acilan, isabet = 0, []
    for p, s, e in ara_isabetler(db, ifade, duzenli):
        isabet.append((p, s, e))
        if p["durum"] == "incelendi":
            db.execute("UPDATE parca SET durum='yeniden', onay=NULL, yeniden_neden=? WHERE id=?", (neden[:200], p["id"]))
            acilan += 1
    return isabet, acilan


def k_ara(a):
    db = baglan(a.vaka)
    if a.yeniden_ac:
        isabet, acilan = geri_tara(db, a.ifade, a.duzenli, f"geri tarama: {a.ifade}")
        gunluk(db, "ara --yeniden-ac", f"{a.ifade}: {len(isabet)} isabet, {acilan} parca yeniden acildi")
        db.commit()
    else:
        isabet, acilan = list(ara_isabetler(db, a.ifade, a.duzenli)), 0
    for p, s, e in isabet[:200]:
        bag = p["metin"][max(0, s - 80):e + 80].replace("\n", " ")
        print(f"{p['id']}  [{p['durum']}]  …{bag}…")
    print(f"-- {len(isabet)} isabet" + (f"; {acilan} incelenmis parca yeniden okunmak uzere acildi ('sonraki --yeniden')" if a.yeniden_ac else ""))


def k_kod_ekle(a):
    db = baglan(a.vaka)
    if len((a.dayanak or "").strip()) < 15:
        hata("kod hipotezi dayanak ister (hangi baglam, neden kod olabilir; en az 15 karakter)")
    if a.parca and not db.execute("SELECT 1 FROM parca WHERE id=?", (a.parca,)).fetchone():
        hata(f"boyle bir parca yok: {a.parca}")
    kid = sonraki_kimlik(db, "kod", "K-", 3)
    db.execute("INSERT INTO kod VALUES (?,?,?,?,?,?)", (kid, a.ifade, a.hipotez, a.dayanak, a.parca or "", simdi()))
    isabet, acilan = geri_tara(db, a.ifade, False, f"kod hipotezi {kid}: '{a.ifade}' = {a.hipotez}")
    gunluk(db, "kod-ekle", f"{kid} {a.ifade} -> {a.hipotez}; {len(isabet)} isabet, {acilan} yeniden")
    db.commit()
    print(f"{kid} kaydedildi (HIPOTEZ, olgu degil): '{a.ifade}' → {a.hipotez}")
    print(f"Geri tarama: {len(isabet)} parcada geciyor; {acilan} incelenmis parca yeniden okunmak uzere acildi.")
    if acilan:
        print("Simdi 'sonraki --yeniden' ile bu parcalari yeni hipotez isiginda tekrar okuyun.")


def k_hafiza(a):
    db = baglan(a.vaka)
    print("== Kod sozlugu (hipotezler; olgu degil)")
    for k in db.execute("SELECT * FROM kod ORDER BY id"):
        print(f"  {k['id']}  '{k['ifade']}' → {k['hipotez']}  | dayanak: {k['dayanak']}{'  | ilk: ' + k['parca'] if k['parca'] else ''}")
    print("== Varliklar (e-posta adresleri ve alan adlari, gecis sayisi)")
    adres = {}
    for b in db.execute("SELECT basliklar FROM belge WHERE durum='islendi' AND basliklar IS NOT NULL"):
        for v in (json.loads(b["basliklar"] or "{}") or {}).values():
            for e in re.findall(r"[\w.+-]+@[\w.-]+", v or ""):
                adres[e.lower()] = adres.get(e.lower(), 0) + 1
    for e, n in sorted(adres.items(), key=lambda x: -x[1])[:40]:
        print(f"  {n:4}  {e}")
    print("== Zaman cizelgesi (sinyal tasiyan e-postalar)")
    for r in db.execute("SELECT s.id, s.kategori, s.alinti, b.tarih, b.etiket FROM sinyal s JOIN parca p ON p.id=s.parca "
                        "JOIN belge b ON b.id=p.belge ORDER BY b.tarih"):
        print(f"  {r['tarih'] or '(tarihsiz)':32} {r['id']} {r['kategori']:6} {r['alinti'][:70]!r}  [{r['etiket']}]")
    g = gostergeler(db)
    print(f"== Ilerleme: {g['incelendi']}/{g['parca_toplam']} parca incelendi; acik sinyal {g['acik_sinyal']}")


def k_capraz(a):
    """Belgeler arasi baglantilar: ayni yazisma zinciri, ayni ek, ayni ozet (kopya)."""
    db = baglan(a.vaka)
    zincir = {}
    for b in db.execute("SELECT id, etiket, basliklar FROM belge WHERE basliklar IS NOT NULL AND basliklar!='{}'"):
        h = json.loads(b["basliklar"])
        konu = re.sub(r"^((re|fw|fwd|ynt|ilt|tr)\s*:\s*)+", "", (h.get("subject") or "").strip(), flags=re.I).lower()
        if konu:
            zincir.setdefault(konu, []).append(b["id"])
    print("== Ayni yazisma zinciri (konu)")
    for k, v in zincir.items():
        if len(v) > 1:
            print(f"  {k[:60]!r}: {', '.join(v)}")
    print("== Kopya icerik (ayni ozet; bagimsiz teyit sayilmaz)")
    for r in db.execute("SELECT sha256, GROUP_CONCAT(id) AS ids, COUNT(*) AS n FROM belge WHERE durum='islendi' GROUP BY sha256 HAVING n>1"):
        print(f"  {r['ids']}")


def k_baglam(a):
    db = baglan(a.vaka)
    p = db.execute("SELECT * FROM parca WHERE id=?", (a.kimlik,)).fetchone()
    bid = p["belge"] if p else a.kimlik
    b = db.execute("SELECT * FROM belge WHERE id=?", (bid,)).fetchone()
    if not b:
        hata(f"bulunamadi: {a.kimlik}")
    kok = b["ust"] or b["id"]
    print(f"Belge {bid}: {b['etiket']}  (ust: {b['ust'] or '-'})")
    print("Ayni kapsayicidaki belgeler (ekler, ust ileti):")
    for x in db.execute("SELECT id, etiket, durum FROM belge WHERE (id=? OR ust=? OR ust=?) AND id!=?", (kok, kok, bid, bid)):
        print(f"  {x['id']}  {x['etiket']}  [{x['durum']}]")
    h = json.loads(b["basliklar"] or "{}")
    konu = re.sub(r"^((re|fw|fwd|ynt|ilt|tr)\s*:\s*)+", "", (h.get("subject") or "").strip(), flags=re.I).lower()
    if konu:
        print("Ayni zincirdeki iletiler (yanit, ret ya da kabul baska iletide olabilir):")
        for x in db.execute("SELECT id, etiket, tarih, basliklar FROM belge WHERE basliklar IS NOT NULL AND id!=?", (bid,)):
            k2 = re.sub(r"^((re|fw|fwd|ynt|ilt|tr)\s*:\s*)+", "", (json.loads(x["basliklar"]).get("subject") or "").strip(), flags=re.I).lower()
            if k2 == konu:
                print(f"  {x['id']}  {x['tarih'] or ''}  {x['etiket']}")


# ---------------------------------------------------------------- bulgu
def bulgu_dogrula(db, f):
    """Bulgu kaydini kurallara gore denetler. Donus: (hatalar, uyarilar, kanit_konumlari, baglanacak_sinyaller)."""
    kontrol, kaynak, kategoriler = katalog()
    H, U = [], []
    for alan in ("baslik", "ozet", "kategori", "oncelik", "sonraki_adim"):
        if not str(f.get(alan, "")).strip():
            H.append(f"'{alan}' bos olamaz")
    if f.get("oncelik") and f["oncelik"] not in ("Acil", "Yüksek", "Orta", "Düşük"):
        H.append("oncelik: Acil | Yüksek | Orta | Düşük")
    if f.get("alan", "rekabet") not in ("rekabet", "komsu"):
        H.append("alan: rekabet | komsu")
    if f.get("tur", "risk_signal") not in ("risk_signal", "insufficient_context"):
        H.append("tur: risk_signal | insufficient_context")
    d = f.get("degerlendirme")
    if d is not None:
        if not isinstance(d, dict) or set(d) - set(DEGERLENDIRME) or any(v not in ("Yüksek", "Orta", "Düşük") for v in d.values()):
            H.append("degerlendirme: {'etki'|'aciliyet'|'kanit_yeterliligi': 'Yüksek'|'Orta'|'Düşük'} biciminde olmali")
    for kid in f.get("kod_hipotezleri") or []:
        if not db.execute("SELECT 1 FROM kod WHERE id=?", (kid,)).fetchone():
            H.append(f"kod hipotezi yok: {kid} (once 'kod-ekle')")
    for alan in ("ihale_uyarilari", "yetki_alani"):
        if f.get(alan) is not None and not (isinstance(f[alan], list) and all(isinstance(x, str) for x in f[alan])):
            H.append(f"'{alan}' metin listesi olmali")
    kat = str(f.get("kategori", "")).upper()
    if kat and aile(kat) not in kategoriler:
        H.append(f"kategori gecersiz: {kat}")
    if kat and "-" in kat and kat not in kontrol:
        H.append(f"kategori kontrol kimligi katalogda yok: {kat}")
    for k in f.get("kontroller", []) or []:
        if k not in kontrol:
            H.append(f"kontrol kimligi katalogda yok: {k}")
    if aile(kat) == "KOMSU" and f.get("alan") != "komsu":
        H.append("KOMSU kategorisindeki bulgu 'alan': 'komsu' olmali (rekabet ihlali diye adlandirilmaz)")
    for alan in ("eksik_olgular", "masum_aciklamalar"):
        if not [x for x in f.get(alan) or [] if str(x).strip()]:
            H.append(f"'{alan}' en az bir madde icermeli (kendine karsi calis)")
    # kanitlar
    kanitlar = f.get("kanitlar") or []
    if not any((k.get("rol") or "destek") == "destek" for k in kanitlar):
        H.append("en az bir destekleyici kanit gerekir (istatistiksel uyari tek basina bulgu acamaz)")
    kanit_konum, kanit_metin = {}, {}
    for k in kanitlar:
        kid, pid, alinti = k.get("id"), k.get("parca", ""), k.get("alinti") or ""
        if not kid:
            H.append("her kanitin 'id' alani olmali (ornek: K1)")
            continue
        p = db.execute("SELECT p.*, b.durum AS bdurum FROM parca p JOIN belge b ON b.id=p.belge WHERE p.id=?", (pid,)).fetchone()
        if not p:
            H.append(f"{kid}: parca kimligi yok: {pid!r} (belge alanina B…-P… yazin)")
            continue
        if p["bdurum"] == "ayrildi":
            H.append(f"{kid}: ayrilmis belgeden alinti kullanilamaz")
            continue
        if p["durum"] != "incelendi":
            H.append(f"{kid}: {pid} henuz okunup isaretlenmedi (durum: {p['durum']}); okunmamis parcadan kanit olmaz")
            continue
        if not alinti.strip():
            H.append(f"{kid}: alinti bos")
            continue
        yerler = [m.start() for m in re.finditer(re.escape(alinti), p["metin"])]
        if not yerler:
            H.append(f"{kid}: alinti {pid} icinde birebir yok: {alinti[:70]!r}")
            continue
        if len(yerler) > 1 and not k.get("konum"):
            H.append(f"{kid}: alinti {pid} icinde {len(yerler)} kez geciyor; 'konum' (1..{len(yerler)}) belirtin")
            continue
        sira = int(k.get("konum") or 1)
        if not 1 <= sira <= len(yerler):
            H.append(f"{kid}: konum 1..{len(yerler)} olmali")
            continue
        s = yerler[sira - 1]
        kanit_konum[kid] = (pid, s, s + len(alinti), p["bas"] + s)
        kanit_metin[kid] = alinti
    # iddialar
    iddialar = f.get("iddialar") or []
    if not iddialar:
        H.append("en az bir iddia gerekir: kim, hangi eylem, neyi, kime, hangi kanita dayanarak")
    eylemler = set()
    for i, d in enumerate(iddialar, 1):
        e = d.get("eylem", "")
        if e not in EYLEMLER:
            H.append(f"iddia {i}: eylem gecersiz '{e}' (gecerli: {', '.join(sorted(EYLEMLER))})")
        for alan in ("kim", "neyi"):
            if not str(d.get(alan, "")).strip():
                H.append(f"iddia {i}: '{alan}' bos olamaz")
        dayanak = d.get("kanit") or []
        if not dayanak:
            H.append(f"iddia {i}: en az bir kanit kimligine dayanmali")
        for kid in dayanak:
            if kid not in kanit_konum and kid not in [k.get("id") for k in kanitlar]:
                H.append(f"iddia {i}: kanit kimligi yok: {kid}")
        if e == "kabul" and dayanak and all(RET_RX.search(katla(kanit_metin.get(k, ""))) for k in dayanak):
            H.append(f"iddia {i}: 'kabul' iddiasinin tum kanitlari ret ifadesi iceriyor; ret iceren alinti kabulu destekleyemez")
        if e == "ret" and d.get("ret_aciklamasi"):
            U.append(f"iddia {i}: 'ret' eylemiyle ret_aciklamasi birlikte verilmis; ret davranisin kendisiyse eylem 'uygulama' olabilir")
        if not d.get("belirsiz"):
            eylemler.add(e)
    if iddialar and all(d.get("belirsiz") for d in iddialar) and f.get("tur", "risk_signal") == "risk_signal":
        H.append("tum iddialar belirsiz; bulgu 'tur': 'insufficient_context' olmali (yalniz hipoteze dayanan risk_signal olmaz)")
    baslik_ozet = katla(f"{f.get('baslik', '')} {f.get('ozet', '')}")
    if KABUL_RX.search(baslik_ozet) and "kabul" not in eylemler:
        H.append("baslik/ozet anlasma ya da kabul diyor ama iddialarda kesin 'kabul' yok; basligi iddialarla ayni yone cekin")
    if any(d.get("kosul") for d in iddialar if d.get("eylem") == "kabul") and not KOSUL_RX.search(baslik_ozet):
        H.append("kosullu kabul var; baslik ya da ozet bunu belirtmeli ('kosullu kabul')")
    if any(d.get("aktaran") for d in iddialar) and not AKTARIM_RX.search(baslik_ozet):
        H.append("baskasinin aktardigi olay var; ozet bunu belirtmeli ('…'in aktardigina gore')")
    # hukuki dayanak
    hd = f.get("hukuki_dayanak") or []
    if not hd:
        H.append("en az bir hukuki dayanak gerekir (kaynak kimligi + bolum)")
    for h in hd:
        k = h.get("kaynak", "")
        if k not in kaynak:
            H.append(f"hukuki dayanak kaynagi katalogda yok: {k!r} (uydurma kaynak kabul edilmez; 'kaynak_yonet.py listele')")
        if k == "TR-01":
            m = re.search(r"(\d+)", str(h.get("bolum", "")))
            if not m:
                H.append("TR-01 (4054) icin madde numarasi yazin (bolum: 'm.4')")
            elif "gecici" in katla(str(h.get("bolum", ""))):
                if not 1 <= int(m.group(1)) <= 7:
                    H.append(f"4054 sayili Kanun'da gecici madde {m.group(1)} yok (gecici 1-7)")
            elif not 1 <= int(m.group(1)) <= 65:
                H.append(f"4054 sayili Kanun'da madde {m.group(1)} yok (1-65; resmi metin: mevzuat.gov.tr)")
    # ihbarci, yonlendirme
    metin_hepsi = katla(json.dumps(f, ensure_ascii=False))
    for ad in [x for x in meta(db, "ihbarci").split(",") if x.strip()]:
        if katla(ad.strip()) in metin_hepsi:
            H.append("bulgu kayitli ihbarcinin adini iceriyor; ihbarci kimligi bulguya yazilmaz ('ihbar kaynakli' deyin)")
    hassas = [x for x in (meta(db, "talep_eden") + "," + meta(db, "ust_yonetim")).split(",") if x.strip()]
    kisiler = katla(" ".join(str(d.get("kim", "")) + " " + str(d.get("kime", "")) for d in iddialar) + " " + f.get("ozet", ""))
    if any(katla(x.strip()) in kisiler for x in hassas) and not YONLENDIRME_RX.search(katla(str(f.get("yonlendirme", "")))):
        H.append("bulgu talep eden kisiye/hattina ya da ust yonetime dokunuyor; 'yonlendirme' alanina bagimsiz hat yazin "
                 "(Denetim Komitesi / bagimsiz hukuk musaviri)")
    # sinyal baglama
    bagla, aileler_bulgu = [], {aile(kat)} | {aile(k) for k in f.get("kontroller", []) or []}
    acikca = {s.get("id") for s in f.get("sinyaller") or []}
    for s in db.execute("SELECT * FROM sinyal WHERE durum='acik'"):
        if s["id"] in acikca:
            continue
        for kid, (pid, bs, bn, _) in kanit_konum.items():
            if s["parca"] == pid and s["bas"] < bn and bs < s["son"]:
                if aile(s["kategori"]) in aileler_bulgu:
                    bagla.append((s["id"], f"{kid} ile kesisiyor"))
                else:
                    U.append(f"{s['id']} ({s['kategori']}) kanit {kid} ile kesisiyor ama kategorisi farkli; ayri bulgu acin ya da "
                             f"'sinyaller' alanina gerekceyle baglayin")
                break
    for s in f.get("sinyaller") or []:
        r = db.execute("SELECT * FROM sinyal WHERE id=?", (s.get("id"),)).fetchone()
        if not r:
            H.append(f"baglanmak istenen sinyal yok: {s.get('id')}")
        elif len(str(s.get("gerekce", "")).strip()) < 15:
            H.append(f"{s.get('id')}: baska kategorideki sinyali baglamak gerekce ister (en az 15 karakter)")
        elif r["durum"] != "acik":
            U.append(f"{s.get('id')} zaten '{r['durum']}'")
        else:
            bagla.append((r["id"], s["gerekce"]))
    return H, U, kanit_konum, bagla


def k_bulgu_ekle(a):
    db = baglan(a.vaka)
    f = json_oku(a.json)
    H, U, konum, bagla = bulgu_dogrula(db, f)
    for u in U:
        print("UYARI " + u)
    if H:
        print("Bulgu REDDEDILDI:")
        for h in H:
            print("  - " + h)
        sys.exit(1)
    fid = sonraki_kimlik(db, "bulgu", "F-", 4)
    f["finding_id"] = fid
    f["_konum"] = {k: {"parca": v[0], "bas": v[1], "son": v[2], "belge_ofset": v[3]} for k, v in konum.items()}
    db.execute("INSERT INTO bulgu VALUES (?,?,?)", (fid, json.dumps(f, ensure_ascii=False), simdi()))
    for sid, ger in bagla:
        db.execute("UPDATE sinyal SET durum='bagli', bulgu=?, gerekce=? WHERE id=?", (fid, ger, sid))
    gunluk(db, "bulgu-ekle", f"{fid}: {f.get('baslik', '')[:80]}; {len(bagla)} sinyal baglandi")
    db.commit()
    print(f"{fid} kaydedildi. Baglanan sinyal: {', '.join(s for s, _ in bagla) or '-'}")


def k_bulgu_liste(a):
    db = baglan(a.vaka)
    for r in db.execute("SELECT * FROM bulgu ORDER BY id"):
        f = json.loads(r["veri"])
        if a.kimlik and r["id"] != a.kimlik:
            continue
        print(f"{r['id']}  [{f.get('oncelik')}] {f.get('kategori')}  {f.get('baslik')}")
        if a.kimlik:
            print(json.dumps(f, ensure_ascii=False, indent=2))


def k_sinyal_liste(a):
    db = baglan(a.vaka)
    q = "SELECT * FROM sinyal" + (" WHERE durum=?" if a.durum else "") + " ORDER BY id"
    for s in db.execute(q, (a.durum,) if a.durum else ()):
        ek = f" → {s['bulgu']}" if s["bulgu"] else (f" | {s['gerekce']}" if s["gerekce"] else "")
        print(f"{s['id']}  {s['durum']:6} {s['kategori']:8} {s['parca']}  {s['alinti'][:80]!r}{ek}")


def k_sinyal_kapat(a):
    db = baglan(a.vaka)
    kayit = json_oku(a.json)
    kayit = kayit if isinstance(kayit, list) else [kayit]
    hatalar = []
    for r in kayit:
        s = db.execute("SELECT * FROM sinyal WHERE id=?", (r.get("id"),)).fetchone()
        if not s:
            hatalar.append(f"{r.get('id')}: yok")
        elif s["durum"] != "acik":
            hatalar.append(f"{r.get('id')}: zaten {s['durum']}")
        elif len(str(r.get("gerekce", "")).strip()) < 15:
            hatalar.append(f"{r.get('id')}: kapatma gerekce ister (en az 15 karakter; neden bulgu degil?)")
        else:
            db.execute("UPDATE sinyal SET durum='kapali', gerekce=? WHERE id=?", (r["gerekce"].strip(), s["id"]))
    gunluk(db, "sinyal-kapat", f"{len(kayit) - len(hatalar)} kapandi")
    db.commit()
    for h in hatalar:
        print("RED " + h)
    print(f"Kapatilan: {len(kayit) - len(hatalar)}")
    if hatalar:
        sys.exit(1)


def k_sinyal_ata(a):
    db = baglan(a.vaka)
    for r in (json_oku(a.json) if isinstance(json_oku(a.json), list) else [json_oku(a.json)]):
        db.execute("UPDATE sinyal SET sorumlu=?, hedef_tarih=? WHERE id=? AND durum='acik'", (r.get("sorumlu"), r.get("hedef_tarih"), r.get("id")))
    db.commit()
    print("Atandi (sinyal acik kalir; rapor onu acik listeler).")


# ---------------------------------------------------------------- dogrula, rapor
def dogrulama(db, kaynak_kok=None):
    sonuc = {}
    # 1) kanit
    sorun = []
    for r in db.execute("SELECT * FROM bulgu"):
        f = json.loads(r["veri"])
        for k in f.get("kanitlar", []):
            p = db.execute("SELECT metin FROM parca WHERE id=?", (k.get("parca"),)).fetchone()
            if not p or k.get("alinti", "") not in p["metin"]:
                sorun.append(f"{r['id']}/{k.get('id')}")
    sonuc["kanit"] = (not sorun, f"{len(sorun)} alinti dogrulanamadi: {', '.join(sorun)}" if sorun else "tum alintilar kaynakta birebir")
    # 2) kaynak butunlugu
    if kaynak_kok:
        bozuk, eksik = [], []
        for b in db.execute("SELECT id, kaynak, sha256 FROM belge WHERE ust IS NULL AND kaynak IS NOT NULL"):
            yol = b["kaynak"]
            if not os.path.exists(yol):
                aday = os.path.join(kaynak_kok, os.path.basename(yol))
                yol = aday if os.path.exists(aday) else None
            if not yol:
                eksik.append(b["id"])
            elif sha256_dosya(yol) != b["sha256"]:
                bozuk.append(b["id"])
        sonuc["kaynak_butunlugu"] = (not bozuk and not eksik,
                                     f"degismis: {bozuk or '-'}; bulunamayan: {eksik or '-'}" if (bozuk or eksik) else "tum kaynak dosyalarin ozeti ayni")
    else:
        sonuc["kaynak_butunlugu"] = (False, "kontrol edilmedi (--kaynak-kok verin)")
    g = gostergeler(db)
    sonuc["okuma_kapsami"] = (g["kuyruk_tamam"] and g["kapsam_tam"],
                              f"bekleyen={g['bekleyen']} yeniden={g['yeniden']} okunamayan parca={g['okunamayan_parca']} elle belge={g['elle_belge']}")
    sonuc["sinyal_karari"] = (g["sinyal_tamam"], f"acik sinyal={g['acik_sinyal']}")
    return sonuc


def k_dogrula(a):
    db = baglan(a.vaka)
    s = dogrulama(db, a.kaynak_kok)
    for k, (ok, aciklama) in s.items():
        print(f"{k:18} {'GECTI' if ok else 'GECMEDI'}  {aciklama}")
    gecti = all(ok for ok, _ in s.values())
    print("SONUC: " + ("tum kontroller gecti" if gecti else "en az bir kontrol gecmedi — 'tumu gecti' denmez"))
    gunluk(db, "dogrula", json.dumps({k: v[0] for k, v in s.items()}))
    db.commit()
    sys.exit(0 if gecti else 1)


DEGERLENDIRME = {"etki": "impact", "aciliyet": "urgency", "kanit_yeterliligi": "evidence_sufficiency"}
IDDIA_ALANLARI = ("kim", "eylem", "neyi", "kime", "kanit", "belirsiz", "kosul", "aktaran", "ret_aciklamasi")


def bulgu_semasi(db, fid, f):
    kanit = []
    for k in f.get("kanitlar", []):
        konum = f.get("_konum", {}).get(k["id"], {})
        p = db.execute("SELECT belge FROM parca WHERE id=?", (k["parca"],)).fetchone()
        b = db.execute("SELECT etiket FROM belge WHERE id=?", (p["belge"],)).fetchone() if p else None
        kanit.append({"document_id": k["parca"], "quote": k["alinti"], "start_char": konum.get("bas"), "end_char": konum.get("son"),
                      "location": (b["etiket"] if b else "") + f" (belge ofseti {konum.get('belge_ofset')})",
                      **({"role": "counter"} if k.get("rol") == "karsi" else {}),
                      **({"language": k["dil"]} if k.get("dil") else {}), **({"translation": k["ceviri"]} if k.get("ceviri") else {})})
    return {
        "finding_id": fid, "finding_type": f.get("tur", "risk_signal"), "jurisdictions": f.get("yetki_alani") or ["TR"],
        "control_ids": sorted({f["kategori"]} | set(f.get("kontroller", []))) if "-" in f["kategori"] else f.get("kontroller", []) or [f["kategori"]],
        "summary": f["ozet"], "priority": f["oncelik"], "evidence": kanit,
        "legal_references": [{"source_id": h["kaynak"], "section": h.get("bolum", ""), "version": h.get("surum", "")} for h in f.get("hukuki_dayanak", [])],
        "missing_facts": f["eksik_olgular"], "alternative_explanations": f["masum_aciklamalar"], "human_review_required": True,
        "next_action": f["sonraki_adim"], "versions": {"model": f.get("model", ""), "prompt": "rekabet-ihlali-inceleme", "rules": SURUM, "corpus": meta(db, "ad")},
        "claims": [{k: d[k] for k in IDDIA_ALANLARI if k in d} for d in f.get("iddialar", [])],
        "area": f.get("alan", "rekabet"),
        **({"escalation_route": f["yonlendirme"]} if f.get("yonlendirme") else {}),
        **({"data_screens": f["ihale_uyarilari"]} if f.get("ihale_uyarilari") else {}),
        **({"assessment": {DEGERLENDIRME[k]: v for k, v in f["degerlendirme"].items()}} if f.get("degerlendirme") else {}),
        **({"coded_language": [{"id": r["id"], "phrase": r["ifade"], "hypothesis": r["hipotez"], "basis": r["dayanak"]}
                               for r in (db.execute("SELECT * FROM kod WHERE id=?", (k,)).fetchone() for k in f["kod_hipotezleri"])]}
           if f.get("kod_hipotezleri") else {}),
        "title": f["baslik"],
    }


def k_rapor(a):
    db = baglan(a.vaka)
    g = gostergeler(db)
    s = dogrulama(db, a.kaynak_kok)
    kismi = not all(ok for ok, _ in s.values())
    zaman = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    klasor = os.path.join(a.vaka, "rapor", f"R-{zaman}-{secrets.token_hex(2)}")
    os.makedirs(klasor)
    bulgular = [(r["id"], json.loads(r["veri"])) for r in db.execute("SELECT * FROM bulgu ORDER BY id")]
    sema = [bulgu_semasi(db, fid, f) for fid, f in bulgular]
    json.dump(sema, open(os.path.join(klasor, "bulgular.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    L = []
    if meta(db, "sentetik") == "1":
        L.append("> **SENTETİK VERİ** — bu rapor kurgusal/test verisiyle üretildi.\n")
    if kismi:
        L.append("> **KISMİ RAPOR** — en az bir gösterge ya da doğrulama kontrolü eksik. Aşağıdaki sonuçlar tüm içeriği kapsamaz.\n")
    L.append(f"# Rekabet riski inceleme raporu — {meta(db, 'ad') or os.path.basename(a.vaka)}\n")
    L.append("Bu rapor risk göstergesi içerir; ihlal tespiti değildir. Değerlendirme yetkili hukuk ekibine aittir.\n")
    L.append("## Kapsam ve yetki\n")
    for k, ad in (("yetki", "Yetki"), ("amac", "Amaç"), ("kapsam", "Kapsam"), ("veri_kaynagi", "Veri kaynağı"), ("muhatap", "Raporun muhatabı")):
        if meta(db, k):
            L.append(f"- **{ad}:** {meta(db, k)}")
    L.append(f"- **Kural sürümü:** {SURUM}\n")
    L.append("## Üç gösterge\n")
    L.append("| Gösterge | Durum | Ayrıntı |\n| --- | --- | --- |")
    L.append(f"| 1. Kuyruk | {'Tamam' if g['kuyruk_tamam'] else 'Eksik'} | bekleyen {g['bekleyen']}, yeniden {g['yeniden']}, incelenen {g['incelendi']}/{g['parca_toplam']} |")
    L.append(f"| 2. Okuma kapsamı | {'Tamam' if g['kapsam_tam'] else 'Eksik'} | okunamayan parça {g['okunamayan_parca']}, elle ele alınacak belge {g['elle_belge']}, kapsam dışı parça {g['kapsam_disi_parca']} |")
    L.append(f"| 3. Sinyal kararı | {'Tamam' if g['sinyal_tamam'] else 'Eksik'} | açık sinyal {g['acik_sinyal']} / {g['sinyal_toplam']} |\n")
    L.append("## Doğrulama\n")
    for k, (ok, ac) in s.items():
        L.append(f"- **{k}:** {'geçti' if ok else 'GEÇMEDİ'} — {ac}")
    okunmayan = g["bekleyen"] + g["yeniden"]
    if okunmayan:
        rs = db.execute("SELECT COUNT(*) n, SUM(CASE WHEN p.id IN (SELECT parca FROM sinyal) THEN 1 ELSE 0 END) k "
                        "FROM parca p WHERE p.rastgele=1 AND p.durum='incelendi'").fetchone()
        n, k = rs["n"] or 0, rs["k"] or 0
        if n:
            alt, ust = wilson(k, n)
            L.append(f"\n**Okunmayan içerik tahmini:** {okunmayan} parça okunmadı. Rastgele seçilip okunan {n} parçanın {k}'inde sinyal çıktı "
                     f"(%{100 * k / n:.0f}; %95 güven aralığı %{100 * alt:.0f}–%{100 * ust:.0f}). Okunmayan bölümde benzer oranda sinyal olabilir.")
        else:
            L.append(f"\n**Okunmayan içerik:** {okunmayan} parça okunmadı ve rastgele örneklem okunmadı; okunmayan bölüm hakkında tahmin yapılamaz.")
    L.append("\n## Bulgular\n")
    if not bulgular:
        L.append("Bulgu yok. *Gösterge bulunmaması uygunluk onayı değildir.*")
    for fid, f in bulgular:
        L.append(f"### {fid} — {f['baslik']}\n")
        L.append(f"**Öncelik:** {f['oncelik']} · **Kategori:** {f['kategori']} · **Alan:** {f.get('alan', 'rekabet')}"
                 + (f" · **Yönlendirme:** {f['yonlendirme']}" if f.get("yonlendirme") else "") + "\n")
        L.append(f"{f['ozet']}\n")
        L.append("**İddialar**\n\n| Kim | Eylem | Neyi | Kime | Kanıt | Not |\n| --- | --- | --- | --- | --- | --- |")
        for d in f["iddialar"]:
            notlar = "; ".join(x for x in [("belirsiz" if d.get("belirsiz") else ""), (f"koşul: {d['kosul']}" if d.get("kosul") else ""),
                                           (f"aktaran: {d['aktaran']}" if d.get("aktaran") else ""),
                                           (f"ret: {d['ret_aciklamasi']}" if d.get("ret_aciklamasi") else "")] if x)
            L.append(f"| {d.get('kim', '')} | {d.get('eylem', '')} | {d.get('neyi', '')} | {d.get('kime', '')} | {', '.join(d.get('kanit', []))} | {notlar} |")
        L.append("\n**Kanıtlar**\n")
        for k in f["kanitlar"]:
            L.append(f"- {k['id']} ({k.get('rol', 'destek')}) `{k['parca']}`: «{k['alinti']}»" + (f" — çeviri: {k['ceviri']}" if k.get("ceviri") else ""))
        L.append("\n**Hukuki dayanak:** " + "; ".join(f"{h['kaynak']} {h.get('bolum', '')}".strip() for h in f["hukuki_dayanak"]))
        L.append("\n**Eksik olgular:** " + "; ".join(f["eksik_olgular"]))
        L.append("\n**Masum açıklamalar:** " + "; ".join(f["masum_aciklamalar"]))
        L.append(f"\n**Sonraki adım:** {f['sonraki_adim']}\n")
    acik = db.execute("SELECT * FROM sinyal WHERE durum='acik'").fetchall()
    if acik:
        L.append("## Açık sinyaller (karara bağlanmadı)\n")
        for x in acik:
            L.append(f"- {x['id']} {x['kategori']} `{x['parca']}` «{x['alinti']}»" + (f" — sorumlu {x['sorumlu']}, hedef {x['hedef_tarih']}" if x["sorumlu"] else ""))
    kapali = db.execute("SELECT * FROM sinyal WHERE durum='kapali'").fetchall()
    if kapali:
        L.append("\n## Gerekçeyle kapatılan sinyaller\n")
        for x in kapali:
            L.append(f"- {x['id']} {x['kategori']} «{x['alinti'][:100]}» — {x['gerekce']}")
    kodlar = db.execute("SELECT * FROM kod").fetchall()
    if kodlar:
        L.append("\n## Örtülü dil hipotezleri (olgu değil)\n")
        for k in kodlar:
            L.append(f"- {k['id']} «{k['ifade']}» → {k['hipotez']} (dayanak: {k['dayanak']})")
    L.append("\n## Okunamayan, kapsam dışı ve ayrılan içerik\n")
    for b in db.execute("SELECT id, etiket, durum, neden FROM belge WHERE durum IN ('okunamadi','ayrildi','icerik_yok','cozuldu')"):
        L.append(f"- {b['id']} [{b['durum']}] {b['etiket']} — {b['neden']}")
    for p in db.execute("SELECT p.id, p.durum, i.notu FROM parca p LEFT JOIN isaret i ON i.parca=p.id WHERE p.durum IN ('okunamadi','kapsam_disi')"):
        L.append(f"- {p['id']} [{p['durum']}] — {p['notu']}")
    open(os.path.join(klasor, "rapor.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    with open(os.path.join(klasor, "kapsama.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["parca", "belge", "etiket", "durum", "gosterim", "karar", "not"])
        for r in db.execute("SELECT p.id, p.belge, b.etiket, p.durum, p.gosterim, i.karar, i.notu FROM parca p JOIN belge b ON b.id=p.belge "
                            "LEFT JOIN isaret i ON i.no=(SELECT MAX(no) FROM isaret WHERE parca=p.id) ORDER BY p.id"):
            w.writerow(list(r))
    gunluk(db, "rapor", klasor)
    db.commit()
    print(f"Rapor: {klasor}" + ("  [KISMI]" if kismi else ""))
    print(f"Bulgu: {len(bulgular)}  " + "  ".join(f"{k}={'gecti' if v[0] else 'GECMEDI'}" for k, v in s.items()))


def k_belge_coz(a):
    """Elle ele alinacak (okunamayan) belgeyi kapatir: elle hazirlanmis dokumu okunacak parca olarak ekler
    ya da gerekceyle 'icerik yok' der. Iki durumda da rapor bunu ayrica listeler."""
    db = baglan(a.vaka)
    b = db.execute("SELECT * FROM belge WHERE id=?", (a.kimlik,)).fetchone()
    if not b or b["durum"] != "okunamadi":
        hata(f"{a.kimlik} elle ele alinacak (okunamadi) bir belge degil")
    if len((a.aciklama or "").strip()) < 15:
        hata("--aciklama zorunlu: kim, nasil inceledi (en az 15 karakter)")
    if a.icerik_yok:
        db.execute("UPDATE belge SET durum='icerik_yok', neden=? WHERE id=?", (f"{b['neden']} | elle: {a.aciklama}", a.kimlik))
        print(f"{a.kimlik}: icerik yok olarak kapatildi (raporda listelenir)")
    else:
        if not a.dokum or not os.path.isfile(a.dokum):
            hata("--dokum <metin dosyasi> ya da --icerik-yok verin")
        metin = open(a.dokum, encoding="utf-8", errors="replace").read()
        if not metin.strip():
            hata("dokum bos")
        cid = sonraki_kimlik(db, "belge", "B", 4)
        db.execute("INSERT INTO belge (id, ust, etiket, sha256, boyut, yontem, durum, neden, karakter) VALUES (?,?,?,?,?,?,?,?,?)",
                   (cid, a.kimlik, f"{b['etiket']}#elle-dokum", hashlib.sha256(metin.encode()).hexdigest(), len(metin), "elle dokum",
                    "islendi", a.aciklama, len(metin)))
        araliklar = parcala(metin)
        for i, (s, e) in enumerate(araliklar, 1):
            db.execute("INSERT INTO parca (id, belge, sira, toplam, bas, son, metin) VALUES (?,?,?,?,?,?,?)",
                       (f"{cid}-P{i:03d}", cid, i, len(araliklar), s, e, metin[s:e]))
        db.execute("UPDATE belge SET durum='cozuldu', neden=? WHERE id=?", (f"{b['neden']} | elle dokum: {cid}", a.kimlik))
        print(f"{a.kimlik}: dokum {cid} olarak eklendi ({len(araliklar)} parca okunmayi bekliyor)")
    gunluk(db, "belge-coz", f"{a.kimlik}: {a.aciklama}")
    db.commit()


def k_gunluk(a):
    db = baglan(a.vaka)
    for r in db.execute("SELECT * FROM gunluk ORDER BY no"):
        print(f"{r['zaman']}  {r['komut']:14} {r['ayrinti']}")


def k_doktor(a):
    import okuyucular as O
    print(O.doktor())


# ---------------------------------------------------------------- arayuz
def main(argv=None):
    ap = argparse.ArgumentParser(description="Rekabet incelemesi vaka defteri (okuma kaniti, sinyal ve bulgu dogrulamasi)")
    alt = ap.add_subparsers(dest="komut", required=True)

    def ekle(ad, fn, vaka=True):
        p = alt.add_parser(ad)
        if vaka:
            p.add_argument("vaka")
        p.set_defaults(fn=fn)
        return p

    p = ekle("ac", k_ac)
    for x in ("--ad", "--yetki", "--amac", "--kapsam", "--talep-eden", "--ust-yonetim", "--muhatap", "--veri-kaynagi",
              "--avukat-alan", "--haric", "--ihbarci"):
        p.add_argument(x)
    p.add_argument("--sentetik", action="store_true", help="yalniz kurgusal/test verisi; rapor damgalanir")
    p = ekle("yukle", k_yukle)
    p.add_argument("yollar", nargs="+")
    p = ekle("sonraki", k_sonraki)
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--yeniden", action="store_true")
    p.add_argument("--rastgele", action="store_true")
    p.add_argument("--isci")
    p = ekle("goster", k_goster)
    p.add_argument("kimlik")
    p = ekle("isaretle", k_isaretle)
    p.add_argument("--json", required=True)
    ekle("durum", k_durum)
    p = ekle("ara", k_ara)
    p.add_argument("ifade")
    p.add_argument("--duzenli", action="store_true")
    p.add_argument("--yeniden-ac", action="store_true")
    p = ekle("kod-ekle", k_kod_ekle)
    for x in ("--ifade", "--hipotez", "--dayanak"):
        p.add_argument(x, required=True)
    p.add_argument("--parca")
    ekle("hafiza", k_hafiza)
    ekle("capraz", k_capraz)
    p = ekle("baglam", k_baglam)
    p.add_argument("kimlik")
    p = ekle("bulgu-ekle", k_bulgu_ekle)
    p.add_argument("--json", required=True)
    p = ekle("bulgu-liste", k_bulgu_liste)
    p.add_argument("kimlik", nargs="?")
    p = ekle("sinyal-liste", k_sinyal_liste)
    p.add_argument("--durum", choices=["acik", "bagli", "kapali"])
    p = ekle("sinyal-kapat", k_sinyal_kapat)
    p.add_argument("--json", required=True)
    p = ekle("sinyal-ata", k_sinyal_ata)
    p.add_argument("--json", required=True)
    p = ekle("dogrula", k_dogrula)
    p.add_argument("--kaynak-kok")
    p = ekle("rapor", k_rapor)
    p.add_argument("--kaynak-kok")
    p = ekle("belge-coz", k_belge_coz)
    p.add_argument("kimlik")
    p.add_argument("--aciklama", required=True)
    p.add_argument("--dokum")
    p.add_argument("--icerik-yok", action="store_true")
    ekle("gunluk", k_gunluk)
    ekle("doktor", k_doktor, vaka=False)
    a = ap.parse_args(argv)
    for k in list(vars(a)):
        if "-" in k:
            setattr(a, k.replace("-", "_"), getattr(a, k))
    a.fn(a)


if __name__ == "__main__":
    main()
```
