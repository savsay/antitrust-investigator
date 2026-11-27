# Örtülü dil: hipotez kurma ve geri tarama

Rakiple koordinasyon nadiren açık yazılır. Taraflar konuyu adlandırmadan ortak bilgiye yaslanır: "malum konu", "her zamanki gibi", "bu sefer sıra onlarda", birimi olmayan bir sayı ("12 olsun"), ya da işle ilgisi olmayan bir takma ad ("bahçe işi"). Anahtar kelime taraması bu cümleleri ya hiç bulmaz ya da sıradan iş dilinden ayıramaz. Bu belge, böyle ifadelerin nasıl ele alınacağını anlatır.

Temel kural: **bir ifadenin ne anlama geldiğini incelemeci belirlemez.** Yalnızca bir hipotez kurar, hipotezin dayanağını yazar ve hipotezin doğru olup olmadığını başka belgelerle sınar. Hipotez hiçbir zaman tek başına bulgu olmaz.

## 1. Neye bakılır

| Görünüm | Örnek | Neden dikkat çeker |
|---|---|---|
| Ortak bilgiye gönderme | "malum konu", "konuştuğumuz gibi", "as discussed", "тот самый вопрос" | Konu metinde yok; okuyucu ne olduğunu zaten biliyor |
| Yerleşik düzen | "her zamanki gibi", "eski usul", "as usual", "как обычно" | Tekrarlanan bir uygulamaya işaret edebilir |
| Sıra ve pay dili | "sıra sizde", "bu sefer biz", "your turn", "наша очередь" | İhalede dönüşümlü kazanma ya da müşteri paylaşımıyla örtüşebilir |
| Birimsiz sayı | "12 olsun", "8'in altına inmeyin" | Fiyat, iskonto ya da teklif farkı adı verilmeden konuşuluyor olabilir |
| İşle ilgisiz ad | "bahçe işi", "düğün", "maç" | Satış ya da ihale yazışmasında yeri yoksa takma ad olabilir |
| Kanal değiştirme | "detayları yüz yüze", "in person", "при встрече" | Yazılı iz bırakmama isteği (gizleme diliyle birlikte değerlendirilir) |

Bu ifadelerin çoğu günlük iş yazışmasında masumdur. Ön tarama (`rekabet_tarama.py`) bu yüzden ORTULU kavramını **tek başına kuyruğa almaz**. Yalnızca karşı tarafla (TARAF) ya da gizleme diliyle (GIZLEME) birlikte geçtiğinde B seviyesine alır; bir rekabet temasıyla da birlikte geçiyorsa A seviyesine çıkarır. Doğrulama: rekabet ihlali içermeyen gerçek bir iş posta kutusunda (Enron örneği, 141 öğe) ORTULU kavramı hiçbir yanlış alarm eklememiştir.

## 2. Hipotez kaydı

Okuma sırasında örtülü görünen bir ifade bulunca, ifadeyi yorumlamadan önce vaka defterine bir kod hipotezi olarak kaydedin:

```bash
python3 scripts/vaka.py kod-ekle VAKA --ifade "bahçe işi" \
  --hipotez "ihale ya da proje paketi" \
  --dayanak "satış yazışmasında bahçe ile ilgili bir iş yok; cümlede paylaşım dili var (bu ay sizde, biz yanaşmıyoruz)" \
  --parca B0005-P001
```

- `--dayanak` boş ya da çok kısa olamaz. "Şüpheli görünüyor" dayanak değildir. Dayanak, ifadenin neden olağan anlamında okunamadığını ve hangi bağlamın başka bir anlam önerdiğini söyler.
- Bir ifade için birden çok hipotez kurulabilir. Her biri ayrı kayıttır.
- `vaka.py hafiza VAKA` kurulan tüm hipotezleri, dayanaklarını ve geçtikleri parçaları listeler. Paralel okuyucular (alt ajanlar) işe başlamadan önce bu listeyi okur.

## 3. Geri tarama

Hipotez kaydedildiği anda defter, ifadenin geçtiği **daha önce okunmuş** parçaları otomatik bulur ve yeniden okunmak üzere açar (`durum='yeniden'`). Neden: ilk okumada "bahçe işi" sıradan bir ifade gibi geçilmiş olabilir. Hipotez bir kez kurulduktan sonra aynı ifadenin önceki geçişleri yeni bir gözle okunmalıdır.

```bash
python3 scripts/vaka.py sonraki VAKA --yeniden      # yeniden açılan parçalar, neden açıldıkları yazılı olarak
```

Yeniden açılan parçalar kuyruk göstergesini EKSİK'e düşürür; hepsi yeniden işaretlenmeden rapor tam sayılmaz. Hipotez kurulmadan önce henüz okunmamış parçalarda ifade geçerse, okuyucu parçayı gösterirken hipotezi de görür.

Aramayla da geri taranabilir: `vaka.py ara VAKA "sıra (sizde|onlarda)" --duzenli --yeniden-ac`.

## 4. Hipotezi sınama

Bir hipotez ancak dışarıdan bir olguyla örtüşürse güçlenir. Bakılacaklar:

- **Zaman eşleşmesi:** İfadenin geçtiği tarih ile ihale, fiyat listesi değişikliği ya da müşteri kaybı tarihleri yakın mı? Teklif verisi varsa `ihale_analiz.py` çıktısındaki rotasyon ve değişkenlik kırılması dönemleriyle karşılaştırın.
- **Tutarlılık:** İfade farklı kişiler arasında aynı anlamla kullanılıyor mu? Hipotez her geçişte anlamlı mı, yoksa bazı geçişlerde açıkça olağan anlamında mı?
- **Masum açıklama:** İfadenin iş içinde bilinen bir karşılığı var mı (gerçek bir peyzaj işi, bir proje kod adı)? Varsa hipotez zayıflar; bunu kayda yazın.

## 5. Bulguya taşıma

Örtülü dile dayanan bir iddia bulguya girerse:

- İddiada `"belirsiz": true` işaretlenir; dayanılan hipotezler `"kod_hipotezleri": ["K-001"]` alanına yazılır (defterde olmayan kimlik reddedilir). Raporda ve `bulgular.json` içinde `coded_language` olarak ifadesi, hipotezi ve dayanağıyla görünür.
- Bütün iddiaları belirsiz olan bulgu `risk_signal` olamaz: `"tur": "insufficient_context"` ile kaydedilir. Hipotez başka bir olguyla doğrulandığında yeni, kesin iddialı bir bulgu açılır.
- Başlık ve özet ifadenin anlamını kesinleşmiş gibi sunmaz. "Bölge paylaşıldı" yazılmaz; "'bahçe işi' ifadesi ihale paketi anlamına geliyorsa paylaşım dili var" gibi koşullu yazılır.
- `masum_aciklamalar` en az bir olağan okuma içerir; `eksik_olgular` hipotezi doğrulayacak belgeyi söyler (ör. ilgili ihale tutanağı).
- `vaka.py bulgu-ekle` alıntının okunmuş bir parçada birebir geçtiğini denetler; hipotezin kendisi alıntı yerine geçmez.

## 6. Yapılmaması gerekenler

- İfadeyi sözlükten "kartel dili" diye etiketleyip doğrudan sinyal saymak.
- Hipotezi raporda kanıt gibi sunmak ya da yalnızca hipoteze dayanarak kişi adı vermek.
- Hipotezi kaydetmeden yorumlamak: kaydedilmeyen hipotez geri taramayı tetiklemez ve rapordaki "Örtülü dil hipotezleri" bölümünde görünmez.
- Doğrulanamayan hipotezi sessizce bırakmak. İlgili sinyal kapatılırken gerekçede hipotezin neden doğrulanamadığı yazılır (`vaka.py sinyal-kapat`).
