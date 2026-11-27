#!/usr/bin/env python3
"""Ihale taramalarinin gercek kartel verisiyle dogrulanmasi.

Veri: Imhof, D. ve Wallimann, H. (2021) "Detecting bid-rigging coalitions in different countries and auction
formats", Int. Rev. Law Econ. 68, 106016; veri Mendeley Data v1, doi:10.17632/x8jwmbcpgn.1 (CC BY 4.0). Veri depoya konmaz; bu betik
dosyalari bir klasorden okur ya da --indir ile Mendeley'den indirir ve SHA-256 ozetini dogrular.

Verinin yapisi: her satir uc firmalik bir koalisyondur. Satirda, koalisyonun birlikte girdigi
ihalelerden hesaplanmis tarama degerlerinin ozeti (min/max/mean/median) ve kartel donemi etiketi
(cartelperiod) vardir. Zaman sirasi ve tek tek teklifler yoktur. Bu yuzden betik iki sey yapar:

  1. Ayirt edicilik: ihale_analiz.py'nin dayandigi olculer (CV, yayilim) kartel koalisyonlarini
     rekabetci olanlardan ne kadar ayiriyor? (AUC, uc ulke ayri ayri)
  2. Gercek CV dagilimlariyla kirilma testi: her ulkede rekabetci koalisyonlarin CV'lerinden
     ve ardindan kartel koalisyonlarinin CV'lerinden olusan seriler kurulur; ihale_analiz.kirilma_testi
     bu serilerde kirilmayi ne siklikla buluyor, yalniz rekabetci CV'lerden kurulan serilerde ne
     siklikla yanlis alarm veriyor?

Kullanim:
  python3 tests/kartel_dogrulama.py [--veri tests/veri/kartel] [--indir] [--tekrar 200]
Cikis kodu 0: tum beklentiler tuttu; 1: en az biri tutmadi; 2: veri yok."""
import argparse, csv, hashlib, json, os, random, statistics, sys, urllib.error, urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "plugins", "rekabet-ihlali-inceleme", "skills", "rekabet-ihlali-inceleme", "scripts"))
import ihale_analiz as IA  # noqa: E402

BEKLENEN = json.load(open(os.path.join(KOK, "tests", "veri", "kartel_beklenen.json"), encoding="utf-8"))
csv.field_size_limit(10 ** 7)


def oku(yol):
    with open(yol, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def auc(satirlar, sutun, dusuk_kartel):
    """Mann-Whitney AUC: rastgele bir kartel satirinin rastgele bir rekabetci satirdan
    'daha kartel gibi' gorunme olasiligi. Esit degerler yarim sayilir."""
    puan = []
    for s in satirlar:
        try:
            v = float(s[sutun])
        except (ValueError, KeyError):
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        puan.append((-v if dusuk_kartel else v, s["cartelperiod"] == "1"))
    puan.sort(key=lambda x: x[0])
    sira_top, n_p, n_n, i = 0.0, 0, 0, 0
    while i < len(puan):
        j = i
        while j < len(puan) and puan[j][0] == puan[i][0]:
            j += 1
        ort = (i + 1 + j) / 2
        for k in range(i, j):
            if puan[k][1]:
                sira_top += ort; n_p += 1
            else:
                n_n += 1
        i = j
    return (sira_top - n_p * (n_p + 1) / 2) / (n_p * n_n)


def kirilma_gercek_cv(kartel, rekabet, uzunluk, tekrar, tohum=1):
    """Gercek CV degerlerinden seri kurup kirilma testini calistirir. Donus: (guc, yanlis_alarm)."""
    rnd = random.Random(tohum)
    yarim = uzunluk // 2
    guc = yanlis = 0
    for t in range(tekrar):
        seri = rnd.sample(rekabet, yarim) + rnd.sample(kartel, uzunluk - yarim)
        r = IA.kirilma_testi(seri, permutasyon=199, tohum=t)
        guc += bool(r and r[2] <= 0.05 and r[3] >= 1.5)
        bos = rnd.sample(rekabet, uzunluk)
        r = IA.kirilma_testi(bos, permutasyon=199, tohum=t)
        yanlis += bool(r and r[2] <= 0.05 and r[3] >= 1.5)
    return guc / tekrar, yanlis / tekrar


def indir(dosya, hedef):
    """Dosyayi indirir. Site erisimi reddederse False doner (veri yok sayilir, test atlanir)."""
    os.makedirs(os.path.dirname(hedef), exist_ok=True)
    istek = urllib.request.Request(dosya["url"], headers={
        "User-Agent": "antitrust-investigator-validation/1.3 (+https://github.com/savsay/antitrust-investigator)"})
    try:
        with urllib.request.urlopen(istek, timeout=120) as r:
            veri = r.read()
    except (urllib.error.URLError, TimeoutError) as ex:
        print(f"::warning::kartel verisi indirilemedi ({dosya['dosya']}): {ex}. Dosyayi tarayicidan indirip --veri klasorune koyun.")
        return False
    with open(hedef, "wb") as f:
        f.write(veri)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", default=os.path.join(KOK, "tests", "veri", "kartel"))
    ap.add_argument("--indir", action="store_true", help="eksik dosyalari Mendeley'den indir")
    ap.add_argument("--tekrar", type=int, default=200)
    a = ap.parse_args()

    hatalar, rapor = [], {}
    for ulke, b in BEKLENEN["ulkeler"].items():
        yol = os.path.join(a.veri, b["dosya"])
        if not os.path.exists(yol) and a.indir:
            print(f"indiriliyor: {b['dosya']}")
            if not indir(b, yol):
                sys.exit(2)
        if not os.path.exists(yol):
            print(f"VERI YOK: {yol}  (--indir kullanin ya da dosyayi bu klasore koyun)")
            sys.exit(2)
        ozet = hashlib.sha256(open(yol, "rb").read()).hexdigest()
        if ozet != b["sha256"]:
            hatalar.append(f"{ulke}: SHA-256 tutmuyor ({ozet}); dosya degismis ya da farkli surum")
            continue
        S = oku(yol)
        kartel = [float(s["mean3cvbid"]) for s in S if s["cartelperiod"] == "1"]
        rekabet = [float(s["mean3cvbid"]) for s in S if s["cartelperiod"] == "0"]
        r = {"satir": len(S), "kartel": len(kartel), "rekabet": len(rekabet), "auc": {},
             "medyan_cv_orani": statistics.median(rekabet) / statistics.median(kartel)}
        if (len(S), len(kartel)) != (b["satir"], b["kartel"]):
            hatalar.append(f"{ulke}: satir/kartel sayisi {len(S)}/{len(kartel)} (beklenen {b['satir']}/{b['kartel']})")
        for sutun, d in BEKLENEN["olculer"].items():
            deger = auc(S, sutun, d["dusuk_kartel"])
            r["auc"][sutun] = round(deger, 4)
            if abs(deger - b["auc"][sutun]) > 0.0015:
                hatalar.append(f"{ulke} {sutun}: AUC {deger:.4f}, bagimsiz hesap {b['auc'][sutun]:.4f}")
        # ihale_analiz'in dayandigi oncul: kartelde CV duser, yayilim daralir
        for sutun in ("mean3cvbid", "median3cvbid", "mean3Spread"):
            if r["auc"][sutun] < BEKLENEN["en_az_auc"]:
                hatalar.append(f"{ulke} {sutun}: AUC {r['auc'][sutun]} < {BEKLENEN['en_az_auc']}")
        if r["medyan_cv_orani"] < BEKLENEN["kirilma_orani_esigi"]:
            hatalar.append(f"{ulke}: medyan CV orani {r['medyan_cv_orani']:.2f} kirilma esiginin altinda")
        for uzunluk in (20, 40):
            g, y = kirilma_gercek_cv(kartel, rekabet, uzunluk, a.tekrar)
            r[f"kirilma_{uzunluk}"] = {"guc": round(g, 3), "yanlis_alarm": round(y, 3)}
            if y > BEKLENEN["kirilma_en_cok_yanlis"]:
                hatalar.append(f"{ulke} n={uzunluk}: yanlis alarm {y:.3f}")
        if r["kirilma_40"]["guc"] < BEKLENEN["kirilma_40_en_az_guc"]:
            hatalar.append(f"{ulke} n=40: guc {r['kirilma_40']['guc']}")
        rapor[ulke] = r

    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    if hatalar:
        print("\nTUTMAYAN BEKLENTILER:\n  " + "\n  ".join(hatalar))
        sys.exit(1)
    print("\nSONUC: gercek kartel verisinde tum beklentiler tuttu.")


if __name__ == "__main__":
    main()
