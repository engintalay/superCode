# superCode

Kiro CLI benzeri, ama [llama.cpp](https://github.com/ggml-org/llama.cpp)
(`llama-server`, OpenAI-uyumlu API) üzerinden **local** AI modelleri kullanan,
daha basit ve kısıtlı kaynaklı ortamlar için tasarlanmış agentic coding
agent'ı.

Öncelik: kaynağı kısıtlı/küçük bir modelin başarısız veya belirsiz olduğu
durumlarda döngüye girmeden durup kullanıcıya bilgi vermesi.

## Durum

Aktif geliştirme aşamasında (MVP / Faz 1). Tüm gereksinim ve tasarım
kararları [`DECISIONS.md`](./DECISIONS.md)'de, ilerleme durumu
[`PROGRESS.md`](./PROGRESS.md)'de tutuluyor.

Tamamlanan task'lar:
- **Task 1** — Proje iskeleti + llama-server bağlantı testi
- **Task 2** — Temel REPL döngüsü (tool'suz)
- **Task 3** — Read-only tool'lar (`read_file`, `glob_search`, `grep_search`)
  + tool-calling agent loop
- **Task 4** — Onay mekanizması (Approval Gate) + `run_shell` tool'u
- **Task 5** — `edit_file` tool'u (Aider-tarzı search/replace formatı)
- **Task 6** — Loop/hata tespiti (Loop Detector)
- **Task 7** — Otonom mod aktivasyonu + `/autonomous` REPL komutu

## Gereksinimler

- Python ≥ 3.12
- [`uv`](https://github.com/astral-sh/uv) (paket yöneticisi)
- Çalışan bir `llama-server` (llama.cpp), `--jinja --tools all` flag'leriyle,
  `http://localhost:8079` adresinde (varsayılan `base_url`)

## Kurulum

```bash
uv sync
```

## Kullanım

Etkileşimli sohbet/agent modunu başlatmak için:

```bash
uv run python -m agent.repl
```

Otonom modda başlatmak için (yazma/shell işlemleri onay istemez - yıkıcı
komutlar ve proje-dışı erişimler hariç):

```bash
uv run python -m agent.repl --autonomous
```

Oturum içinde otonom modu açıp kapatmak için: `/autonomous on|off|status`.

Çıkmak için `/exit`, `/quit` veya Ctrl+D.

Tek seferlik basit bir mesaj göndermek için (tool'suz):

```bash
uv run python -m agent.llm_client "merhaba de"
```

## Mevcut Özellikler

- llama-server ile OpenAI-uyumlu `/v1/chat/completions` üzerinden sohbet
- Turlar arası korunan konuşma geçmişi
- Read-only tool'lar: `read_file`, `glob_search`, `grep_search`
  (proje dizini dışına path traversal engellenir)
- `run_shell` tool'u (varsayılan olarak kullanıcı onayı gerektirir)
- Onay mekanizması: yazma/shell işlemleri onay ister; otonom mod ile
  atlanabilir (`/autonomous on|off|status` komutu veya `--autonomous`
  CLI flag'i ile), ancak yıkıcı komutlar ve proje-dışı erişimler otonom
  modda da her zaman onay ister (mutlak güvenlik sınırı)
- Native tool-calling (model destekliyorsa) + content içine gömülü
  tool-call JSON'u için fallback ayrıştırma

## Test Çalıştırma

Tüm test suite'ini çalıştırmak ve tarihli bir rapor almak için:

```bash
./run_tests.sh
```

Raporlar `test_reports/` altında saklanır (bkz.
[`test_reports/README.md`](./test_reports/README.md)).

llama-server çalışmıyorsa, sunucu gerektiren testler otomatik olarak
`SKIPPED` işaretlenir; suite bozulmaz.

## Proje Yapısı

```
agent/
  llm_client.py     # llama-server'a bağlanan temel OpenAI istemcisi
  repl.py           # Etkileşimli REPL + tool-calling agent loop
  tools.py          # read_file / glob_search / grep_search implementasyonları
  tool_parsing.py   # content'e gömülü tool-call JSON'u için fallback parser
tests/              # pytest test suite'i
test_reports/       # ./run_tests.sh tarafından üretilen tarihli test raporları
DECISIONS.md        # Tüm proje/tasarım kararları (kronolojik, kalıcı)
PROGRESS.md         # Task bazlı ilerleme durumu, oturumlar arası devam notu
run_tests.sh         # Test suite'ini çalıştırıp rapor üreten script
```

## Katkı / Geliştirme Kuralları

Bu projedeki geliştirme süreci kendi kurallarını `DECISIONS.md`'de takip
eder (özet):
- Her karar `DECISIONS.md`'ye eklenir, eskisi silinmez (değişirse not
  eklenir).
- Her task tamamlandığında `./run_tests.sh` çalıştırılır ve bir git
  commit'i atılır.
- Yıkıcı git komutları (force push, reset --hard vb.) kullanıcı onayı
  olmadan çalıştırılmaz.
