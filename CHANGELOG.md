# Değişiklik günlüğü

## 1.2.0 — 2026-11-26

- **İhale verisi taraması:** `scripts/ihale_analiz.py` (yalnız standart kütüphane). Kazanan rotasyonu, sabit teklif farkı, olağandışı yakın/aynı teklif, hep az farkla kaybeden profil ve çekilme sonrası kazanma; her uyarı kontrol kimliği, metrik ve alternatif açıklama taşır. 500 rastgele rekabetçi pazarda %7–9 yanlış alarm, sentetik halkada %100 yakalama.
- **Kaynaklar (50 → 61):** 4734 sayılı KİK ve TCK m.235–236, Aktif İşbirliği, Uzlaşma ve İdari Para Cezaları yönetmelikleri, World Bank Fraud and Corruption Awareness Handbook, DOJ ECCP (2024), IIA Global Internal Audit Standards, ISO 37301 / 37002 / 37008.
- **Kontroller (140 → 147):** IHL-09 kamu ihalesinde paralel risk (Acil), IHL-10 istatistiksel göstergenin belgeyle desteklenmesi, HM-21 olay tarihindeki politika sürümü, MT-25 özgün dilde alıntı + çeviri, MT-26 sayıların kodla hesaplanması, OP-17 bağımsız raporlama hattı, OP-18 ihbarcı kimliğinin korunması.
- SKILL.md: roller tablosu, varsayılan ayarlar, üst yönetim iddiasında bağımsız hat, ihbarcı koruması, kurum içi politika katmanı, etki / aciliyet / kanıt yeterliliği ekseni, takip tablosunda yalnız insanın doldurduğu sonuç sütunu.
- Bulgu şeması v1.1 (v1 ile uyumlu): isteğe bağlı `assessment`, `parallel_exposure`, `escalation_route`, `data_screens`, kanıtta `language` / `translation`.
- 3 yeni test senaryosu (üst yönetim iddiası, teklif verisi taraması, Rusça yazışma); toplam 6 senaryo, 33 kontrol. 4 yeni birim testi.
- README: roller, 90 günlük yaygınlaştırma planı, güncel sayılar, yol haritası.

## 1.1.0 — 2026-11-26

- Repo `savsay/antitrust-investigator` olarak açıldı: İngilizce README, MIT lisansı, issue ve PR şablonları.

- Skill, kaynak kataloğunu kendi `references/` klasöründen okuyor: 50 kaynak, 140 kontrol, TR/EN/RU arama ipuçları, bulgu şeması.
- `scripts/kaynak_yonet.py` eklendi: kaynak ekleme, kontrollere bağlama, katalog doğrulama.
- Web'den bulunan kaynaklar için öneriler artık hazır `kaynak_yonet.py ekle` komutu olarak geliyor.
- İnceleme raporu hem Claude dokümanı hem Word (.docx) olarak üretiliyor.
- Claude Code marketplace, GitHub Actions testleri ve claude.ai zip paketlemesi eklendi.

## 1.0.0 — 2026-11-26

- İlk sürüm. Kapsam kapısı, bilgi tabanı hiyerarşisi, Purview KQL örnekleri, 60 rekabet kontrolü, kavram tabanlı ön-tarama betiği, Bulgu_Semasi v1 çıktısı, 3 test senaryosu.
