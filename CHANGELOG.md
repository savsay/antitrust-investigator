# Değişiklik günlüğü

## 1.3.0 — 2026-11-27

- **Vaka defteri (`scripts/vaka.py`, yalnız standart kütüphane):**
  - Yetki kapısı: yetki, amaç ve kapsam olmadan vaka açılmaz ve vaka dosyası oluşmaz.
  - Kısıtlı içerik (avukat alan adı, gizlilik ibaresi, kapsam dışı desen) metne çevrilmeden ayrılır; ekleri ve alt öğeleri de ayrılır.
  - Belgeler yaklaşık 3000 karakterlik parçalara bölünür; her parça gösterildiğinde tek kullanımlık bir onay kodu alır.
  - Üç ayrı gösterge (kuyruk, okuma kapsamı, sinyal kararı); biri eksikse rapor KISMİ damgası taşır.
  - Rastgele örneklem ve Wilson güven aralığı, paralel okuyucular (`--isci`), SHA-256 ile kaynak bütünlüğü denetimi.
  - Okunamayan belgeyi gerekçeyle kapatmak için `belge-coz`.
- **Bulgu doğrulaması:** Bulgu bir iddia listesidir (kim · eylem · neyi · kime · kanıt). Teklif, ret ve kabul ayrımı denetlenir. Aşağıdakiler reddedilir:
  - Ret içeren alıntıyı kabulün dayanağı yapmak.
  - "Anlaştılar" diyen ama yalnız teklif gösteren başlık.
  - Okunmamış parçadan alıntı; katalogda olmayan kaynak; 4054 sayılı Kanun'da bulunmayan madde (1–65, geçici 1–7).
  - İhbarcı adı; bağımsız hat gerektiren durumda yönlendirmenin eksik olması.
  - Koşullu kabulü ya da aktarılan anlatımı başlıkta belirtmemek.
  - Bütün iddiaları belirsiz olan bir `risk_signal`.
- **Örtülü dil:** Dayanaklı kod hipotezi (`kod-ekle`) ve geri tarama: hipotez daha önce okunmuş geçişleri yeniden açar. Ön taramaya ORTULU kavramı eklendi; tek başına kuyruğa almaz, karşı tarafla birlikte B, temayla birlikte A olur. Yöntem `references/ortulu_dil.md`'de.
- **Okuyucular (`scripts/okuyucular.py`):** PST/OST (readpst), zip-slip korumalı arşivler, OpenDocument, RTF, eski .doc/.xls/.ppt (catdoc), uzantısız eklerin içerikten tanınması, taranmış görsel ve metinsiz PDF sayfası OCR'ı (tur+eng+rus). Anlamsız OCR çıktısı kayda alınmaz.
- **Değişkenlik kırılması taraması (`ihale_analiz.py`, IHL-10):** Teklif CV serisinde permütasyon testi ve seriler arası Benjamini-Hochberg düzeltmesi; her dönemde en az 6 ihale ve 1,5 kat oran aranır. Her ihalenin CV'si `ihale_cv.csv`'ye yazılır.
- **Gerçek kartel verisiyle doğrulama (`tests/kartel_dogrulama.py`):** Imhof ve Wallimann (2021) verisi; İsviçre, İtalya ve Japonya için CV AUC'si 0,91 / 0,85 / 0,74. Veri CI'da indirilir ve SHA-256 ile doğrulanır; depoya girmez. Kaynak INT-02 olarak kataloğa eklendi (62 kaynak).
- **Düzeltme:** Ön taramada `zam` kalıbı "zaman" kelimesini de yakalıyordu ("her zamanki gibi" FIYAT sayılıyordu); düzeltildi.
- **Bulgu şeması v1.2:** Zorunlu alanlar değişmedi. İsteğe bağlı yeni alanlar: `title`, `area`, `claims`, `coded_language` ve kanıtta `role`. Vaka raporu bu şemaya karşı test edilir.
- **Testler:**
  - `tests/test_vaka.py`: yetki kapısı, onay kodları, bulgu reddi nedenleri, geri tarama, KISMİ damgası, bütünlük, dizin sürümü uçtan uca, OCR, PST.
  - PST testleri iki dış projenin test dosyalarıyla yapılır (java-libpst dist-list.pst, pst-extractor enron.pst); beklenen değerler o projelerin kendi testlerinden alınmıştır.
  - 9 yeni sentetik örnek (69).
  - 2 yeni değerlendirme senaryosu: teklif/ret/koşullu kabul ayrımı ve örtülü dil ile geri tarama. Toplam 8 senaryo, 47 kontrol.
- **Claude dizini sürümü:** `vaka.py` ve `okuyucular.py` Markdown içinde gelir; katalog JSON'dan okunur (`REKABET_REF`).

## 1.2.0 — 2026-11-26

- **İhale verisi taraması:** `scripts/ihale_analiz.py` (yalnız standart kütüphane). Kazanan rotasyonu, sabit teklif farkı, olağandışı yakın/aynı teklif, hep az farkla kaybeden profil ve çekilme sonrası kazanma; her uyarı kontrol kimliği, metrik ve alternatif açıklama taşır. 500 rastgele rekabetçi pazarda %7–9 yanlış alarm, sentetik halkada %100 yakalama.
- **Kaynaklar (50 → 61):** 4734 sayılı KİK ve TCK m.235–236, Aktif İşbirliği, Uzlaşma ve İdari Para Cezaları yönetmelikleri, World Bank Fraud and Corruption Awareness Handbook, DOJ ECCP (2024), IIA Global Internal Audit Standards, ISO 37301 / 37002 / 37008.
- **Kontroller (140 → 147):** IHL-09 kamu ihalesinde paralel risk (Acil), IHL-10 istatistiksel göstergenin belgeyle desteklenmesi, HM-21 olay tarihindeki politika sürümü, MT-25 özgün dilde alıntı + çeviri, MT-26 sayıların kodla hesaplanması, OP-17 bağımsız raporlama hattı, OP-18 ihbarcı kimliğinin korunması.
- SKILL.md: roller tablosu, varsayılan ayarlar, üst yönetim iddiasında bağımsız hat, ihbarcı koruması, kurum içi politika katmanı, etki / aciliyet / kanıt yeterliliği ekseni, takip tablosunda yalnız insanın doldurduğu sonuç sütunu.
- Bulgu şeması v1.1 (v1 ile uyumlu): isteğe bağlı `assessment`, `parallel_exposure`, `escalation_route`, `data_screens`, kanıtta `language` / `translation`.
- 3 yeni test senaryosu (üst yönetim iddiası, teklif verisi taraması, Rusça yazışma); toplam 6 senaryo, 33 kontrol. 4 yeni birim testi.
- README: roller, 90 günlük yaygınlaştırma planı, güncel sayılar, yol haritası.
- Claude dizinine gönderim için: eklenti klasörüne İngilizce README, LICENSE ve 512 px ikon; `displayName` "Antitrust Investigator"; ikili test dosyaları kurulan pakete girmesin diye `evals/` repo köküne taşındı.

## 1.1.0 — 2026-11-26

- Repo `savsay/antitrust-investigator` olarak açıldı: İngilizce README, MIT lisansı, issue ve PR şablonları.

- Skill, kaynak kataloğunu kendi `references/` klasöründen okuyor: 50 kaynak, 140 kontrol, TR/EN/RU arama ipuçları, bulgu şeması.
- `scripts/kaynak_yonet.py` eklendi: kaynak ekleme, kontrollere bağlama, katalog doğrulama.
- Web'den bulunan kaynaklar için öneriler artık hazır `kaynak_yonet.py ekle` komutu olarak geliyor.
- İnceleme raporu hem Claude dokümanı hem Word (.docx) olarak üretiliyor.
- Claude Code marketplace, GitHub Actions testleri ve claude.ai zip paketlemesi eklendi.

## 1.0.0 — 2026-11-26

- İlk sürüm. Kapsam kapısı, bilgi tabanı hiyerarşisi, Purview KQL örnekleri, 60 rekabet kontrolü, kavram tabanlı ön-tarama betiği, Bulgu_Semasi v1 çıktısı, 3 test senaryosu.
