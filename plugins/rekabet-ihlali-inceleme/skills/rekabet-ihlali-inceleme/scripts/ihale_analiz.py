"""Ihale teklif verisinde danisiklilik taramasi (OECD / Dunya Bankasi tipi gostergeler).

Kullanim:
  python3 ihale_analiz.py teklifler.csv [--cikti ihale_uyarilari.csv] [--min-ihale 3]
                                        [--sabit-fark-cv 0.15] [--sabit-fark-min 4]
                                        [--yakin-teklif 0.01] [--kaybeden-fark 0.10]

Girdi CSV sutunlari (Turkce ya da Ingilizce ad kabul edilir):
  ihale_id (tender_id), tarih (date, YYYY-AA-GG), firma (bidder), teklif (bid),
  kazanan (winner: 1/0, evet/hayir, true/false)
  istege bagli: kamu (public: evet/hayir), idare (authority), durum (status: gecerli/cekildi/gecersiz)

Cikti bir uyari listesidir, bulgu degildir. Her uyari ilgili ihalelerin belgeleriyle okunmali;
fiyat ortusmesi tek basina kartel kaniti sayilmaz (kontrol MT-24, IHL-10).
Yalniz standart kutuphane kullanir; girdi dosyasini degistirmez."""
import argparse, csv, hashlib, itertools, json, statistics, sys
from collections import Counter, defaultdict

ALIAS = {
    "ihale_id": ["ihale_id", "tender_id", "ihale", "tender"],
    "tarih": ["tarih", "date", "ihale_tarihi"],
    "firma": ["firma", "bidder", "istekli", "company"],
    "teklif": ["teklif", "bid", "teklif_tutari", "amount"],
    "kazanan": ["kazanan", "winner", "won"],
    "kamu": ["kamu", "public", "kamu_ihalesi"],
    "idare": ["idare", "authority", "isveren"],
    "durum": ["durum", "status"],
}
EVET = {"1", "evet", "e", "true", "yes", "y", "x", "kazandi"}
GECERSIZ = {"cekildi", "çekildi", "gecersiz", "geçersiz", "withdrawn", "invalid", "rejected"}


def sutun_eslestir(alanlar):
    kucuk = {a.strip().lower(): a for a in alanlar}
    es = {}
    for hedef, adaylar in ALIAS.items():
        for aday in adaylar:
            if aday in kucuk:
                es[hedef] = kucuk[aday]
                break
    eksik = [s for s in ("ihale_id", "tarih", "firma", "teklif", "kazanan") if s not in es]
    if eksik:
        sys.exit(f"Eksik sutun(lar): {', '.join(eksik)}")
    return es


def sayi(s):
    s = str(s).strip().replace(" ", "")
    if s.count(",") == 1 and s.count(".") >= 1 and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")      # 1.234.567,89
    elif s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")                        # 1234567,89
    else:
        s = s.replace(",", "")                         # 1,234,567.89
    return float(s)


def oku(yol):
    with open(yol, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        es = sutun_eslestir(r.fieldnames or [])
        ihaleler = defaultdict(lambda: {"teklifler": [], "tarih": "", "kamu": False, "idare": ""})
        for satir in r:
            iid = satir[es["ihale_id"]].strip()
            ih = ihaleler[iid]
            ih["tarih"] = satir[es["tarih"]].strip()
            if "kamu" in es:
                ih["kamu"] = ih["kamu"] or satir[es["kamu"]].strip().lower() in EVET
            if "idare" in es:
                ih["idare"] = satir[es["idare"]].strip()
            durum = satir[es["durum"]].strip().lower() if "durum" in es else ""
            ih["teklifler"].append({
                "firma": satir[es["firma"]].strip(),
                "teklif": sayi(satir[es["teklif"]]),
                "kazanan": satir[es["kazanan"]].strip().lower() in EVET,
                "gecerli": durum not in GECERSIZ,
            })
    return dict(sorted(ihaleler.items(), key=lambda kv: (kv[1]["tarih"], kv[0])))


def kazanan(ih):
    k = [t for t in ih["teklifler"] if t["kazanan"]]
    return k[0] if k else None


def tara(ihaleler, min_ihale=3, sabit_fark_cv=0.15, yakin_teklif=0.01, kaybeden_fark=0.10, sabit_fark_min=4):
    uyarilar = []

    def ekle(tarama, kontrol, firmalar, ihale_listesi, metrik, aciklama, alternatif):
        uyarilar.append({
            "uyari_id": f"U-{len(uyarilar) + 1:03d}", "tarama": tarama, "kontrol": kontrol,
            "firmalar": "; ".join(sorted(firmalar)), "ihaleler": "; ".join(ihale_listesi),
            "metrik": json.dumps(metrik, ensure_ascii=False), "aciklama": aciklama,
            "alternatif_aciklama": alternatif,
            "kamu_ihalesi": "evet" if any(ihaleler[i]["kamu"] for i in ihale_listesi) else "hayir",
        })

    # 1) Rotasyon: ayni istekli grubu tekrar tekrar karsilasiyor ve kazanan sirayla degisiyor (IHL-03)
    gruplar = defaultdict(list)
    for iid, ih in ihaleler.items():
        firmalar = frozenset(t["firma"] for t in ih["teklifler"] if t["gecerli"])
        if len(firmalar) >= 3 and kazanan(ih):
            gruplar[firmalar].append(iid)
    for firmalar, liste in gruplar.items():
        if len(liste) < max(min_ihale, 2 * len(firmalar)):  # en az iki tam tur
            continue
        sira = [kazanan(ihaleler[i])["firma"] for i in liste]
        sayim = Counter(sira)
        art_arda = sum(1 for a, b in zip(sira, sira[1:]) if a == b)
        if set(sayim) == set(firmalar) and max(sayim.values()) - min(sayim.values()) <= 1 and art_arda == 0:
            ekle("ROTASYON", "IHL-03", firmalar, liste,
                 {"kazanan_sirasi": sira, "kazanma_sayisi": dict(sayim)},
                 f"Ayni {len(firmalar)} istekli {len(liste)} ihalede karsilasmis; her biri sirayla ve esit sayida kazanmis.",
                 "Kapasite sinirlari, is yuku veya ihale paketlerinin farkli uzmanlik gerektirmesi.")

    # 2) Sabit fark: kaybedenin teklifi kazananinkinin hep ayni oranda uzerinde (IHL-07, IHL-01)
    oranlar = defaultdict(list)
    for iid, ih in ihaleler.items():
        k = kazanan(ih)
        if not k or k["teklif"] <= 0:
            continue
        for t in ih["teklifler"]:
            if t["gecerli"] and not t["kazanan"]:
                oranlar[(t["firma"], k["firma"])].append((iid, t["teklif"] / k["teklif"]))
    for (kaybeden, kazanan_firma), deger in oranlar.items():
        if len(deger) < max(min_ihale, sabit_fark_min):  # az ornekte tesaduf payi yuksek
            continue
        r = [d for _, d in deger]
        ort = statistics.mean(r)
        fark = [d - 1 for d in r]                     # oran degil fark yuzdesi: dar fiyat bandinda da ayirt edici
        fark_ort = statistics.mean(fark)
        cv = statistics.pstdev(fark) / fark_ort if fark_ort > 0 else 1
        if cv <= sabit_fark_cv and min(fark) > 0:
            ekle("SABIT_FARK", "IHL-07", [kaybeden, kazanan_firma], [i for i, _ in deger],
                 {"ortalama_fark": round(fark_ort, 4), "farkin_degiskenlik_katsayisi": round(cv, 4), "ihale_sayisi": len(r)},
                 f"{kaybeden}, {kazanan_firma} kazandiginda teklifini surekli yaklasik %{(ort - 1) * 100:.1f} yuksek vermis.",
                 "Ayni maliyet formulu, ayni tedarikci fiyat listesi veya kamuya acik birim fiyatlarin kullanilmasi.")

    # 3) Olagandisi yakin veya ayni teklifler (IHL-05, IHL-01)
    for iid, ih in ihaleler.items():
        gec = [t for t in ih["teklifler"] if t["gecerli"]]
        if len(gec) < 3:
            continue
        tek = sorted(t["teklif"] for t in gec)
        yayilim = (tek[-1] - tek[0]) / tek[0] if tek[0] else 1
        ayni = [f for f, s in Counter(t["teklif"] for t in gec).items() if s > 1]
        if yayilim <= yakin_teklif or ayni:
            ekle("YAKIN_TEKLIF", "IHL-05", [t["firma"] for t in gec], [iid],
                 {"yayilim": round(yayilim, 4), "ayni_tutarli_teklif": len(ayni) > 0},
                 "Ayni ihaledeki teklifler olagandisi yakin" + (" ve en az iki teklif birebir ayni." if ayni else "."),
                 "Idarenin yaklasik maliyeti veya birim fiyatlari teklifleri belirliyor olabilir.")

    # 4) Hep kaybeden, hep az farkla (destek teklif profili, IHL-01)
    profil = defaultdict(lambda: {"teklif": 0, "kazanma": 0, "farklar": [], "ihaleler": []})
    for iid, ih in ihaleler.items():
        k = kazanan(ih)
        for t in ih["teklifler"]:
            if not t["gecerli"]:
                continue
            p = profil[t["firma"]]
            p["teklif"] += 1
            p["ihaleler"].append(iid)
            if t["kazanan"]:
                p["kazanma"] += 1
            elif k and k["teklif"] > 0:
                p["farklar"].append(t["teklif"] / k["teklif"] - 1)
    for firma, p in profil.items():
        if p["teklif"] >= min_ihale and p["kazanma"] == 0 and p["farklar"] and \
                all(0 < f <= kaybeden_fark for f in p["farklar"]):
            ekle("HEP_KAYBEDEN", "IHL-01", [firma], p["ihaleler"],
                 {"teklif_sayisi": p["teklif"], "medyan_fark": round(statistics.median(p["farklar"]), 4)},
                 f"{firma} {p['teklif']} ihaleye girmis, hic kazanmamis; her seferinde kazanandan en fazla %{kaybeden_fark * 100:.0f} yuksek kalmis.",
                 "Pazara yeni giren, kapasitesi sinirli veya stratejik olarak deneme teklifi veren firma.")

    # 5) Cekilme sonrasi ayni firmanin kazanmasi (IHL-02)
    cekilen = defaultdict(list)
    for iid, ih in ihaleler.items():
        k = kazanan(ih)
        for t in ih["teklifler"]:
            if not t["gecerli"] and k:
                cekilen[(t["firma"], k["firma"])].append(iid)
    for (firma, kaz), liste in cekilen.items():
        if len(liste) >= 2:
            ekle("CEKILME", "IHL-02", [firma, kaz], liste, {"tekrar": len(liste)},
                 f"{firma} teklifini {len(liste)} kez cekmis ya da gecersiz kalmis; her seferinde {kaz} kazanmis.",
                 "Belge eksikligi, kapasite veya teminat sorunu gibi bagimsiz nedenler.")
    return uyarilar


def main():
    ap = argparse.ArgumentParser(description="Ihale teklif verisinde danisiklilik taramasi")
    ap.add_argument("girdi")
    ap.add_argument("--cikti", default="ihale_uyarilari.csv")
    ap.add_argument("--min-ihale", type=int, default=3)
    ap.add_argument("--sabit-fark-cv", type=float, default=0.15)
    ap.add_argument("--sabit-fark-min", type=int, default=4)
    ap.add_argument("--yakin-teklif", type=float, default=0.01)
    ap.add_argument("--kaybeden-fark", type=float, default=0.10)
    a = ap.parse_args()
    ihaleler = oku(a.girdi)
    uyarilar = tara(ihaleler, a.min_ihale, a.sabit_fark_cv, a.yakin_teklif, a.kaybeden_fark, a.sabit_fark_min)
    alanlar = ["uyari_id", "tarama", "kontrol", "firmalar", "ihaleler", "metrik", "aciklama",
               "alternatif_aciklama", "kamu_ihalesi"]
    with open(a.cikti, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar)
        w.writeheader()
        w.writerows(uyarilar)
    with open(a.girdi, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    print(json.dumps({"girdi_sha256": sha, "ihale": len(ihaleler), "uyari": len(uyarilar),
                      "tarama_sayilari": dict(Counter(u["tarama"] for u in uyarilar)),
                      "kamu_ihalesi_uyarisi": sum(u["kamu_ihalesi"] == "evet" for u in uyarilar),
                      "esikler": {"min_ihale": a.min_ihale, "sabit_fark_cv": a.sabit_fark_cv, "sabit_fark_min": a.sabit_fark_min,
                                  "yakin_teklif": a.yakin_teklif, "kaybeden_fark": a.kaybeden_fark},
                      "cikti": a.cikti}, ensure_ascii=False))


if __name__ == "__main__":
    main()
