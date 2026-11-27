# antitrust-investigator — Rekabet İhlali İnceleme skill'i

[English README](README.md)

Kurumsal e-posta, Teams, SharePoint/OneDrive ve dosya sunucusu kayıtlarını **yetkili bir inceleme kapsamında** rekabet hukuku açısından tarayan bir Claude skill'i. Kaynaklı risk göstergeleri ve hukuk ekibi için rapor üretir. İhlal kararı vermez.

- **Odaklı tarama:** Verilen konu, anahtar kelime, rakip ve proje adlarına odaklanır. Türkçe, İngilizce ve Rusça yazışmalarda çalışır.
- **Kaynaklı değerlendirme:** Her bulgu `references/kontroller.csv` içindeki bir kontrole (FYT, IHL, PZR, BLG, IK, DKY, HD, JV, BD, DL, ALG) ve `references/kaynaklar.csv` içindeki bir hukuk kaynağına bağlanır.
- **Güncel kalma:** Katalogda eksik ya da eski kalan bir kaynak varsa yalnız resmî sitelerden bakar. Bulduğu kaynağı "hukuk onayı yok" diye işaretler ve kataloğa eklenecek komutu hazırlar.
- **Vaka defteri ve okuma kanıtı:** Her belge yaklaşık 3000 karakterlik parçalara bölünür. Her parça gösterildiğinde tek kullanımlık bir onay kodu alır ve yalnız o kodla işaretlenebilir. Üç gösterge ayrı tutulur: kuyruk, okuma kapsamı ve sinyal kararı. Biri eksikse rapor **KISMİ** damgası taşır. Avukat yazışması ve kapsam dışı içerik metne çevrilmeden ayrılır.
- **İddia yapısıyla bulgu doğrulaması:** Bulgu kim, hangi eylem (teklif, ret, kabul…), neyi, kime ve hangi alıntıyla sorularına cevap veren bir iddia listesidir. Aşağıdaki bulgular reddedilir:
  - Başlığı "anlaştılar" deyip yalnız teklif gösteren bulgu.
  - Ret içeren alıntıyı kabulün kanıtı yapan bulgu.
  - Okunmamış parçadan alıntı yapan, katalogda olmayan kaynağa ya da var olmayan maddeye dayanan bulgu.
  - İhbarcının adını içeren bulgu.
- **Örtülü dil:** "Her zamanki gibi", "malum konu", "sıra sizde" gibi ifadeler için dayanaklı bir hipotez kurulur. Defter, ifadenin daha önce okunmuş geçişlerini yeniden okumaya açar (geri tarama). Yalnız hipoteze dayanan bulgu `risk_signal` olamaz.
- **Okuyucular:** PST/OST, arşivler, OpenDocument, RTF, eski .doc/.xls/.ppt dosyaları, taranmış görseller ve PDF sayfaları (Türkçe/İngilizce/Rusça OCR) okunur. Yanlış dil modeliyle üretilmiş anlamsız OCR çıktısı kayda alınmaz.
- **İhale verisi taraması:** Teklif tablosunda kodla hesaplanan işaretler:
  - kazanan rotasyonu,
  - sabit fiyat farkı,
  - olağandışı yakın teklif,
  - hep az farkla kaybeden firma,
  - tekrarlanan çekilme,
  - **değişkenlik kırılması** (teklif dağılımının bir dönemde daralması).

  Kırılma taraması gerçek kartel verisiyle doğrulandı: Imhof ve Wallimann (2021), İsviçre, İtalya ve Japonya. Kamu ihalesinde 4734 ve TCK m.235 paralel riski ayrıca belirtilir.
- **Bağımsız hat ve ihbarcı koruması:** İddia üst yönetimi veya talep edenin hattını kapsıyorsa raporu onlara değil, Denetim Komitesi ya da bağımsız müşavire yönlendirir. İhbarcı kimliğini rapora koymaz.
- **Güvenlik:** Salt okunur çalışır. Belge içindeki talimatları uygulamaz. Avukat yazışmalarını ve kişisel hesapları ayırır. Web aramalarına şirket içi bilgi koymaz.

> Bu repo gerçek inceleme verisi içermez ve içermemelidir. `evals/` ve `tests/veri/` altındaki yazışmaların tamamı sentetiktir. Tek istisna `tests/veri/pst/dist-list.pst`: java-libpst projesinin (Apache-2.0) yayımladığı, kişisel veri içermeyen küçük bir test dosyası.

## Repo yapısı

```
.
├── .claude-plugin/marketplace.json          Claude Code marketplace tanımı
├── plugins/rekabet-ihlali-inceleme/
│   ├── .claude-plugin/plugin.json           plugin bilgisi ve sürüm
│   ├── README.md / LICENSE                  dizin listesi için eklenti açıklaması ve lisans
│   └── skills/rekabet-ihlali-inceleme/      ← skill'in kendisi (claude.ai'ye yüklenen klasör)
│       ├── SKILL.md
│       ├── scripts/rekabet_tarama.py        ön-tarama betiği
│       ├── scripts/vaka.py                  vaka defteri: okuma kanıtı, bulgu doğrulama, geri tarama, rapor
│       ├── scripts/okuyucular.py            PST, OCR, arşiv, ODF, RTF, eski Office okuyucuları
│       ├── scripts/ihale_analiz.py          teklif verisi taraması (değişkenlik kırılması dahil)
│       ├── scripts/kaynak_yonet.py          kaynak ekleme / doğrulama
│       └── references/
│           ├── kaynaklar.csv                62 kaynak
│           ├── kontroller.csv               147 kontrol
│           ├── arama_ipuclari.csv           TR/EN/RU arama ipuçları
│           ├── bulgu_semasi.json            bulgu çıktı şeması (v1.2)
│           ├── okuma_protokolu.md           vaka defteri ve üç gösterge
│           ├── bulgu_dogrulama.md           iddia yapısı ve ret nedenleri
│           ├── ortulu_dil.md                örtülü dil yöntemi ve geri tarama
│           └── metinler/                    (isteğe bağlı) kaynak metinleri
├── evals/                                   8 test senaryosu (47 kontrol)
├── tests/                                   testler, sentetik örnekler, örnek PST, kartel verisi doğrulaması
├── tools/paketle.py                         claude.ai zip'ini üretir
└── .github/workflows/dogrula.yml            her PR'da test, her sürüm etiketinde zip
```

## Kurulum

### claude.ai (web, masaüstü, mobil)

1. [Releases](https://github.com/savsay/antitrust-investigator/releases/latest) sayfasından `rekabet-ihlali-inceleme.zip` dosyasını indirin. Ya da `python3 tools/paketle.py` ile kendiniz üretin; dosya `dist/` altına yazılır.
2. **Kişisel kullanım:** Customize > Skills > Upload a skill ile zip'i yükleyin.
3. **Tüm kuruma dağıtım (Team/Enterprise sahibi):** Organization settings > Plugins & skills > Add > Upload a skill ile zip'i yükleyin. Skill herkese açılır; kullanıcılar tek tek kapatabilir.
4. **Belirli kişilerle paylaşım:** Yüklediğiniz skill'i Customize > Skills üzerinden kişilerle veya gruplarla paylaşın. Bu, kurumunuzda "Skill sharing" açıksa çalışır.

Skill'in çalışması için kurumda **Code execution and file creation** ve **Skills** açık olmalıdır.

### Claude dizini

Eklenti Claude dizinine (Claude'da Customize sayfası) **Antitrust Investigator** adıyla gönderildi; incelemeden geçince oradan tek tıkla eklenebilir. Dizine giden kopya `directory/` klasöründedir: aynı skill, katalog JSON ve ihale betiği Markdown içinde, çünkü dizin bireysel yayıncılardan yalnız metin dosyası kabul ediyor. Bu klasör `python3 tools/dizin_surumu.py` ile üretilir.

### Claude Code

```bash
claude plugin marketplace add savsay/antitrust-investigator      # GitHub owner/repo
claude plugin install rekabet-ihlali-inceleme@antitrust-investigator
```

Özel (private) repo için kullanıcının GitHub erişimi olmalıdır. Güncellemeler `plugin.json` içindeki `version` artırıldığında gelir.

## Kullanım örnekleri

- "Kapsam HK-2026-014: ekteki Purview export'unda 2025 Ankara Metro ihalesiyle ilgili rakip yazışmalarını incele."
- "SharePoint'teki teklif klasörünü ihale danışıklılığı açısından tara; Rakip Yapı ve Konya projesine odaklan."
- "İç Denetim, kapsam HK-2026-040: ekteki teklifler.csv'de son bir yılın ihale sonuçları var. Danışıklılık işareti var mı, hangi firma ve ihalelere bakalım?"
- "Rekabet Kurumu'nun yeni hâkim durum kılavuzunu kaynak kataloğuna ekle."

## Roller

| Rol | Görev |
|---|---|
| Hukuk / Uyum (program sahibi) | Yetki, kapsam, bulgu kararı, raporun dağıtımı |
| İç Denetim | Süreç ve kontrol bulguları, ihale verisi analizi; hukuki nitelendirme yapmaz |
| BT / eDiscovery | Purview araması, muhafaza, dışa aktarma, hash; içerik yorumlamaz |
| Denetim Komitesi / bağımsız müşavir | Üst yönetim veya talep edenin hattı iddia kapsamındaysa raporun muhatabı |
| İK | Yalnız iş gücü kontrolleri için ücret ve işe alım verisi |

## 90 günlük yaygınlaştırma

| Gün | Adım |
|---|---|
| 1–30 | Kapanmış bir dosyada pilot; hukuk 50–100 mesajı etiketler ve skill'in kuyruğuyla karşılaştırılır. Roller, bağımsız hat ve dağıtım netleşir |
| 31–60 | Kurum politikaları ve jargon (proje kodları, rakip lakapları) eklenir; C örneklem oranı ve ihale eşikleri sektöre göre ayarlanır. Her insan kararı (`doğrulandı` / `çürütüldü` / `yeterli kanıt yok`) takip tablosuna yazılır |
| 61–90 | Canlı dosyalarda Purview dışa aktarımlarıyla kullanılır; kapanan bulgularla her ay isabet gözden geçirilir, kaynak kataloğu hukuk onayından sonra güncellenir |

## Kaynak ekleme

Kısaca şu komutla eklenir:

```bash
python3 plugins/rekabet-ihlali-inceleme/skills/rekabet-ihlali-inceleme/scripts/kaynak_yonet.py ekle \
  --onek TR --baslik "..." --kurum "Rekabet Kurumu" --bolge Turkiye --surum "..." --tur Kılavuz \
  --amac "..." --url "https://www.rekabet.gov.tr/..." --kontroller "HD-03,DKY-05"
```

Ayrıntılar ve kontrol, ipucu ve sözlük ekleme için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

## Sınırlar

- Çıktılar risk göstergesidir, hukuki görüş değildir. Değerlendirme yetkili hukuk ekibine aittir.
- Katalogdaki kaynakların hukuk onayı `Bekliyor` durumundadır.
- Çalışan iletişiminin incelenmesi için hukuki dayanak ve aydınlatma (KVKK) kurum tarafından sağlanmalıdır.
- İhale taraması uyarıları kanıt değil okuma önceliğidir; dar fiyat bandı olan sektörlerde eşikler düşürülmelidir.
- Ön-tarama betiği sentetik örneklerle ve rekabet ihlali içermeyen gerçek bir iş posta kutusuyla (Enron, 141 öğe) test edilmiştir. Gerçek verideki isabet oranı, hukukça etiketlenmiş örneklerle ayrıca ölçülmelidir.
- Değişkenlik kırılması taraması kısa serilerde (12 ihaleden az) çalışmaz; İsviçre etkisi büyüklüğünde 20 ihalelik bir seride yakalama oranı yaklaşık %60'tır. Uyarı bir okuma önceliğidir.
- Vaka defterindeki onay kodu bir parçanın açıldığını kanıtlar, okumanın kalitesini kanıtlamaz; her işaret bu yüzden bir karar ve gerektiğinde gerekçe ister.

## Lisans

[MIT](LICENSE). Çıktılar hukuki görüş değildir; kullanım sorumluluğu kullanana aittir.
