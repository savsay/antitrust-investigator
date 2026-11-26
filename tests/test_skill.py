#!/usr/bin/env python3
"""Repo testleri. Ek bağımlılık gerektirmez: python3 tests/test_skill.py"""
import json, os, re, subprocess, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = "rekabet-ihlali-inceleme"
PLUGIN = os.path.join(KOK, "plugins", AD)
SKILL = os.path.join(PLUGIN, "skills", AD)
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import rekabet_tarama as R  # noqa: E402

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
    gomulu = re.search(r"```python\n(#!/usr/bin/env python3.*?)```", SKILL_MD, re.S).group(1)
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


@test("sentetik orneklerde tarama davranisi (60 ornek, TR/EN/RU)")
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
    assert len(ornekler) >= 60, f"yalniz {len(ornekler)} ornek"
    assert not kacan, f"{len(kacan)} ornek beklenen kuyruga dusmedi: {kacan[:8]}"


@test("ofsetler orijinal metne ait (Turkce buyuk harf dahil)")
def _():
    t = "Merhaba.\nRAKİP firma ile GÖRÜŞTÜK; gelecek ay ikimiz de zam yapacağız. Aramızda kalsın."
    h = R.tara(t)
    assert h and h[0]["seviye"] == "A"
    assert t[h[0]["start_char"]:h[0]["end_char"]].strip().startswith("Merhaba")


print()
if basarisiz:
    print(f"{len(basarisiz)} test kaldi."); sys.exit(1)
print("Tum testler gecti.")
