#!/usr/bin/env python3
"""Vaka defteri ve okuyucu testleri: python3 tests/test_vaka.py

Her kural ihlal edilmeye calisilarak sinanir: yanlis olani dene, reddedildigini gor.
Dis araclar (tesseract, readpst, pdftoppm) yoksa ilgili testler ATLANDI olarak gecer; CI bunlari kurar."""
import email.message, email.policy, json, os, re, shutil, subprocess, sys, tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(KOK, "plugins", "rekabet-ihlali-inceleme", "skills", "rekabet-ihlali-inceleme", "scripts")
VERI = os.path.join(KOK, "tests", "veri")
sys.path.insert(0, SCRIPTS)
import okuyucular as O  # noqa: E402

basarisiz, atlanan = [], []


def test(ad):
    def sar(f):
        try:
            sonuc = f()
            if sonuc == "ATLA":
                atlanan.append(ad); print(f"ATLANDI {ad}")
            else:
                print(f"GECTI   {ad}")
        except AssertionError as e:
            basarisiz.append(ad); print(f"KALDI   {ad}: {e}")
        except Exception as e:  # beklenmeyen hata da kalir
            basarisiz.append(ad); print(f"KALDI   {ad}: {type(e).__name__}: {e}")
        return f
    return sar


TMP = tempfile.mkdtemp(prefix="vaka_test_")
VK = os.path.join(TMP, "vk")
DATA = os.path.join(TMP, "veri")


def vaka(*argv, beklenen=0):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "vaka.py"), *argv], capture_output=True, text=True, cwd=TMP)
    assert r.returncode == beklenen, f"{argv[0]} cikis {r.returncode} (beklenen {beklenen}): {r.stdout[-600:]} {r.stderr[-600:]}"
    return r.stdout + r.stderr


def jyaz(ad, veri):
    p = os.path.join(TMP, ad)
    json.dump(veri, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def kodlar(cikti):
    return {m.group(1): re.search(r"\[\[ONAY: (\w+)\]\]", cikti[m.end():]).group(1) for m in re.finditer(r"===== (\S+)", cikti)}


def eml(p, frm, to, subj, date, body, ek=None):
    m = email.message.EmailMessage(policy=email.policy.default)
    m["From"], m["To"], m["Subject"], m["Date"] = frm, to, subj, date
    m.set_content(body)
    if ek:
        m.add_attachment(ek[1], subtype="plain", filename=ek[0])
    open(p, "wb").write(m.as_bytes())


def veri_kur():
    os.makedirs(os.path.join(DATA, "ozel"))
    eml(f"{DATA}/01.eml", "satis@ornek.example", "mudur@rakip.example", "Nisan", "Mon, 10 Mar 2025 10:00:00 +0300",
        "Dünkü görüşmede konuştuğumuz gibi Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz. Bu konuyu maile fazla yazmayalım.\n")
    eml(f"{DATA}/02.eml", "mudur@rakip.example", "satis@ornek.example", "Re: Nisan", "Tue, 11 Mar 2025 09:00:00 +0300",
        "Teklifinizi değerlendirdik, kabul etmiyoruz. Fiyatlarımızı bağımsız belirleyeceğiz.\n")
    eml(f"{DATA}/03.eml", "avukat@buro.av.tr", "hukuk@ornek.example", "Görüş", "Wed, 12 Mar 2025 09:00:00 +0300",
        "Değerlendirmemiz ektedir.\n", ek=("gorus.txt", "Rakip ile fiyat görüşmesi risklidir."))
    eml(f"{DATA}/04.eml", "bolge@ornek.example", "satis@ornek.example", "Bahçe", "Thu, 13 Mar 2025 09:00:00 +0300",
        "Bahçe işi bu ay sizde, biz yanaşmıyoruz. Her zamanki gibi.\n")
    eml(f"{DATA}/05.eml", "x@ornek.example", "y@ornek.example", "Hukuk görüşü", "Fri, 14 Mar 2025 09:00:00 +0300",
        "AVUKAT-MÜVEKKİL GİZLİLİĞİ. Rakip ile yapılan görüşmeye ilişkin değerlendirme.\n")
    open(f"{DATA}/ozel/kisisel.txt", "w").write("Rakip ile fiyat konusu kişisel not.")
    open(f"{DATA}/bozuk.pdf", "wb").write(b"%PDF-1.4 bozuk")
    open(f"{DATA}/uzun.txt", "w").write("\n\n".join(f"Paragraf {i}: ihale hazırlıkları ve birim fiyat çalışmaları sürüyor. " * 8 for i in range(12)))


veri_kur()


@test("yetki kapisi: yetki/amac/kapsam olmadan vaka acilmaz ve yukleme calismaz")
def _():
    out = vaka("ac", VK + "_kapi", "--ad", "x", beklenen=4)
    assert "yetki kapisi" in out
    assert not os.path.exists(os.path.join(VK + "_kapi", "vaka.db")), "kapi reddinde vaka dosyasi olusmamali"
    vaka("yukle", VK + "_kapi", DATA, beklenen=2)
    os.makedirs(VK + "_bos")
    import sqlite3
    sqlite3.connect(os.path.join(VK + "_bos", "vaka.db")).close()  # elle olusturulmus bos dosya kapiyi asamaz
    assert "acilisi tamamlanmamis" in vaka("yukle", VK + "_bos", DATA, beklenen=4)


@test("yukleme: kisitli icerik metne cevrilmeden ayrilir, ekleri de ayrilir; bozuk dosya elle ele alinacaklara duser")
def _():
    vaka("ac", VK, "--ad", "Test", "--yetki", "Hukuk HK-1", "--amac", "uyum incelemesi", "--kapsam", "satis 2025",
         "--avukat-alan", "buro.av.tr", "--haric", "ozel/*", "--ihbarci", "Ayşe K.", "--talep-eden", "Satış GMY")
    s = json.loads(vaka("yukle", VK, DATA).strip().splitlines()[-1])
    assert s["ayrildi"] == 4, s       # avukat e-postasi + eki, gizlilik ibareli e-posta, haric klasor
    assert s["okunamadi"] == 1, s     # bozuk.pdf
    d = vaka("durum", VK)
    assert "avukat alan adi: buro.av.tr" in d and "kapsam disi desen" in d and "avukat-muvekkil gizliligi ibaresi" in d
    import sqlite3
    db = sqlite3.connect(os.path.join(VK, "vaka.db"))
    assert db.execute("SELECT COUNT(*) FROM parca p JOIN belge b ON b.id=p.belge WHERE b.durum='ayrildi'").fetchone()[0] == 0, \
        "ayrilan belgenin parcasi olmamali"
    tekrar = json.loads(vaka("yukle", VK, DATA).strip().splitlines()[-1])
    assert tekrar["atlandi"] == 8 and tekrar["belge"] == 0, f"ayni dosyalar ikinci kez yuklenmemeli: {tekrar}"


K = {}


@test("okuma: onay kodu olmadan, yanlis kodla, alintisi parcada olmayan ya da gerekcesiz isaret reddedilir")
def _():
    K.update(kodlar(vaka("sonraki", VK, "--n", "20")))
    assert len(K) == 6, K
    out = vaka("isaretle", VK, "--json", jyaz("k.json", [
        {"parca": "B0001-P001", "onay": "YANLIS", "karar": "temiz"},
        {"parca": "B0002-P001", "onay": K["B0002-P001"], "karar": "sinyal", "sinyaller": [{"kategori": "FYT", "alinti": "olmayan cumle"}]},
        {"parca": "B0009-P001", "onay": K["B0009-P001"], "karar": "okunamadi"},
        {"parca": "B0009-P002", "onay": K["B0009-P002"], "karar": "sinyal", "sinyaller": [{"kategori": "XYZ", "alinti": "Paragraf"}]},
        {"parca": "B0005-P001", "onay": K["B0005-P001"], "karar": "temiz", "sinyaller": [{"kategori": "PZR", "alinti": "Bahçe"}]},
    ]), beklenen=1)
    for parca in ("onay kodu tutmuyor", "birebir yok", "gerekce ister", "gecersiz kategori", "karar 'sinyal' olmali"):
        assert parca in out, f"'{parca}' reddi yok: {out}"
    assert "Islenen: 0" in out


@test("okuma: dogru kodla isaretlenen parca kapanir; yeniden gostermek eski kodu gecersiz kilar")
def _():
    eski = K["B0009-P003"]
    K.update(kodlar(vaka("goster", VK, "B0009-P003")))
    assert K["B0009-P003"] != eski
    vaka("isaretle", VK, "--json", jyaz("e.json", [{"parca": "B0009-P003", "onay": eski, "karar": "temiz"}]), beklenen=1)
    vaka("isaretle", VK, "--json", jyaz("i.json", [
        {"parca": "B0001-P001", "onay": K["B0001-P001"], "karar": "sinyal", "sinyaller": [
            {"kategori": "FYT", "alinti": "Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz"},
            {"kategori": "DL", "alinti": "Bu konuyu maile fazla yazmayalım"}]},
        {"parca": "B0002-P001", "onay": K["B0002-P001"], "karar": "sinyal", "sinyaller": [{"kategori": "FYT", "alinti": "Teklifinizi değerlendirdik, kabul etmiyoruz"}]},
        {"parca": "B0005-P001", "onay": K["B0005-P001"], "karar": "sinyal", "sinyaller": [{"kategori": "PZR", "alinti": "Bahçe işi bu ay sizde, biz yanaşmıyoruz"}]},
        {"parca": "B0009-P001", "onay": K["B0009-P001"], "karar": "temiz"},
        {"parca": "B0009-P002", "onay": K["B0009-P002"], "karar": "temiz"},
    ]))
    d = vaka("durum", VK)
    assert "bekleyen=1" in d and "acik sinyal=4" in d, d


@test("gostergeler ayri: kuyruk eksikken kapsam ve rapor da eksik; rapor KISMI damgasi tasir")
def _():
    d = vaka("durum", VK)
    assert "1) Kuyruk          : EKSIK" in d and "2) Okuma kapsami   : EKSIK" in d and "3) Sinyal karari   : EKSIK" in d
    out = vaka("rapor", VK)
    yol = re.search(r"Rapor: (\S+)", out).group(1)
    rapor = open(os.path.join(TMP, yol, "rapor.md"), encoding="utf-8").read()
    assert "KISMİ RAPOR" in rapor and "Açık sinyaller" in rapor
    vaka("dogrula", VK, beklenen=1)


@test("rastgele orneklem: kismi raporda okunmayan icerik tahmini guven araligiyla yazilir")
def _():
    out = vaka("sonraki", VK, "--rastgele", "--n", "1")
    pid, kod = next(iter(kodlar(out).items()))
    vaka("isaretle", VK, "--json", jyaz("r.json", [{"parca": pid, "onay": kod, "karar": "temiz"}]))
    yol = re.search(r"Rapor: (\S+)", vaka("rapor", VK)).group(1)
    rapor = open(os.path.join(TMP, yol, "rapor.md"), encoding="utf-8").read()
    assert "KISMİ RAPOR" in rapor
    assert pid == "B0009-P003"


@test("bulgu: ret iceren alintiyla kabul, okunmamis parca, uydurma kaynak, olmayan madde, ihbarci adi, bagimsiz hat eksigi reddedilir")
def _():
    out = vaka("bulgu-ekle", VK, "--json", jyaz("bk.json", {
        "baslik": "Satış ile rakip Nisan zammında anlaştılar", "ozet": "Ayşe K.'nın ihbarına göre Satış GMY ekibi rakiple anlaştı.",
        "kategori": "FYT", "oncelik": "Yüksek", "kontroller": ["FYT-01", "FYT-99"],
        "kanitlar": [{"id": "K1", "parca": "B0002-P001", "alinti": "Teklifinizi değerlendirdik, kabul etmiyoruz"},
                     {"id": "K2", "parca": "B0004-P001", "alinti": "x"}],
        "iddialar": [{"kim": "Rakip", "eylem": "kabul", "neyi": "zam", "kime": "Satış", "kanit": ["K1"]},
                     {"kim": "Rakip", "eylem": "anlasti", "neyi": "zam", "kanit": ["K1"]}],
        "hukuki_dayanak": [{"kaynak": "TR-99", "bolum": "m.4"}, {"kaynak": "TR-01", "bolum": "m.99"}],
        "eksik_olgular": [], "masum_aciklamalar": ["maliyet"], "sonraki_adim": "hukuka ilet"}), beklenen=1)
    for parca in ("ret iceren alinti kabulu destekleyemez", "kaynagi katalogda yok", "madde 99 yok", "ihbarcinin adini",
                  "yonlendirme", "eylem gecersiz", "eksik_olgular", "kontrol kimligi katalogda yok: FYT-99", "parca kimligi yok"):
        assert parca in out, f"'{parca}' reddi yok:\n{out}"


@test("bulgu: baslik iddialardan farkli yonde olamaz; kosullu kabul ve aktarim basliga/ozete yazilmali")
def _():
    temel = {"kategori": "FYT", "oncelik": "Orta", "kontroller": ["FYT-01"],
             "kanitlar": [{"id": "K1", "parca": "B0001-P001", "alinti": "Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz"}],
             "hukuki_dayanak": [{"kaynak": "TR-01", "bolum": "m.4"}], "eksik_olgular": ["uygulama"], "masum_aciklamalar": ["maliyet"],
             "sonraki_adim": "incele"}
    out = vaka("bulgu-ekle", VK, "--json", jyaz("y1.json", {**temel, "baslik": "Taraflar zamda anlaştı", "ozet": "Teklif yapıldı.",
              "iddialar": [{"kim": "Satış", "eylem": "teklif", "neyi": "zam", "kime": "Rakip", "kanit": ["K1"]}]}), beklenen=1)
    assert "basligi iddialarla ayni yone" in out, out
    out = vaka("bulgu-ekle", VK, "--json", jyaz("y2.json", {**temel, "baslik": "Rakip zammı kabul etti", "ozet": "Kabul var.",
              "iddialar": [{"kim": "Rakip", "eylem": "kabul", "neyi": "zam", "kime": "Satış", "kanit": ["K1"], "kosul": "hammadde artarsa",
                            "aktaran": "bölge müdürü"}]}), beklenen=1)
    assert "kosullu kabul var" in out and "baskasinin aktardigi" in out, out
    out = vaka("bulgu-ekle", VK, "--json", jyaz("y3.json", {**temel, "baslik": "Ortak zam teklifi", "ozet": "Teklif yapıldı.",
              "kanitlar": [{"id": "K1", "parca": "B0009-P001", "alinti": "Paragraf"}],
              "iddialar": [{"kim": "Satış", "eylem": "teklif", "neyi": "zam", "kime": "Rakip", "kanit": ["K1"]}]}), beklenen=1)
    assert "kez geciyor; 'konum'" in out, out


@test("bulgu: kurala uyan bulgu kaydolur; ayni kategorideki kesisen sinyaller baglanir, farkli kategori acik kalir")
def _():
    out = vaka("bulgu-ekle", VK, "--json", jyaz("iyi.json", {
        "baslik": "Rakibe ortak fiyat artışı teklif edildi; rakip reddetti",
        "ozet": "Satış çalışanı rakibe Nisan için ortak %12 zam önerdi; rakip ertesi gün reddetti.",
        "kategori": "FYT", "oncelik": "Yüksek", "kontroller": ["FYT-01"],
        "kanitlar": [{"id": "K1", "parca": "B0001-P001", "alinti": "Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz"},
                     {"id": "K2", "parca": "B0002-P001", "alinti": "Teklifinizi değerlendirdik, kabul etmiyoruz"},
                     {"id": "K3", "parca": "B0001-P001", "alinti": "Dünkü görüşmede konuştuğumuz gibi Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz. Bu konuyu maile"}],
        "iddialar": [{"kim": "satis@ornek.example", "eylem": "teklif", "neyi": "ortak %12 zam", "kime": "mudur@rakip.example", "kanit": ["K1"]},
                     {"kim": "mudur@rakip.example", "eylem": "ret", "neyi": "ortak zam teklifi", "kime": "satis@ornek.example", "kanit": ["K2"]}],
        "hukuki_dayanak": [{"kaynak": "TR-01", "bolum": "m.4"}, {"kaynak": "TR-01", "bolum": "geçici m.3"}],
        "eksik_olgular": ["Zammın uygulanıp uygulanmadığı"], "masum_aciklamalar": ["Bağımsız maliyet artışı"],
        "sonraki_adim": "Hukuka ilet"}))
    assert "F-0001 kaydedildi" in out, out
    assert "S-0002 (DL) kanit K3 ile kesisiyor ama kategorisi farkli" in out, "genis alinti baska kategorideki sinyali kapatmamali"
    liste = vaka("sinyal-liste", VK)
    assert re.search(r"S-0001\s+bagli", liste) and re.search(r"S-0003\s+bagli", liste) and re.search(r"S-0002\s+acik", liste), liste


@test("ortulu dil: kod hipotezi gerekce ister; kayit geri tarama yapar ve incelenmis parcayi yeniden acar")
def _():
    vaka("kod-ekle", VK, "--ifade", "bahçe", "--hipotez", "ihale", "--dayanak", "kisa", beklenen=2)
    out = vaka("kod-ekle", VK, "--ifade", "BAHÇE İŞİ", "--hipotez", "ihale ya da proje paketi",
               "--dayanak", "satış iletisinde bahçe işi yok; paylaşım dili var", "--parca", "B0005-P001")
    assert "1 incelenmis parca yeniden okunmak uzere acildi" in out, out
    d = vaka("durum", VK)
    assert "yeniden=1" in d and "1) Kuyruk          : EKSIK" in d
    yeniden = vaka("sonraki", VK, "--yeniden")
    assert "YENIDEN: kod hipotezi K-001" in yeniden
    K.update(kodlar(yeniden))
    vaka("isaretle", VK, "--json", jyaz("y.json", [{"parca": "B0005-P001", "onay": K["B0005-P001"], "karar": "temiz", "not": "hipotezle okundu"}]))
    assert "K-001" in vaka("hafiza", VK)


@test("ortulu dile dayanan bulgu: yalniz belirsiz iddiayla risk_signal olmaz; insufficient_context olarak kod hipoteziyle kaydolur")
def _():
    temel = {"baslik": "Bölge yazışmasında paylaşım dili (örtülü ifade)", "kategori": "PZR", "oncelik": "Orta", "kontroller": ["PZR-03"],
             "ozet": "'Bahçe işi' ifadesi ihale paketi anlamına geliyorsa bu ay işin rakibe bırakıldığı yazılıyor; anlam doğrulanmadı.",
             "kanitlar": [{"id": "K1", "parca": "B0005-P001", "alinti": "Bahçe işi bu ay sizde, biz yanaşmıyoruz"}],
             "iddialar": [{"kim": "bolge@ornek.example", "eylem": "teklif", "neyi": "işi karşı tarafa bırakma", "kime": "satis@ornek.example",
                           "kanit": ["K1"], "belirsiz": True}],
             "hukuki_dayanak": [{"kaynak": "TR-01", "bolum": "m.4"}], "eksik_olgular": ["'Bahçe işi' ifadesinin karşılığı olan ihale"],
             "masum_aciklamalar": ["Gerçek bir peyzaj işinin iş bölümü"], "sonraki_adim": "İlgili ayın ihale kayıtlarıyla eşleştir"}
    out = vaka("bulgu-ekle", VK, "--json", jyaz("o1.json", temel), beklenen=1)
    assert "tum iddialar belirsiz" in out, out
    out = vaka("bulgu-ekle", VK, "--json", jyaz("o2.json", {**temel, "tur": "insufficient_context", "kod_hipotezleri": ["K-999"]}), beklenen=1)
    assert "kod hipotezi yok: K-999" in out, out
    out = vaka("bulgu-ekle", VK, "--json", jyaz("o3.json", {**temel, "tur": "insufficient_context", "kod_hipotezleri": ["K-001"],
                                                          "degerlendirme": {"etki": "Orta", "aciliyet": "cok"}}), beklenen=1)
    assert "degerlendirme:" in out, out
    out = vaka("bulgu-ekle", VK, "--json", jyaz("o4.json", {**temel, "tur": "insufficient_context", "kod_hipotezleri": ["K-001"],
                                                          "degerlendirme": {"etki": "Orta", "aciliyet": "Düşük", "kanit_yeterliligi": "Düşük"}}))
    assert "F-0002 kaydedildi" in out and "S-0004" in out, out


@test("sinyal kapatma gerekce ister; elle ele alinacak belge gerekceyle cozulur; tum kontroller gecince rapor tam")
def _():
    vaka("sinyal-kapat", VK, "--json", jyaz("s1.json", [{"id": "S-0002", "gerekce": "kisa"}]), beklenen=1)
    vaka("sinyal-kapat", VK, "--json", jyaz("s2.json", [{"id": "S-0002", "gerekce": "Gizleme ifadesi F-0001 bulgusunun parcasi; ayri risk degil"}]))
    vaka("belge-coz", VK, "B0001", "--icerik-yok", "--aciklama", "okunmus bir belge, cozulemez", beklenen=2)
    vaka("belge-coz", VK, "B0007", "--icerik-yok", "--aciklama", "kisa", beklenen=2)
    vaka("belge-coz", VK, "B0007", "--icerik-yok", "--aciklama", "PDF bozuk; ozgun dosya yeniden istendi")
    out = vaka("dogrula", VK, "--kaynak-kok", DATA)
    assert "SONUC: tum kontroller gecti" in out, out
    yol = re.search(r"Rapor: (\S+)", vaka("rapor", VK, "--kaynak-kok", DATA)).group(1)
    rapor = open(os.path.join(TMP, yol, "rapor.md"), encoding="utf-8").read()
    assert "KISMİ" not in rapor and "F-0001" in rapor and "Örtülü dil hipotezleri" in rapor
    b = json.load(open(os.path.join(TMP, yol, "bulgular.json"), encoding="utf-8"))
    assert b[0]["claims"][1]["eylem"] == "ret" and b[0]["evidence"][0]["quote"].startswith("Nisan")
    assert b[1]["finding_type"] == "insufficient_context" and b[1]["coded_language"][0]["phrase"] == "BAHÇE İŞİ"
    assert b[1]["assessment"] == {"impact": "Orta", "urgency": "Düşük", "evidence_sufficiency": "Düşük"}
    try:
        import jsonschema
    except ImportError:
        print("  (jsonschema yok; sema dogrulamasi atlandi)")
        return
    sema = json.load(open(os.path.join(SCRIPTS, "..", "references", "bulgu_semasi.json"), encoding="utf-8"))
    for bulgu in b:
        jsonschema.validate(bulgu, sema)


@test("kaynak butunlugu: kaynak dosya sonradan degisirse dogrulama gecmez")
def _():
    with open(f"{DATA}/uzun.txt", "a") as f:
        f.write("ek satir")
    out = vaka("dogrula", VK, "--kaynak-kok", DATA, beklenen=1)
    assert "kaynak_butunlugu   GECMEDI" in out, out


@test("sentetik vaka: kapi aranmaz, rapor SENTETIK damgasi tasir")
def _():
    sv = os.path.join(TMP, "sv")
    vaka("ac", sv, "--sentetik")
    vaka("yukle", sv, os.path.join(DATA, "02.eml"))
    yol = re.search(r"Rapor: (\S+)", vaka("rapor", sv)).group(1)
    assert "SENTETİK VERİ" in open(os.path.join(TMP, yol, "rapor.md"), encoding="utf-8").read()


def _calis(komut, ortam, beklenen):
    r = subprocess.run(komut, capture_output=True, text=True, cwd=TMP, env=ortam)
    assert r.returncode == beklenen, f"{komut[2]} cikis {r.returncode}: {r.stdout[-400:]} {r.stderr[-400:]}"
    return r.stdout + r.stderr


@test("Claude dizini surumu: .md'den yazilan betikler JSON katalogla calisir (REKABET_REF)")
def _():
    sys.path.insert(0, os.path.join(KOK, "tools"))
    import dizin_surumu as DZ
    hedef = os.path.join(TMP, "dizin")
    DZ.uret(hedef)
    skill = os.path.join(hedef, "skills", "rekabet-ihlali-inceleme")
    assert not [f for f in os.listdir(os.path.join(skill, "scripts")) if f.endswith(".py")], "dizin surumunde .py olmamali"
    calisma = os.path.join(TMP, "dizin_calisma"); os.makedirs(calisma)
    blok = lambda metin, bas: re.search(r"```python\n(" + bas + r".*?)```", metin, re.S).group(1)
    open(os.path.join(calisma, "rekabet_tarama.py"), "w", encoding="utf-8").write(
        blok(open(os.path.join(skill, "SKILL.md"), encoding="utf-8").read(), '"""Rekabet riski'))
    for ad in ("vaka", "okuyucular", "ihale_analiz"):
        md = open(os.path.join(skill, "scripts", ad + ".md"), encoding="utf-8").read()
        open(os.path.join(calisma, ad + ".py"), "w", encoding="utf-8").write(blok(md, ""))
    ortam = {**os.environ, "REKABET_REF": os.path.join(skill, "references")}
    calis = lambda *a, beklenen=0: _calis([sys.executable, os.path.join(calisma, "vaka.py"), *a], ortam, beklenen)
    dv = os.path.join(TMP, "dizin_vaka")
    calis("ac", dv, "--sentetik")
    calis("yukle", dv, os.path.join(DATA, "02.eml"))
    k = kodlar(calis("sonraki", dv))
    calis("isaretle", dv, "--json", jyaz("dz_i.json", [{"parca": "B0001-P001", "onay": k["B0001-P001"], "karar": "sinyal",
          "sinyaller": [{"kategori": "FYT", "alinti": "kabul etmiyoruz"}]}]))
    bulgu = {"baslik": "Rakip ortak zam teklifini reddetti", "ozet": "Ret cevabı.", "kategori": "FYT", "oncelik": "Düşük",
             "kontroller": ["FYT-01"], "kanitlar": [{"id": "K1", "parca": "B0001-P001", "alinti": "kabul etmiyoruz"}],
             "iddialar": [{"kim": "Rakip", "eylem": "ret", "neyi": "ortak zam", "kanit": ["K1"]}],
             "hukuki_dayanak": [{"kaynak": "TR-99", "bolum": "m.4"}], "eksik_olgular": ["teklif"], "masum_aciklamalar": ["yok"],
             "sonraki_adim": "incele"}
    assert "katalogda yok: 'TR-99'" in calis("bulgu-ekle", dv, "--json", jyaz("dz1.json", bulgu), beklenen=1)
    bulgu["hukuki_dayanak"] = [{"kaynak": "TR-01", "bolum": "m.4"}]
    assert "F-0001 kaydedildi" in calis("bulgu-ekle", dv, "--json", jyaz("dz2.json", bulgu))
    r = subprocess.run([sys.executable, os.path.join(calisma, "ihale_analiz.py"), os.path.join(KOK, "tests", "veri", "ihale_ornek.csv"),
                        "--cikti", os.path.join(TMP, "dz_u.csv"), "--cv-cikti", os.path.join(TMP, "dz_cv.csv")], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["uyari"] > 0, r.stderr


# ---------------------------------------------------------------- okuyucular
@test("okuyucu: arsiv (zip, tar.gz) acilir; zip-slip yolu disari yazilamaz")
def _():
    import io, tarfile, zipfile
    z = os.path.join(TMP, "a.zip")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("klasor/not.txt", "Rakip ile teklif konuşuldu.")
        f.writestr("../../disari.txt", "kotu")
    d = O.oku(z)
    metinler = [c["metin"] for _, c in O.duzlestir(d)]
    assert any("Rakip ile teklif" in m for m in metinler)
    assert not os.path.exists(os.path.join(os.path.dirname(TMP), "disari.txt"))
    t = os.path.join(TMP, "a.tar.gz")
    with tarfile.open(t, "w:gz") as f:
        veri = "Tar icindeki belge".encode()
        bilgi = tarfile.TarInfo("x/belge.txt"); bilgi.size = len(veri)
        f.addfile(bilgi, io.BytesIO(veri))
    assert any("Tar icindeki" in c["metin"] for _, c in O.duzlestir(O.oku(t)))


@test("okuyucu: OpenDocument ve RTF (Turkce ve Kiril)")
def _():
    import zipfile
    odt = os.path.join(TMP, "b.odt")
    with zipfile.ZipFile(odt, "w") as f:
        f.writestr("content.xml", '<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                   'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:p>Bölge paylaşımı şöyle olsun</text:p>'
                   '<text:p>Второй абзац</text:p></office:text></office:body></office:document-content>')
    m = O.oku(odt)["metin"]
    assert "Bölge paylaşımı" in m and "Второй абзац" in m, m
    rtf = os.path.join(TMP, "c.rtf")
    open(rtf, "w").write(r"{\rtf1\ansi\ansicpg1254{\fonttbl{\f0 Arial;}}\f0 Rakip firma ile \'fcretim kapasitesi\par \u1062?\u1077?\u1085?\u1072? \par}")
    m = O.oku(rtf)["metin"]
    assert "üretim kapasitesi" in m and "Цена" in m, m


@test("okuyucu: uzantisiz dosyanin turu icerikten taninir (PDF, PNG, docx, OLE, metin)")
def _():
    import zipfile
    d = os.path.join(TMP, "uzantisiz"); os.makedirs(d, exist_ok=True)
    yaz = lambda ad, b: open(os.path.join(d, ad), "wb").write(b) and os.path.join(d, ad)
    assert O.tur_tahmin(yaz("a", b"%PDF-1.4\n...")) == ".pdf"
    assert O.tur_tahmin(yaz("b", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)) == ".png"
    assert O.tur_tahmin(yaz("c", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 50)) == ".ole"
    assert O.tur_tahmin(yaz("d", "[InternetShortcut]\nURL=http://ornek.example/ Rakip fiyat listesi".encode())) == ".txt"
    z = os.path.join(d, "e")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("[Content_Types].xml", "<Types/>"); f.writestr("word/document.xml", "<w/>")
    assert O.tur_tahmin(z) == ".docx"
    assert O.tur_tahmin(yaz("f", bytes(range(256)) * 4)) is None
    m = O.oku(os.path.join(d, "d"), "ek_uzantisiz")
    assert m["durum"] == "islendi" and "Rakip fiyat listesi" in m["metin"] and "icerikten" in m["yontem"], m
    bos = O.oku(os.path.join(d, "f"))
    assert bos["durum"] == "okunamadi" and bos["neden"], bos


def _ocr_var():
    return bool(O.arac("tesseract")) and {"tur", "eng"} <= set(O.ocr_dilleri())


def _gorsel(yol, satirlar, boyut=34):
    from PIL import Image, ImageDraw, ImageFont
    yaz = None
    for aday in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf"):
        if os.path.exists(aday):
            yaz = ImageFont.truetype(aday, boyut)
            break
    im = Image.new("RGB", (1400, 70 + 70 * len(satirlar)), "white")
    d = ImageDraw.Draw(im)
    for i, s in enumerate(satirlar):
        d.text((30, 30 + 70 * i), s, fill="black", font=yaz)
    im.save(yol)


@test("OCR: taranmis Turkce gorsel okunur ve [OCR METNI] etiketi tasir")
def _():
    if not _ocr_var():
        return "ATLA"
    p = os.path.join(TMP, "tarama.png")
    _gorsel(p, ["Rakip firma ile ihale teklifleri konuşuldu.", "Bu ay işi onlar alacak, biz yüksek teklif vereceğiz."])
    d = O.oku(p)
    assert d["durum"] == "islendi" and d["ocr"], d
    assert "Bu ay işi onlar alacak, biz yüksek teklif vereceğiz." in d["metin"], d["metin"]
    assert d["metin"].startswith("[OCR METNİ")


@test("OCR: metin katmani olmayan PDF sayfasi OCR'lanir")
def _():
    if not _ocr_var() or not O.arac("pdftoppm"):
        return "ATLA"
    from PIL import Image
    png = os.path.join(TMP, "sayfa.png")
    _gorsel(png, ["Teklif tablosu gizli tutulsun, rakibe gönderildi."])
    pdf = os.path.join(TMP, "taranmis.pdf")
    Image.open(png).convert("RGB").save(pdf, resolution=150)
    d = O.oku(pdf)
    assert d["ocr"] and "rakibe gönderildi" in d["metin"], d


@test("OCR: yanlis dil modeliyle uretilen anlamsiz cikti kayda alinmaz, belge nedeniyle isaretlenir")
def _():
    if not _ocr_var():
        return "ATLA"
    p = os.path.join(TMP, "kiril.png")
    _gorsel(p, ["Цены на следующий месяц согласуем с конкурентом.", "Подтвердите по телефону, письменно не пишите."])
    eski = O.ocr_dilleri
    O.ocr_dilleri = lambda: ["eng"]  # Kiril paketi kurulu degilmis gibi
    try:
        d = O.oku(p)
    finally:
        O.ocr_dilleri = eski
    assert d["durum"] == "okunamadi" and "anlamsiz" in d["neden"], d
    if "rus" in O.ocr_dilleri():
        d2 = O.oku(p)
        assert d2["durum"] == "islendi" and "конкурентом" in d2["metin"], d2


@test("anlamsizlik olcusu: gercek Turkce/Ingilizce/Rusca metin esigin altinda, karisik cop ustunde")
def _():
    for metin in ("Rakip firma ile ihale teklifleri konuşuldu ve fiyatlar birlikte belirlendi.",
                  "We agreed with the competitor to keep prices stable next quarter.",
                  "Цены на следующий месяц согласуем с конкурентом по телефону."):
        assert O.anlamsiz_oran(metin) < O.ANLAMSIZ_ESIK, (metin, O.anlamsiz_oran(metin))
    assert O.anlamsiz_oran("Llenpi Ha cnenyiouynii mecay corsacyem c koHKypeHTOM. NoaTBeppure no TenecboHy") > O.ANLAMSIZ_ESIK


def _pst_beklenen():
    return json.load(open(os.path.join(VERI, "pst", "beklenen.json"), encoding="utf-8"))["dosyalar"]


@test("PST: java-libpst test dosyasi (dist-list.pst) acilir; kaynak testin bekledigi kisi adresi cikar")
def _():
    pst = os.path.join(VERI, "pst", "dist-list.pst")
    if not O.arac("readpst"):
        return "ATLA"
    b = _pst_beklenen()["dist-list.pst"]
    d = O.oku(pst)
    assert d["durum"] == "islendi", d["neden"]
    cocuk = [c for _, c in O.duzlestir(d)][1:]
    assert len(cocuk) >= b["en_az_oge"], f"{len(cocuk)} oge"
    tum = "\n".join(c["metin"] for c in cocuk)
    for ifade in b["metinde_gecmeli"]:
        assert ifade in tum, f"PST ciktisinda yok: {ifade!r}"
    assert all(c["durum"] == "islendi" for c in cocuk), [(c["etiket"], c["neden"]) for c in cocuk if c["durum"] != "islendi"]


@test("PST: pst-extractor Enron posta kutusu; klasorler, konu, gonderen ve govde kaynak projenin testiyle eslesir")
def _():
    import hashlib
    b = _pst_beklenen()["enron.pst"]
    pst = os.path.join(VERI, "pst", "indirilen", "enron.pst")
    if not O.arac("readpst") or not os.path.exists(pst):
        return "ATLA"  # CI dosyayi beklenen.json'daki sabit commit adresinden indirir
    assert hashlib.sha256(open(pst, "rb").read()).hexdigest() == b["sha256"], "enron.pst ozeti tutmuyor"
    d = O.oku(pst, "enron.pst")
    assert d["durum"] == "islendi", d["neden"]
    oge = [c for _, c in O.duzlestir(d)][1:]
    eposta = [c for c in oge if c["etiket"].endswith(".eml")]
    klasor = {c["etiket"].split("#", 1)[1].rsplit("/", 1)[0] for c in eposta}
    for k in b["klasorler"]:
        assert any(x.endswith(k) for x in klasor), f"klasor yok: {k}"
    for k, n in b["klasorde_dogrudan_eposta"].items():
        sayi = sum(1 for c in eposta if c["etiket"].split("#", 1)[1].rsplit("/", 1)[0].endswith(k))
        assert sayi == n, f"{k}: {sayi} e-posta (beklenen {n})"
    for ileti in b["iletiler"]:
        eslesen = [c for c in eposta if c["basliklar"].get("subject", "").strip() == ileti["konu"]]
        assert eslesen, f"konu bulunamadi: {ileti['konu']}"
        c = eslesen[0]
        assert ileti["gonderen"].lower() in c["basliklar"].get("from", "").lower() or ileti["gonderen"] in c["metin"], c["basliklar"]
        assert ileti["govde"] in c["metin"], f"govde yok: {ileti['govde'][:40]}"
        if "tarih" in ileti:
            assert ileti["tarih"] in c["basliklar"].get("date", ""), c["basliklar"].get("date")
    okunamayan = [c for c in oge if c["durum"] != "islendi"]
    assert all(c["neden"] for c in okunamayan), "okunamayan her oge bir neden tasimali"
    assert not [c for c in okunamayan if "desteklenmeyen" in c["neden"]], "uzantisiz ekler icerikten taninmali"
    if O.arac("catdoc") and O.arac("xls2csv"):
        eski = [c for c in oge if c["etiket"].lower().endswith((".doc", ".xls"))]
        okunan = [c for c in eski if c["durum"] == "islendi"]
        assert len(eski) >= 20 and len(okunan) / len(eski) >= 0.85, f"eski Office: {len(okunan)}/{len(eski)}"
        assert any("OPERATOR BALANCING AGREEMENT" in c["metin"] for c in okunan)


@test("PST: vaka yuklemesi posta kutusu ogelerini ayri belgelere ve parcalara boler")
def _():
    pst = os.path.join(VERI, "pst", "indirilen", "enron.pst")
    if not os.path.exists(pst):
        pst = os.path.join(VERI, "pst", "dist-list.pst")
    if not O.arac("readpst"):
        return "ATLA"
    pv = os.path.join(TMP, "pv")
    vaka("ac", pv, "--sentetik")
    s = json.loads(vaka("yukle", pv, pst).strip().splitlines()[-1])
    assert s["belge"] >= 2 and s["parca"] >= 1, s
    if "enron" in pst:
        ilk = vaka("sonraki", pv, "--n", "1")
        assert "on-tarama: ERISIM" in ilk and "!! ERISIM" in ilk, "erisim isaretli parca once ve uyariyla gosterilmeli"


shutil.rmtree(TMP, ignore_errors=True)
print()
if basarisiz:
    print(f"{len(basarisiz)} test KALDI: {basarisiz}")
    sys.exit(1)
print(f"Tum vaka/okuyucu testleri gecti ({len(atlanan)} atlandi: {atlanan})" if atlanan else "Tum vaka/okuyucu testleri gecti.")
