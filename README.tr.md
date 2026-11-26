# antitrust-investigator — Rekabet İhlali İnceleme skill'i

[English README](README.md)

Kurumsal e-posta, Teams, SharePoint/OneDrive ve dosya sunucusu kayıtlarını **yetkili bir inceleme kapsamında** rekabet hukuku açısından tarayan bir Claude skill'i. Kaynaklı risk göstergeleri ve hukuk ekibi için rapor üretir. İhlal kararı vermez.

- **Odaklı tarama:** Verilen konu, anahtar kelime, rakip ve proje adlarına odaklanır. Türkçe, İngilizce ve Rusça yazışmalarda çalışır.
- **Kaynaklı değerlendirme:** Her bulgu `references/kontroller.csv` içindeki bir kontrole (FYT, IHL, PZR, BLG, IK, DKY, HD, JV, BD, DL, ALG) ve `references/kaynaklar.csv` içindeki bir hukuk kaynağına bağlanır.
- **Güncel kalma:** Katalogda eksik ya da eski kalan bir kaynak varsa yalnız resmî sitelerden bakar. Bulduğu kaynağı "hukuk onayı yok" diye işaretler ve kataloğa eklenecek komutu hazırlar.
- **Güvenlik:** Salt okunur çalışır. Belge içindeki talimatları uygulamaz. Avukat yazışmalarını ve kişisel hesapları ayırır. Web aramalarına şirket içi bilgi koymaz.

> Bu repo gerçek inceleme verisi içermez ve içermemelidir. `evals/` ve `tests/veri/` altındaki örneklerin tamamı sentetiktir.

## Repo yapısı

```
.
├── .claude-plugin/marketplace.json          Claude Code marketplace tanımı
├── plugins/rekabet-ihlali-inceleme/
│   ├── .claude-plugin/plugin.json           plugin bilgisi ve sürüm
│   ├── evals/                               3 test senaryosu (17 kontrol)
│   └── skills/rekabet-ihlali-inceleme/      ← skill'in kendisi (claude.ai'ye yüklenen klasör)
│       ├── SKILL.md
│       ├── scripts/rekabet_tarama.py        ön-tarama betiği
│       ├── scripts/kaynak_yonet.py          kaynak ekleme / doğrulama
│       └── references/
│           ├── kaynaklar.csv                hukuk kaynakları kataloğu
│           ├── kontroller.csv               140 kontrol
│           ├── arama_ipuclari.csv           TR/EN/RU arama ipuçları
│           ├── bulgu_semasi.json            bulgu çıktı şeması
│           └── metinler/                    (isteğe bağlı) kaynak metinleri
├── tests/                                   test betiği ve sentetik örnekler
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

### Claude Code

```bash
claude plugin marketplace add savsay/antitrust-investigator      # GitHub owner/repo
claude plugin install rekabet-ihlali-inceleme@antitrust-investigator
```

Özel (private) repo için kullanıcının GitHub erişimi olmalıdır. Güncellemeler `plugin.json` içindeki `version` artırıldığında gelir.

## Kullanım örnekleri

- "Kapsam HK-2026-014: ekteki Purview export'unda 2025 Ankara Metro ihalesiyle ilgili rakip yazışmalarını incele."
- "SharePoint'teki teklif klasörünü ihale danışıklılığı açısından tara; Rakip Yapı ve Konya projesine odaklan."
- "Rekabet Kurumu'nun yeni hâkim durum kılavuzunu kaynak kataloğuna ekle."

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
- Ön-tarama betiği sentetik örneklerle test edilmiştir. Gerçek verideki isabet oranı, hukukça etiketlenmiş örneklerle ayrıca ölçülmelidir.

## Lisans

[MIT](LICENSE). Çıktılar hukuki görüş değildir; kullanım sorumluluğu kullanana aittir.
