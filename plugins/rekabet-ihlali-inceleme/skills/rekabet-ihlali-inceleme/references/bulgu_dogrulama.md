# Bulgu doğrulama: iddia yapısı ve reddedilme nedenleri

Rekabet incelemesinde en pahalı hata, okunan metnin yönünü değiştirmektir. "Rakibe ortak zam önerdik, reddettiler" yazışması, raporda "rakiple zamda anlaştılar" diye özetlenirse hem hukuken yanlış bir sonuca hem de bir çalışan hakkında haksız bir suçlamaya yol açar. Teklif, kabul edilmiş bir anlaşma değildir. Ret ise teklifin hiç yapılmadığı anlamına gelmez. Koşullu kabul de koşulsuz kabulle aynı şey değildir.

`vaka.py bulgu-ekle` bu yüzden bulguyu serbest metin olarak değil, **iddialar** listesi olarak alır ve kaydetmeden önce denetler. Reddedilen bulgu kaydedilmez; çıktı her nedeni ayrı satırda verir.

## 1. Bulgu kaydı

```json
{
  "baslik": "Rakibe ortak fiyat artışı teklif edildi; rakip reddetti",
  "ozet": "Satış çalışanı rakibe Nisan için ortak %12 zam önerdi; rakip ertesi gün reddetti.",
  "tur": "risk_signal",
  "kategori": "FYT", "oncelik": "Yüksek", "kontroller": ["FYT-01", "FYT-06"],
  "kanitlar": [
    {"id": "K1", "parca": "B0001-P001", "alinti": "Nisan'da ikimiz de beton fiyatına %12 zam yapıyoruz"},
    {"id": "K2", "parca": "B0002-P001", "alinti": "Teklifinizi değerlendirdik, kabul etmiyoruz", "rol": "karsi"}
  ],
  "iddialar": [
    {"kim": "satis@ornek.example", "eylem": "teklif", "neyi": "ortak %12 zam", "kime": "mudur@rakip.example", "kanit": ["K1"]},
    {"kim": "mudur@rakip.example", "eylem": "ret", "neyi": "ortak zam teklifi", "kime": "satis@ornek.example", "kanit": ["K2"]}
  ],
  "hukuki_dayanak": [{"kaynak": "TR-01", "bolum": "m.4"}],
  "eksik_olgular": ["Zammın fiilen uygulanıp uygulanmadığı", "Tarafların rakip olduğunun teyidi"],
  "masum_aciklamalar": ["Bağımsız maliyet artışının duyurulması"],
  "sonraki_adim": "Hukuka ilet; Nisan fiyat listelerini karşılaştır",
  "degerlendirme": {"etki": "Orta", "aciliyet": "Düşük", "kanit_yeterliligi": "Yüksek"},
  "ihale_uyarilari": [], "kod_hipotezleri": [], "yonlendirme": "", "alan": "rekabet"
}
```

- `eylem`: teklif, ret, kabul, uygulama, bilgi_paylasimi, talimat, silme, engelleme, sapma, karar, taahhut, sozlesme.
- İddia alanları: `belirsiz` (yoruma ya da örtülü dil hipotezine dayanıyor), `kosul` (koşullu kabulün koşulu), `aktaran` (olay başkasının anlatımıyla biliniyor), `ret_aciklamasi`.
- `rol: "karsi"`: bulguya karşı kanıttır (ör. ret cevabı). Karşı kanıt gizlenmez, bulguya eklenir.
- `tur`: `risk_signal` (varsayılan) ya da `insufficient_context`.

## 2. Denetimler

| Denetim | Neden |
|---|---|
| Her kanıt, **okunup işaretlenmiş** bir parçada birebir geçer; birden çok kez geçiyorsa `konum` ister; ayrılmış (avukat/kapsam dışı) belgeden alıntı yapılamaz | Okunmamış metinden kanıt olmaz; alıntı uydurulamaz |
| En az bir destekleyici kanıt | İstatistiksel uyarı (ihale_analiz) tek başına bulgu açamaz |
| En az bir iddia; her iddiada `kim`, `neyi`, geçerli `eylem` ve kanıt kimliği | "Rakiple temas var" bir bulgu değildir |
| `kabul` iddiasının bütün kanıtları ret ifadesi içeriyorsa reddedilir | Ret içeren alıntı kabulü destekleyemez |
| Başlık ya da özet "anlaştı / kabul etti / agreed" diyorsa, iddialarda kesin (belirsiz olmayan) bir `kabul` bulunmalı | Başlık, iddialarla aynı yönde olmalı |
| Koşullu kabul varsa başlık ya da özet bunu söylemeli; aktarılan olay varsa özet "…'in aktardığına göre" demeli | Okuyucu yalnız başlığı okur |
| Bütün iddialar `belirsiz` ise `tur` = `insufficient_context` | Yalnız hipoteze dayanan bulgu risk sinyali sayılmaz |
| `hukuki_dayanak` kaynağı katalogda olmalı; TR-01 (4054) için madde 1–65, geçici madde 1–7 | Uydurma kaynak ve var olmayan madde reddedilir |
| `kategori` ve `kontroller` katalogda olmalı; KOMSU kategorisi `alan: "komsu"` ister | Şartname sapması ya da rüşvet rekabet ihlali diye adlandırılmaz |
| `eksik_olgular` ve `masum_aciklamalar` en az bir madde | İncelemeci kendi hipotezine karşı çalışmalı |
| Kayıtlı ihbarcının adı bulgunun hiçbir alanında geçemez | İhbarcıyı koruma (OP-18) |
| Bulgu talep edene, onun hattına ya da üst yönetime dokunuyorsa `yonlendirme` bağımsız bir hat olmalı (Denetim Komitesi, bağımsız hukuk müşaviri) | Bağımsız raporlama hattı (OP-17) |
| `kod_hipotezleri` defterde kayıtlı olmalı; `degerlendirme` üç eksen ve Yüksek/Orta/Düşük değerleri | Şemaya uygun çıktı |

**Uyarılar** kaydı engellemez ama yazılır: kanıtla kesişen açık sinyal başka kategorideyse otomatik bağlanmaz ("ayrı bulgu açın ya da gerekçeyle bağlayın"); `ret` iddiasında `ret_aciklamasi` varsa eylemin `uygulama` olup olmadığı sorulur.

## 3. Sık karşılaşılan durumlar

- **Teklif yapıldı, cevap yok.** İddia `teklif`; başlık "teklif edildi". Cevabın yokluğu `eksik_olgular`a yazılır. Rakibin sessiz kalıp uyguladığına dair veri varsa ayrı bir `uygulama` iddiası ve kanıtı gerekir.
- **Ret, ama ret sonrası fiyatlar yine aynı yönde.** İki iddia: `teklif` ve `ret`. Fiyat paralelliğinin kanıtı yazışma değil veriyse ayrı bir `uygulama` iddiası kurulmaz; veri `ihale_uyarilari` ya da `eksik_olgular` olarak eklenir. Paralellik tek başına mutabakat göstermez.
- **"Konuştuğumuz gibi" ile kurulan kabul.** Kabulün konusu metinde yoksa iddia `belirsiz` olur ve örtülü dil hipotezine bağlanır (`references/ortulu_dil.md`).
- **Üçüncü kişinin anlatımı.** "Bölge müdürü rakiple anlaştıklarını söyledi" → `aktaran: "bölge müdürü"`; özet "bölge müdürünün aktardığına göre" der.
- **Aynı alıntı iki bulguda.** Mümkündür; ama sinyal yalnız bir bulguya otomatik bağlanır. Diğeri `sinyaller` alanında gerekçeyle bağlanır.

## 4. Çıktı

`vaka.py rapor` bulguları `bulgular.json` içinde Bulgu_Semasi v1.2'ye çevirir: `claims` (iddialar), `title`, `area`, `coded_language` (hipotez, dayanak), kanıtta `role: "counter"`. v1.1 zorunlu alanları değişmedi; eski tüketiciler yeni alanları görmezden gelebilir. Kanıt konumları (`start_char`, `end_char`) parça içindedir; belge içi ofset `location` alanında yazılır.
