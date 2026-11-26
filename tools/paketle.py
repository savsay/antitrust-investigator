#!/usr/bin/env python3
"""claude.ai'ye yüklenecek skill zip'ini üretir: dist/rekabet-ihlali-inceleme.zip
Zip'in kökünde skill klasörü bulunur (claude.ai'nin beklediği yapı)."""
import os, zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = "rekabet-ihlali-inceleme"
SKILL = os.path.join(KOK, "plugins", AD, "skills", AD)
CIKTI = os.path.join(KOK, "dist", f"{AD}.zip")

os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
sayi = 0
with zipfile.ZipFile(CIKTI, "w", zipfile.ZIP_DEFLATED) as z:
    for kok, klasorler, dosyalar in os.walk(SKILL):
        klasorler[:] = [k for k in klasorler if k != "__pycache__"]
        for ad in sorted(dosyalar):
            if ad.endswith((".pyc", ".tmp")):
                continue
            yol = os.path.join(kok, ad)
            z.write(yol, os.path.join(AD, os.path.relpath(yol, SKILL)))
            sayi += 1
print(f"{CIKTI} ({sayi} dosya, {os.path.getsize(CIKTI) // 1024} KB)")
