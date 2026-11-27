# PST test dosyaları

Bu klasördeki PST dosyaları bizim üretimimiz değildir. Okuyucunun gerçek bir Outlook dosyasını açabildiği, başkalarının yazdığı testlerle sınanır.

| Dosya | Kaynak | Lisans | Depoda |
|---|---|---|---|
| `dist-list.pst` | [java-libpst](https://github.com/rjohnsondev/java-libpst), `src/test/resources/dist-list.pst` | Apache License 2.0 | Evet (268 KB; bir test kişisi, bir test randevusu, bir dağıtım listesi) |
| `indirilen/enron.pst` | [pst-extractor](https://github.com/epfromer/pst-extractor), `src/__tests__/testdata/enron.pst` (commit `7d08ef9`) | MIT | Hayır; CI indirir ve SHA-256 ile doğrular |

Beklenen değerler (`beklenen.json`), bizim okuyucumuzun çıktısından değil, bu projelerin kendi testlerinden alınmıştır: java-libpst `DistListTest.java`, pst-extractor `PSTMessage.spec.ts` ve `PSTFolder.spec.ts`.

`dist-list.pst` dosyası java-libpst projesinin Apache License 2.0 lisansıyla dağıtılır ve burada değiştirilmeden yer alır. Lisans metni: https://www.apache.org/licenses/LICENSE-2.0
