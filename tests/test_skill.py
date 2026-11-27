#!/usr/bin/env python3
"""Repo testleri. Ek bağımlılık gerektirmez: python3 tests/test_skill.py"""
import csv, json, os, re, subprocess, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = "rekabet-ihlali-inceleme"
PLUGIN = os.path.join(KOK, "plugins", AD)
SKILL = os.path.join(PLUGIN, "skills", AD)
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import rekabet_tarama as R  # noqa: E402
import ihale_analiz as IA  # noqa: E402

basarisiz = []


def test(ad):
    def sar(f):
        try:
            f(); print(f"GECTI   {ad}")
        except AssertionError as e:
            basarisiz.append(ad); print(f"KALDI   {ad}: {e}")
        return f
    return sar


SKILL_MD = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()


@test("SKILL.md onbilgisi gecerli")
def _():
    m = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", SKILL_MD)
    assert m, "frontmatter bulunamadi"
    assert m.group(1) == AD, f"name '{m.group(1)}' != {AD}"
    d = m.group(2)
    assert len(d) <= 1024, f"description {len(d)} karakter (en fazla 1024)"
    assert "<" not in d and ">" not in d, "description acili ayrac iceremez"
    assert SKILL_MD.count("\n") < 500, "SKILL.md 500 satiri asmamali"


@test("SKILL.md icindeki betik scripts/rekabet_tarama.py ile ayni")
def _():
    gomulu = re.search(r"```python\n(\"\"\"Rekabet riski.*?)```", SKILL_MD, re.S).group(1)
    dosya = open(os.path.join(SKILL, "scripts", "rekabet_tarama.py"), encoding="utf-8").read()
    assert gomulu == dosya, "iki kopya farkli; SKILL.md'deki blogu dosyayla esitleyin"


@test("plugin, marketplace ve skill adlari ayni")
def _():
    p = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8"))
    m = json.load(open(os.path.join(KOK, ".claude-plugin", "marketplace.json"), encoding="utf-8"))
    assert p["name"] == AD
    assert [x["name"] for x in m["plugins"]] == [AD]
    assert m["plugins"][0]["source"] == f"./plugins/{AD}"


@test("kaynak katalogu ve kontrol baglari dogrulaniyor")
def _():
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "kaynak_yonet.py"), "dogrula"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]


@test("sentetik orneklerde tarama davranisi (69 ornek, TR/EN/RU)")
def _():
    yol = os.path.join(KOK, "tests", "veri", "sentetik_ornekler.jsonl")
    ornekler = [json.loads(s) for s in open(yol, encoding="utf-8")]
    kacan = []
    for o in ornekler:
        c = R.kavramlar(o["input_text"]); sv = R.seviye(c); lab = o["label"]
        if lab in ("risk_signal", "insufficient_context") and sv not in ("A", "B"):
            kacan.append((o["sample_id"], lab, sv))
        if lab == "access_restricted" and sv != "ERISIM":
            kacan.append((o["sample_id"], lab, sv))
        if lab == "no_signal_in_excerpt" and "BAGLAM_AZALTICI" not in c:
            kacan.append((o["sample_id"], lab, "baglam azaltici yok"))
    assert len(ornekler) >= 69, f"yalniz {len(ornekler)} ornek"
    assert not kacan, f"{len(kacan)} ornek beklenen kuyruga dusmedi: {kacan[:8]}"


@test("ortulu dil: tek basina kuyruga almaz; karsi tarafla birlikte okunur; 'zaman' kelimesi fiyat sayilmaz")
def _():
    assert R.seviye(R.kavramlar("Toplantıda konuştuğumuz gibi raporu cuma gönderiyorum.")) is None
    assert R.seviye(R.kavramlar("As we discussed, let us meet in person next week.")) is None
    assert R.seviye(R.kavramlar("Rakip ile malum konuyu konuştuk, sıra onlarda.")) == "B"
    assert R.seviye(R.kavramlar("Rakip firmayla ihalede her zamanki gibi; onlar 12 olsun.")) == "A"
    for kelime in ("zaman", "zamanında", "her zamanki gibi", "o zamanlar"):
        assert "FIYAT" not in R.kavramlar(kelime), kelime
    for kelime in ("zam", "zammı", "zamları", "zamlı"):
        assert "FIYAT" in R.kavramlar(kelime), kelime


@test("ofsetler orijinal metne ait (Turkce buyuk harf dahil)")
def _():
    t = "Merhaba.\nRAKİP firma ile GÖRÜŞTÜK; gelecek ay ikimiz de zam yapacağız. Aramızda kalsın."
    h = R.tara(t)
    assert h and h[0]["seviye"] == "A"
    assert t[h[0]["start_char"]:h[0]["end_char"]].strip().startswith("Merhaba")


@test("ihale_analiz: sentetik halka yakalanir, rekabetci grup temiz kalir")
def _():
    ih = IA.oku(os.path.join(KOK, "tests", "veri", "ihale_ornek.csv"))
    u = IA.tara(ih)
    tur = {x["tarama"] for x in u}
    assert {"ROTASYON", "SABIT_FARK", "HEP_KAYBEDEN", "CEKILME"} <= tur, tur
    halka = {"Alfa Yapi", "Beta Insaat", "Gama Taahhut"}
    rot = [x for x in u if x["tarama"] == "ROTASYON"]
    assert rot and set(rot[0]["firmalar"].split("; ")) == halka
    assert rot[0]["kamu_ihalesi"] == "evet", "kamu ihalesi isareti (IHL-09) kayboldu"
    rakip = {"Delta Muhendislik", "Epsilon Yapi", "Zeta Insaat", "Eta Taahhut"}
    yanlis = [x for x in u if set(x["firmalar"].split("; ")) & rakip]
    assert not yanlis, f"rekabetci gruba yanlis alarm: {yanlis[:2]}"
    assert all(x["alternatif_aciklama"] for x in u), "her uyari alternatif aciklama tasimali"


@test("ihale_analiz: rastgele rekabetci pazarlarda yanlis alarm sinirli")
def _():
    import random
    alarm = 0
    for tohum in range(200):
        rnd = random.Random(tohum); ih = {}
        for i in range(10):
            taban = rnd.uniform(5e6, 9e6)
            t = {f"F{j}": taban * rnd.uniform(0.85, 1.20) for j in range(4)}
            k = min(t, key=t.get)
            ih[f"T{i:02d}"] = {"tarih": f"2025-{i:02d}", "kamu": False, "idare": "",
                              "teklifler": [{"firma": f, "teklif": v, "kazanan": f == k, "gecerli": True}
                                            for f, v in t.items()]}
        alarm += bool(IA.tara(ih))
    assert alarm / 200 <= 0.12, f"yanlis alarm orani {alarm / 200:.2f}"


def _kirilma_serisi(rnd, n, kartel_bas, oran, sd_rek=0.06, firma=4):
    ih = {}
    for i in range(n):
        sd = sd_rek / oran if i >= kartel_bas else sd_rek
        taban = rnd.uniform(5e6, 9e6)
        t = {f"F{j}": taban * (1 + rnd.gauss(0, sd)) for j in range(firma)}
        k = min(t, key=t.get)
        ih[f"T{i:03d}"] = {"tarih": f"{2020 + i // 12}-{i % 12 + 1:02d}", "kamu": False, "idare": "",
                          "teklifler": [{"firma": f, "teklif": v, "kazanan": f == k, "gecerli": True} for f, v in t.items()]}
    return ih


def _kirilma_uyarisi(ih, tohum):
    return [x for x in IA.tara(ih, permutasyon=199, tohum=tohum) if x["tarama"] == "DEGISKENLIK_KIRILMASI"]


@test("degiskenlik kirilmasi: belirgin basamakta bolme noktasi dogru bulunur, CV ve p raporlanir")
def _():
    seri = [0.06] * 12 + [0.02] * 12
    seri = [v * (1 + 0.05 * ((i * 7) % 5 - 2)) for i, v in enumerate(seri)]
    k, T, p, oran = IA.kirilma_testi(seri, permutasyon=499)
    assert k == 12 and p < 0.01 and 2.5 < oran < 3.5, (k, T, p, oran)
    assert IA.kirilma_testi([0.05] * 11) is None, "kisa seri test edilmemeli"
    assert IA.kirilma_testi([0.05] * 20) is None, "sabit seride kirilma yok"
    u = _kirilma_uyarisi(_kirilma_serisi(__import__("random").Random(3), 30, 15, 3.0), 3)
    assert u and u[0]["kontrol"] == "IHL-10" and u[0]["alternatif_aciklama"], u
    m = json.loads(u[0]["metrik"])
    assert m["medyan_cv_dusuk"] < m["medyan_cv_yuksek"] and m["p"] <= m["bh_esik"] and m["ihale_dusuk"] >= 6, m
    assert abs(m["ihale_yuksek"] - 15) <= 2, m


@test("degiskenlik kirilmasi: simulasyonda guc ve yanlis alarm (gercek kartel verisindeki etki buyuklukleriyle)")
def _():
    import random
    # Etki: Imhof-Wallimann verisinde rekabetci/kartel medyan CV orani Isvicre 1.8, Italya 3.9, Japonya 5.6
    guc_18 = sum(bool(_kirilma_uyarisi(_kirilma_serisi(random.Random(s), 40, 20, 1.8), s)) for s in range(60)) / 60
    guc_30 = sum(bool(_kirilma_uyarisi(_kirilma_serisi(random.Random(s), 20, 10, 3.0), s)) for s in range(60)) / 60
    yanlis = sum(bool(_kirilma_uyarisi(_kirilma_serisi(random.Random(10000 + s), 30, 30, 1.0), s)) for s in range(200)) / 200
    assert guc_18 >= 0.75, f"oran 1.8, 40 ihale: guc {guc_18:.2f}"
    assert guc_30 >= 0.90, f"oran 3.0, 20 ihale: guc {guc_30:.2f}"
    assert yanlis <= 0.09, f"kartelsiz seride yanlis alarm {yanlis:.3f}"


@test("ihale_analiz: komut satiri her ihalenin CV'sini ayri dosyaya ve ozete yazar")
def _():
    import tempfile
    d = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "ihale_analiz.py"), os.path.join(KOK, "tests", "veri", "ihale_ornek.csv"),
                        "--cikti", os.path.join(d, "u.csv"), "--cv-cikti", os.path.join(d, "cv.csv")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ozet = json.loads(r.stdout)
    assert ozet["cv"]["ihale"] > 0 and ozet["esikler"]["kirilma_min"] == 6
    satir = list(csv.DictReader(open(os.path.join(d, "cv.csv"), encoding="utf-8-sig")))
    assert len(satir) == ozet["ihale"] and all(("cv" in x) for x in satir)


@test("ihale_analiz: Turkce ve Ingilizce sayi bicimleri")
def _():
    assert IA.sayi("1.234.567,89") == 1234567.89
    assert IA.sayi("1,234,567.89") == 1234567.89
    assert IA.sayi("1234567,5") == 1234567.5


@test("bulgu semasi v1.2 geriye donuk uyumlu")
def _():
    d = json.load(open(os.path.join(SKILL, "references", "bulgu_semasi.json"), encoding="utf-8"))
    gerekli = ["finding_id", "finding_type", "jurisdictions", "control_ids", "summary", "priority", "evidence",
               "legal_references", "missing_facts", "alternative_explanations", "human_review_required",
               "next_action", "versions"]
    assert d["required"] == gerekli, "zorunlu alanlar degismemeli"
    for alan in ("assessment", "parallel_exposure", "escalation_route", "data_screens", "title", "area", "claims", "coded_language"):
        assert alan in d["properties"] and alan not in d["required"], alan
    assert "role" in d["properties"]["evidence"]["items"]["properties"]


@test("Claude dizini surumu (directory/) guncel ve yalniz izinli dosya turlerinden olusuyor")
def _():
    r = subprocess.run([sys.executable, os.path.join(KOK, "tools", "dizin_surumu.py"), "--denetle"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    izinli = (".md", ".json", ".png")
    for kok, _, dosyalar in os.walk(os.path.join(KOK, "directory")):
        for ad in dosyalar:
            yol = os.path.join(kok, ad)
            assert ad.endswith(izinli) or ad == "LICENSE", f"izinsiz dosya: {yol}"
            if not ad.endswith(".png"):
                assert not open(yol, encoding="utf-8").read().startswith("#!"), f"#! ile basliyor: {yol}"


print()
if basarisiz:
    print(f"{len(basarisiz)} test kaldi."); sys.exit(1)
print("Tum testler gecti.")
