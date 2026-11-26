# Katkı rehberi

Skill'in bilgi tabanı dört dosyadan oluşur. Hepsi `plugins/rekabet-ihlali-inceleme/skills/rekabet-ihlali-inceleme/references/` altındadır:

| Dosya | Ne tutar | Nasıl genişletilir |
|---|---|---|
| `kaynaklar.csv` | Hukuk kaynakları: kanun, kılavuz, karar, duyuru | `scripts/kaynak_yonet.py ekle` |
| `kontroller.csv` | Kontroller: soru, risk göstergesi, gerekli kanıt, karşı kontrol, kaynak kimlikleri | Satır ekle; `source_ids` mevcut kaynaklara bağlanmalı |
| `arama_ipuclari.csv` | TR/EN/RU arama ifadeleri | Satır ekle |
| `metinler/<ID>.txt` | Kaynağın düz metni (isteğe bağlı) | Dosya ekle; yeniden kullanım hakkını kontrol et |

Dosyaların sütunları, kaynak paketindeki `Kaynak_Envanteri.csv` ve `Kontrol_Katalogu.csv` ile aynıdır. Paketten satır kopyalamak bu yüzden sorunsuzdur.

## 1. Yeni hukuk kaynağı eklemek

```bash
cd plugins/rekabet-ihlali-inceleme/skills/rekabet-ihlali-inceleme
python3 scripts/kaynak_yonet.py ekle \
  --onek TR \
  --baslik "Hâkim Durumdaki Teşebbüslerin Dışlayıcı Davranışları Kılavuzu" \
  --kurum "Rekabet Kurumu" --bolge Turkiye \
  --surum "Kurul kararı tarihi / sayısı" --tur Kılavuz \
  --amac "Sadakat indirimi, münhasırlık, dışlama analizi" \
  --url "https://www.rekabet.gov.tr/..." \
  --kontroller "HD-03,DKY-05"
python3 scripts/kaynak_yonet.py dogrula
```

Komut şunları yapar:

- `--onek TR` verildiğinde sıradaki boş kimliği seçer (ör. `TR-15`). Kimliği kendiniz vermek için `--id TR-15` kullanın.
- Kaynağı `legal_approval=Bekliyor` ile ekler.
- `--kontroller` ile verilen kontrollerin `source_ids` alanına yeni kimliği işler.
- URL resmî alan adı listesinde değilse uyarır: rekabet.gov.tr, mevzuat.gov.tr, resmigazete.gov.tr, kvkk.gov.tr, europa.eu, justice.gov, ftc.gov, gov.uk, oecd.org, fas.gov.ru ve diğerleri.

Skill de bunu üretebilir: Claude'a "şu kılavuzu kaynaklara ekle" deyin, size hazır `ekle` komutunu verir.

**Yeni bir ülke için** (ör. Rusya): `--onek RU --bolge Rusya` kullanın. Skill o ülkeyi kapsam olarak gördüğünde bu kaynakları kullanır.

**Hukuk onayı verildiğinde:** `kaynaklar.csv` içinde ilgili satırın `legal_approval` alanını `Onaylandı` yapın. `note` alanına onaylayanı ve tarihi yazın.

## 2. Kontrol eklemek

`kontroller.csv` dosyasına bir satır ekleyin. Kimlik, ailenin önekiyle sıradaki numara olmalı (ör. `IHL-11`). `source_ids` alanı `; ` ile ayrılmış kaynak kimlikleri içerir ve hepsi `kaynaklar.csv` içinde bulunmalıdır. `dogrula` bunu denetler.

Yeni bir risk ailesi eklerseniz SKILL.md'deki bölüm 6 özetine de bir satır ekleyin.

## 3. Arama sözlüğünü genişletmek

- **İnsan okuması ve Purview sorguları için:** `arama_ipuclari.csv` dosyasına satır ekleyin.
- **Ön-tarama betiği için:** `scripts/rekabet_tarama.py` içindeki `K` sözlüğüne kök ekleyin. Kökleri küçük harf ve ASCII yazın (`ş`→`s`, `ı`→`i`); betik Türkçe ve Kiril harfleri kendisi katlar.
- Betiği değiştirdiyseniz **SKILL.md bölüm 11'deki kopyayı da aynı yapın**. Test iki kopyanın birebir aynı olmasını ister, çünkü tek dosya olarak kurulan skill gömülü kopyayı kullanır.

## 4. İhale taramasını geliştirmek

`scripts/ihale_analiz.py` yalnız standart kütüphaneyle çalışır ve tek dosya kurulumda gömülü kopyası yoktur. Yeni bir tarama eklerken:

- `tara()` içine bir blok ekleyin; her uyarı bir kontrol kimliği (`IHL-…`), ölçülen metrik ve **alternatif açıklama** taşımalı.
- Eşiği komut satırı seçeneği yapın ve varsayılanı `SKILL.md` bölüm 5'e yazın.
- `tests/test_skill.py` içindeki rastgele rekabetçi pazar testinin yanlış alarm sınırı (%12) geçilmemeli; sentetik halka (`tests/veri/ihale_ornek.csv`) yakalanmaya devam etmeli. Gerçek ihale verisini repoya koymayın.

## 5. Test ve sürüm

```bash
python3 tests/test_skill.py      # frontmatter, betik eşliği, ad tutarlılığı, katalog, 60 sentetik örnek, ihale taraması
python3 tools/paketle.py         # dist/rekabet-ihlali-inceleme.zip
```

Sürüm çıkarmak için:

1. `plugins/rekabet-ihlali-inceleme/.claude-plugin/plugin.json` içindeki `version` alanını artırın.
2. `CHANGELOG.md` dosyasına not düşün.
3. PR açın; GitHub Actions testleri çalıştırır.
4. Birleştirdikten sonra etiketleyin: `git tag v1.2.0 && git push --tags`. Actions zip'i Releases sayfasına ekler.
5. claude.ai'de kurum geneline dağıtıldıysa: kurum sahibi eski skill'i kaldırıp yeni zip'i yükler. Claude Code kullanıcıları yeni sürümü otomatik alır.

## Asla repoya eklemeyin

Gerçek e-posta, belge, PST/MSG dışa aktarımı, çalışan adı, inceleme bulgusu veya rapor eklemeyin. Kaynak PDF'leri de eklemeyin; bağlantılar katalogda durur. `.gitignore` bunların çoğunu engeller, ama son kontrol sizdedir.
