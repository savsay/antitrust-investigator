#!/usr/bin/env python3
"""Rekabet kaynak katalogunu yonetir.

Katalog: references/kaynaklar.csv  (Kaynak_Envanteri.csv ile ayni sutunlar)
Kontroller: references/kontroller.csv (Kontrol_Katalogu.csv ile ayni sutunlar)

Komutlar:
  dogrula                 katalogu ve kontrol-kaynak baglarini denetler (hata varsa cikis kodu 1)
  listele [--onek TR]     kaynaklari kisa liste olarak yazar
  ekle ...                yeni kaynak satiri ekler; --kontroller verilirse kontroller.csv'ye de baglar

Ornek:
  python3 scripts/kaynak_yonet.py ekle --onek TR --baslik "Hakim Durum Kilavuzu" --kurum "Rekabet Kurumu" \
    --bolge Turkiye --surum "2026" --tur Kilavuz --amac "Dislayici davranis analizi" \
    --url "https://www.rekabet.gov.tr/..." --kontroller "HD-03,DKY-05"
"""
import argparse, csv, datetime, os, re, sys
from urllib.parse import urlparse

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG = os.path.join(KOK, "references", "kaynaklar.csv")
KONTROL = os.path.join(KOK, "references", "kontroller.csv")

SUTUNLAR = ["source_id", "region", "title", "authority", "version", "document_status", "purpose", "url",
            "original_url", "landing_url", "download_status", "local_file", "text_file", "page_count", "sha256",
            "legal_approval", "active_rag", "training_rights", "legal_currentness_review", "note"]
ZORUNLU = ["source_id", "region", "title", "authority", "version", "document_status", "purpose", "url",
           "legal_approval"]
ONAY_DEGERLERI = {"Bekliyor", "Onaylandı", "Reddedildi", "Geri çekildi"}
RESMI_ALANLAR = ("rekabet.gov.tr", "mevzuat.gov.tr", "resmigazete.gov.tr", "kvkk.gov.tr", "danistay.gov.tr",
                 "yargitay.gov.tr", "europa.eu", "justice.gov", "ftc.gov", "gov.uk", "oecd.org", "fas.gov.ru",
                 "wipo.int", "nist.gov", "worldbank.org", "theiia.org", "iso.org")
ID_RX = re.compile(r"^[A-Z]{2,5}-\d{2,3}$")


def oku(yol):
    if not os.path.exists(yol):
        return [], []
    with open(yol, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def yaz(yol, alanlar, satirlar):
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar)
        w.writeheader()
        w.writerows(satirlar)
    os.replace(gecici, yol)


def resmi_mi(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == a or host.endswith("." + a) for a in RESMI_ALANLAR)


def dogrula(sessiz=False):
    hatalar, uyarilar = [], []
    alanlar, satirlar = oku(KATALOG)
    if not satirlar:
        hatalar.append(f"Katalog bulunamadi veya bos: {KATALOG}")
    eksik = [s for s in SUTUNLAR if s not in alanlar]
    if eksik:
        hatalar.append(f"Eksik sutun(lar): {', '.join(eksik)}")
    gorulen = set()
    for i, s in enumerate(satirlar, start=2):
        sid = (s.get("source_id") or "").strip()
        if not ID_RX.match(sid):
            hatalar.append(f"Satir {i}: gecersiz source_id '{sid}' (ornek bicim: TR-15)")
        if sid in gorulen:
            hatalar.append(f"Satir {i}: tekrar eden source_id '{sid}'")
        gorulen.add(sid)
        for z in ZORUNLU:
            if not (s.get(z) or "").strip():
                hatalar.append(f"{sid}: zorunlu alan bos: {z}")
        url = (s.get("url") or "").strip()
        if url and urlparse(url).scheme != "https":
            hatalar.append(f"{sid}: url https olmali: {url}")
        elif url and not resmi_mi(url):
            uyarilar.append(f"{sid}: url resmi alan adi listesinde degil, kaynagi teyit edin: {url}")
        onay = (s.get("legal_approval") or "").strip()
        if onay and onay not in ONAY_DEGERLERI:
            uyarilar.append(f"{sid}: legal_approval beklenmeyen deger '{onay}'")
    _, kontroller = oku(KONTROL)
    for k in kontroller:
        for ref in filter(None, (x.strip() for x in (k.get("source_ids") or "").replace(";", ",").split(","))):
            if ref not in gorulen:
                hatalar.append(f"{k.get('control_id')}: bilinmeyen kaynak kimligi '{ref}'")
    if not sessiz:
        for u in uyarilar:
            print("UYARI:", u)
        for h in hatalar:
            print("HATA :", h)
        print(f"{len(satirlar)} kaynak, {len(kontroller)} kontrol denetlendi: {len(hatalar)} hata, {len(uyarilar)} uyari.")
    return hatalar


def sonraki_id(satirlar, onek):
    nums = [int(s["source_id"].split("-")[1]) for s in satirlar
            if s.get("source_id", "").startswith(onek + "-") and ID_RX.match(s["source_id"])]
    return f"{onek}-{(max(nums) + 1) if nums else 1:02d}"


def ekle(a):
    alanlar, satirlar = oku(KATALOG)
    alanlar = alanlar or SUTUNLAR
    sid = a.id or sonraki_id(satirlar, a.onek.upper())
    if not ID_RX.match(sid):
        sys.exit(f"Gecersiz kimlik: {sid}")
    if any(s["source_id"] == sid for s in satirlar):
        sys.exit(f"{sid} zaten var; baska kimlik verin veya --onek kullanin.")
    if urlparse(a.url).scheme != "https":
        sys.exit("URL https ile baslamali.")
    if not resmi_mi(a.url):
        print(f"UYARI: {a.url} resmi alan adi listesinde degil. Kaynagin resmi oldugunu teyit edin.")
    bugun = datetime.date.today().strftime("%d.%m.%Y")
    yeni = {k: "" for k in alanlar}
    yeni.update({
        "source_id": sid, "region": a.bolge, "title": a.baslik, "authority": a.kurum, "version": a.surum,
        "document_status": a.tur, "purpose": a.amac, "url": a.url, "original_url": a.orijinal_url or a.url,
        "download_status": "Baglanti var; dosya eklenmedi", "legal_approval": "Bekliyor", "active_rag": "False",
        "training_rights": "Ayrıca hukuk ve lisans incelemesi gerekli",
        "legal_currentness_review": "Olay tarihi ve güncel değişiklikler hukukça doğrulanacak",
        "note": (a.notlar + " " if a.notlar else "") + f"Kataloğa {bugun} tarihinde eklendi.",
    })
    satirlar.append(yeni)
    yaz(KATALOG, alanlar, satirlar)
    print(f"Eklendi: {sid} | {a.baslik}")
    if a.kontroller:
        k_alanlar, kontroller = oku(KONTROL)
        hedef = {x.strip() for x in a.kontroller.split(",") if x.strip()}
        bulunan = set()
        for k in kontroller:
            if k.get("control_id") in hedef:
                mevcut = [x.strip() for x in (k.get("source_ids") or "").replace(";", ",").split(",") if x.strip()]
                if sid not in mevcut:
                    k["source_ids"] = "; ".join(mevcut + [sid])
                bulunan.add(k["control_id"])
        yaz(KONTROL, k_alanlar, kontroller)
        print(f"Kontrollere baglandi: {', '.join(sorted(bulunan)) or '-'}")
        if hedef - bulunan:
            print(f"UYARI: bulunamayan kontrol(ler): {', '.join(sorted(hedef - bulunan))}")
    if dogrula(sessiz=True):
        print("UYARI: katalog dogrulamasi hata veriyor; 'dogrula' komutunu calistirin.")
    print("Sonraki adimlar: CHANGELOG.md'ye not dusun, plugin.json surumunu artirin, hukuk onayini isleyin.")


def listele(a):
    _, satirlar = oku(KATALOG)
    for s in satirlar:
        if a.onek and not s["source_id"].startswith(a.onek.upper() + "-"):
            continue
        print(f"{s['source_id']:<9} {s.get('legal_approval', ''):<10} {s['title'][:70]}")


def main():
    ap = argparse.ArgumentParser(description="Rekabet kaynak katalogu yonetimi")
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("dogrula")
    l = alt.add_parser("listele"); l.add_argument("--onek")
    e = alt.add_parser("ekle")
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="ornek: TR-15")
    g.add_argument("--onek", help="TR, EU, US, UK, OECD, DP, RU... siradaki bos numara secilir")
    e.add_argument("--baslik", required=True); e.add_argument("--kurum", required=True)
    e.add_argument("--bolge", required=True, help="Turkiye, Avrupa_Birligi, ABD, Birlesik_Krallik, Rusya...")
    e.add_argument("--surum", required=True); e.add_argument("--tur", required=True)
    e.add_argument("--amac", required=True); e.add_argument("--url", required=True)
    e.add_argument("--orijinal-url", dest="orijinal_url"); e.add_argument("--kontroller")
    e.add_argument("--not", dest="notlar")
    a = ap.parse_args()
    if a.komut == "dogrula":
        sys.exit(1 if dogrula() else 0)
    if a.komut == "listele":
        listele(a)
    if a.komut == "ekle":
        ekle(a)


if __name__ == "__main__":
    main()
