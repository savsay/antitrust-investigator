# Okuma protokolü: vaka defteri ve üç gösterge

Bir inceleme raporunun en zayıf noktası, "her şeyi okudum" cümlesinin doğrulanamamasıdır. Model uzun bir belge kümesinde bazı parçaları atlayabilir, bir dosyayı açamadığı hâlde temiz sayabilir ya da bulduğu bir sinyali rapora taşımayı unutabilir. Vaka defteri (`scripts/vaka.py`) bu üç hatayı ayrı ayrı görünür kılar. Okumayı model yapar; defter yalnızca okumanın gerçekten yapıldığını ve her sinyalin bir karara bağlandığını kayıt altına alır.

Defteri şu durumlarda kullan: gerçek veriyle yapılan her inceleme, yaklaşık 20'den fazla belge, birden çok okuyucu (alt ajan) ya da raporun başkasına teslim edileceği her iş. Birkaç belgelik hızlı bir ön bakış için SKILL.md bölüm 5'teki ön tarama yeterlidir.

## 1. Vakayı açma (yetki kapısı)

```bash
python3 scripts/vaka.py ac VAKA --ad "Ankara Metro ihalesi" \
  --yetki "Hukuk Md. talimatı HK-2026-14" --amac "teklif koordinasyonu şüphesi" --kapsam "satış ekibi, 01.2025-06.2025, Exchange" \
  --avukat-alan "buro.av.tr,hukukburosu.example" --haric "*/kisisel/*,*.pst.bak" \
  --talep-eden "Satış GMY" --ust-yonetim "CEO" --ihbarci "<ad>"
```

- `--yetki`, `--amac` ve `--kapsam` olmadan gerçek vaka açılmaz (çıkış kodu 4) ve klasörde vaka dosyası oluşmaz. Bu bilgileri kullanıcıya sor; uydurma. Kurgusal test verisi için `--sentetik` kullanılır; raporun her sayfası SENTETİK damgası taşır.
- `--avukat-alan`, `--haric` ve metindeki gizlilik ibareleri, belgeyi **metne çevirmeden önce** ayırır. Ayrılan belgenin ekleri ve alt öğeleri de ayrılır. Ayrılan içerik parçalanmaz, okunmaz, aranmaz; yalnız sayısı ve nedeni raporlanır.
- `--talep-eden` ve `--ust-yonetim`, bulgu bu kişilere dokunduğunda bağımsız raporlama hattını zorunlu kılar. `--ihbarci` adı hiçbir bulgu kaydına giremez.

## 2. Yükleme ve okuyucular

```bash
python3 scripts/vaka.py doktor                 # hangi okuyucu araçları kurulu
python3 scripts/vaka.py yukle VAKA <klasör|dosya> ...
```

`okuyucular.py` şunları açar: EML, PST/OST (readpst ile her öğe ayrı belge), arşivler (zip, tar, gz; varsa rar/7z), OpenDocument, RTF, eski Office (.doc/.xls/.ppt, catdoc paketiyle), taranmış görsel ve metin katmanı olmayan PDF sayfaları (Tesseract OCR; tur+eng+rus). Uzantısı olmayan ekler içerikten tanınır. Aynı dosya ikinci kez yüklenmez (SHA-256).

Okunamayan her belge (şifreli, bozuk, OCR'ın anlamsız çıktı verdiği görsel) **elle ele alınacaklar** listesine düşer; temiz sayılmaz. OCR çıktısı bir anlamsızlık ölçüsünden geçer; yanlış dil modeliyle üretilmiş çöp metin kayda alınmaz. Elle incelenen belge gerekçeyle kapatılır:

```bash
python3 scripts/vaka.py belge-coz VAKA B0007 --dokum elle_dokum.txt --aciklama "taranmış sözleşme, iç denetim elle yazdı"
python3 scripts/vaka.py belge-coz VAKA B0012 --icerik-yok --aciklama "fotoğraf; metin yok, iki kişi kontrol etti"
```

## 3. Okuma döngüsü

```bash
python3 scripts/vaka.py sonraki VAKA --n 3        # ERISIM → A → B → C → işaretsiz sırasıyla
```

Her parça yaklaşık 3000 karakterdir ve gösterildiği anda tek kullanımlık bir onay kodu alır (`[[ONAY: 4F2A9C]]`). Parça yalnız bu kodla işaretlenebilir. Aynı parça yeniden gösterilirse eski kod geçersiz olur. Bu, parçanın gerçekten açıldığının kaydıdır; kodun kendisi okuma kalitesini kanıtlamaz, bu yüzden her işaret bir karar ve gerektiğinde gerekçe ister.

```json
[{"parca": "B0001-P001", "onay": "4F2A9C", "karar": "sinyal",
  "sinyaller": [{"kategori": "FYT", "alinti": "Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz"}]},
 {"parca": "B0002-P001", "onay": "77B0E1", "karar": "temiz"},
 {"parca": "B0003-P002", "onay": "0C93AA", "karar": "okunamadi", "not": "tablo görüntü olarak gömülü"}]
```

```bash
python3 scripts/vaka.py isaretle VAKA --json isaret.json
```

- `karar`: `temiz` | `sinyal` | `okunamadi` | `kapsam_disi`. Son ikisi en az 10 karakterlik `not` ister.
- Sinyal alıntısı parçada **birebir** geçmelidir; kategori kontrol ailelerinden biri (FYT, IHL, BLG, PZR, IK, DKY, HD, JV, BD, DL, ALG) ya da KOMSU, GUVENLIK, ERISIM olmalıdır.
- ERISIM ön etiketli parça uyarıyla gösterilir: içeriği analiz etmeden önce erişim yetkisini doğrula; yetki yoksa `kapsam_disi` ile işaretle ve hukuka yönlendir.
- Bağlam için: `vaka.py baglam VAKA B0004-P001` (aynı kapsayıcıdaki ekler ve aynı yazışma zincirindeki iletiler; ret ya da kabul çoğu zaman başka iletidedir), `vaka.py capraz VAKA` (zincirler ve kopya içerik; kopya bağımsız teyit sayılmaz), `vaka.py ara VAKA "<ifade>" [--duzenli] [--yeniden-ac]`.

**Paralel okuma.** Birden çok alt ajan aynı vakada çalışabilir: her biri `sonraki --isci <ad>` ile parça alır; alınan parça 30 dakika boyunca başka işçiye verilmez. İşçiler işe başlamadan önce `vaka.py hafiza VAKA` ile örtülü dil hipotezlerini okur (`references/ortulu_dil.md`).

## 4. Üç gösterge

`vaka.py durum VAKA` üç göstergeyi ayrı ayrı verir. Biri diğerinin yerine geçmez:

| Gösterge | Tamam sayılması için | Tipik eksik |
|---|---|---|
| 1. Kuyruk | Bekleyen ya da yeniden açılmış parça yok | Geri tarama yeni parçaları açtı |
| 2. Okuma kapsamı | Okunamayan parça yok; elle ele alınacak her belge `belge-coz` ile kapatıldı | Şifreli ek, OCR çıkmayan görsel |
| 3. Sinyal kararı | Her sinyal bir bulguya bağlandı ya da gerekçeyle kapatıldı | Fark edilmiş ama rapora taşınmamış sinyal |

"Kuyruk bitti", "tamamı okundu" demek değildir; "tamamı okundu" da "riskler eksiksiz raporlandı" demek değildir. Sinyal, bulguya `bulgu-ekle` sırasında otomatik (aynı parça, kesişen konum, aynı kategori ailesi) ya da `sinyaller` alanında gerekçeyle bağlanır. Bulguya dönüşmeyen sinyal en az 15 karakterlik gerekçeyle kapatılır:

```bash
python3 scripts/vaka.py sinyal-kapat VAKA --json '[{"id": "S-0005", "gerekce": "Kamuya açık fiyat listesinden alıntı; bağımsız fiyatlama"}]'
python3 scripts/vaka.py sinyal-ata VAKA --json '[{"id": "S-0006", "sorumlu": "İç Denetim", "hedef_tarih": "2026-12-15"}]'   # açık kalır
```

## 5. Kısmi okuma ve örneklem

Her parçanın okunması mümkün değilse (ör. on binlerce C seviyesi parça), kalan kuyruktan rastgele parça okunur:

```bash
python3 scripts/vaka.py sonraki VAKA --rastgele --n 20
```

Rapor, rastgele okunan parçalardaki sinyal oranından okunmayan kısım için %95 güven aralıklı (Wilson) bir tahmin verir: "okunmayan N parçada beklenen sinyal oranı %a–%b". Bu bir tahmindir; okunmayan parçaları temiz saymaz ve raporu KISMİ olmaktan çıkarmaz.

## 6. Doğrulama ve rapor

```bash
python3 scripts/vaka.py dogrula VAKA --kaynak-kok <yüklenen klasör>
python3 scripts/vaka.py rapor VAKA --kaynak-kok <yüklenen klasör>
```

`dogrula` dört denetim yapar ve biri geçmezse çıkış kodu 1 döner:

- **kanit:** her bulgu alıntısı, işaretlenmiş bir parçada hâlâ birebir duruyor.
- **kaynak_butunlugu:** kaynak dosyaların SHA-256 özeti yüklemedeki ile aynı (dosya sonradan değiştiyse geçmez).
- **okuma_kapsami:** gösterge 1 ve 2.
- **sinyal_karari:** gösterge 3.

`rapor`, `rapor/R-<zaman>-<kimlik>/` altına `rapor.md`, şemaya uygun `bulgular.json` (v1.2) ve parça bazında `kapsama.csv` yazar. Eksik her gösterge raporun başına KISMİ damgası koyar; açık sinyaller, elle ele alınan belgeler, ayrılan içerik sayısı ve örtülü dil hipotezleri ayrı bölümlerde listelenir. Raporu Claude dokümanına ve .docx'e (SKILL.md bölüm 9) bu dosyalardan aktar; sayıları yeniden hesaplama, `rapor.md`'den al.

`vaka.py gunluk VAKA` tüm komutların zaman damgalı kaydını verir; yöntem bölümüne dayanak olarak eklenebilir.
