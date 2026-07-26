# Test Raporları

Bu klasör, `run_tests.sh` script'i tarafından otomatik oluşturulan test
raporlarını içerir. Her rapor, o anki tüm test suite'inin çalıştırılma
sonucunu tarih damgasıyla kalıcı olarak kaydeder.

## Amaç

Her geliştirme adımından (task) sonra `./run_tests.sh` çalıştırılır. Bu,
yeni eklenen kodun çalıştığını doğrulamanın yanı sıra, **önceki task'larda
yazılan kodun/testlerin bozulmadığını** (regresyon yok) teyit eder.

## Dosya Adlandırma

```
test_report_YYYYMMDD_HHMMSS.md
```

## Rapor İçeriği

Her rapor şunları içerir:
- Çalıştırma zamanı
- Kullanılan komut (`uv run pytest -v ...`)
- Çıkış kodu ve BAŞARILI/BAŞARISIZ durumu
- Ortam bilgisi (Python sürümü, llama-server erişilebilirliği)
- Tam pytest çıktısı (hangi testlerin PASSED/FAILED/SKIPPED olduğu)

## Nasıl Çalıştırılır

```bash
./run_tests.sh                # tüm testler
./run_tests.sh -k test_repl   # sadece belirli bir dosya/desen
```

Script, `uv run pytest` kullanır; llama-server çalışmıyorsa sunucu
gerektiren testler otomatik `SKIPPED` olarak işaretlenir (bkz. her test
dosyasındaki `skipif` kullanımı), suite bozulmaz.

## Geçmiş Raporlar (Kronolojik Not)

- `test_report_20260726_232141.md`: `run_tests.sh` script'inin ilk
  kullanımı. O ana kadar tamamlanan **Task 1** (llama-server bağlantısı,
  `agent/llm_client.py`) ve **Task 2** (REPL döngüsü, `agent/repl.py`)
  kodlarının birlikte regresyon kontrolü. Sonuç: 7/7 test PASSED
  (gerçek llama-server'a bağlanarak, `Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf`).
  Task 1 sırasında ayrıca `uv run pytest -v` (2/2 PASSED) ve
  `uv run python -m agent.llm_client "merhaba de"` manuel olarak
  çalıştırılmış, Task 2 sırasında `uv run pytest -v` (7/7 PASSED) ve
  REPL üzerinden manuel geçmiş-korunumu testi yapılmıştı (bkz. `PROGRESS.md`
  Task 1 ve Task 2 notları) — bu script'ten önceki bu çalıştırmalar ayrı
  dosya olarak arşivlenmedi, sonuçları `PROGRESS.md`'de metinsel olarak
  kayıtlıdır.
