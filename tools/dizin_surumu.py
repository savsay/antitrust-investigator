#!/usr/bin/env python3
"""Claude dizini (claude.ai/directory) için yalnız metin dosyalarından oluşan eklenti kopyasını üretir.

Dizin, Verified olmayan organizasyonlardan yalnız Markdown, metin, JSON, YAML ve görsel kabul eder.
Bu araç ana eklentiyi (plugins/rekabet-ihlali-inceleme) şu dönüşümlerle directory/ altına kopyalar:
  - references/*.csv  -> aynı sütunlarla .json (satır başına bir nesne)
  - scripts/ihale_analiz.py -> scripts/ihale_analiz.md (kod bloğu; SKILL.md onu yazıp çalıştırmayı söyler)
  - scripts/rekabet_tarama.py -> atlanır (SKILL.md bölüm 11'de gömülü kopyası var)
  - scripts/kaynak_yonet.py   -> atlanır (bakımcı aracı; GitHub reposunda çalışır)
Kullanım:  python3 tools/dizin_surumu.py            (üretir)
           python3 tools/dizin_surumu.py --denetle  (güncel değilse 1 ile çıkar)"""
import csv, json, os, shutil, sys, tempfile, filecmp

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = "rekabet-ihlali-inceleme"
KAYNAK = os.path.join(KOK, "plugins", AD)
HEDEF = os.path.join(KOK, "directory", AD)
ATLA = {"rekabet_tarama.py", "kaynak_yonet.py", "__pycache__"}


def uret(hedef):
    if os.path.exists(hedef):
        shutil.rmtree(hedef)
    for kok, klasorler, dosyalar in os.walk(KAYNAK):
        klasorler[:] = [k for k in klasorler if k not in ATLA]
        goreli = os.path.relpath(kok, KAYNAK)
        os.makedirs(os.path.join(hedef, goreli), exist_ok=True)
        for ad in sorted(dosyalar):
            if ad in ATLA or ad.endswith(".pyc"):
                continue
            src = os.path.join(kok, ad)
            if ad.endswith(".csv"):
                with open(src, encoding="utf-8-sig", newline="") as f:
                    satirlar = list(csv.DictReader(f))
                with open(os.path.join(hedef, goreli, ad[:-4] + ".json"), "w", encoding="utf-8") as f:
                    json.dump(satirlar, f, ensure_ascii=False, indent=1)
                    f.write("\n")
            elif ad.endswith(".py"):
                kod = open(src, encoding="utf-8").read()
                with open(os.path.join(hedef, goreli, ad[:-3] + ".md"), "w", encoding="utf-8") as f:
                    f.write(f"# {ad}\n\nBu dosya Claude dizini sürümünde betiğin okunabilir kopyasıdır. "
                            f"Aşağıdaki kodu değiştirmeden çalışma klasörüne `{ad}` olarak yazın ve "
                            f"SKILL.md'deki komutla çalıştırın. Kaynak: "
                            f"https://github.com/savsay/antitrust-investigator/blob/main/plugins/{AD}/"
                            f"{os.path.relpath(src, KAYNAK).replace(os.sep, '/')}\n\n```python\n{kod}```\n")
            elif ad.endswith(".md") or ad.endswith(".json") or ad.endswith(".png") or ad == "LICENSE":
                shutil.copy2(src, os.path.join(hedef, goreli, ad))
            else:
                sys.exit(f"Dizin sürümüne alınamayan dosya türü: {src}")


def ayni(a, b):
    c = filecmp.dircmp(a, b)
    if c.left_only or c.right_only or c.diff_files or c.funny_files:
        return False
    _, uyusmayan, hatali = filecmp.cmpfiles(a, b, c.common_files, shallow=False)
    return not uyusmayan and not hatali and all(ayni(os.path.join(a, d), os.path.join(b, d)) for d in c.common_dirs)


if __name__ == "__main__":
    if "--denetle" in sys.argv:
        with tempfile.TemporaryDirectory() as t:
            uret(os.path.join(t, AD))
            if not os.path.isdir(HEDEF) or not ayni(os.path.join(t, AD), HEDEF):
                sys.exit("directory/ güncel değil: python3 tools/dizin_surumu.py çalıştırın")
        print("directory/ güncel")
    else:
        uret(HEDEF)
        print(f"{HEDEF} üretildi")
