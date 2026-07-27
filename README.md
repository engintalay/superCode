# superCode

Kiro CLI benzeri, ama [llama.cpp](https://github.com/ggml-org/llama.cpp)
(`llama-server`, OpenAI-uyumlu API) üzerinden **local** AI modelleri kullanan,
daha basit ve kısıtlı kaynaklı ortamlar için tasarlanmış agentic coding
agent'ı.

Öncelik: kaynağı kısıtlı/küçük bir modelin başarısız veya belirsiz olduğu
durumlarda döngüye girmeden durup kullanıcıya bilgi vermesi.

## Durum

Faz 1 (MVP) ve Faz 2 (Paralellik) TAMAMLANDI. Tüm gereksinim ve tasarım
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
- **Task 8** — Context yönetimi (özetleme)
- **Task 9** — Sistem promptu cilalama + uçtan uca gerçek görev testleri
- **Task 10** — Paralel tool execution altyapısı (glob/grep sonrası
  otomatik paralel dosya okuma)
- **Task 11** — Paralel + onay + loop-detection entegrasyonu, uçtan uca
  doğrulama

## Gereksinimler

- Python ≥ 3.12
- [`uv`](https://github.com/astral-sh/uv) (paket yöneticisi)
- Çalışan bir `llama-server` (llama.cpp), `--jinja --tools all` flag'leriyle,
  `http://localhost:8079` adresinde (varsayılan `base_url`)

## Kurulum

```bash
./install.sh
```

Bu, Python/`uv` kontrolü, bağımlılık kurulumu ve llama-server bağlantı
kontrolünü otomatik yapar. Ayrıntılı kurulum talimatları (llama-server
başlatma, sorun giderme dahil) için [`INSTALL.md`](./INSTALL.md)'ye
bakın. Manuel kurulum için:

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
- Context yönetimi: konuşma geçmişi context limitine yaklaştığında
  otomatik olarak özetlenir (eski mesajlar tek bir özete indirilir, son
  mesajlar korunur)
- Native tool-calling (model destekliyorsa) + content içine gömülü
  tool-call JSON'u için fallback ayrıştırma
- Sistem promptu: agent kimliği, tool kuralları ve döngüye girmeden
  durma önceliğini net şekilde ifade eden bir sistem mesajıyla başlar

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
  approval.py       # Onay mekanizması (K7/K8) - requires_approval, prompt_user_confirmation
  loop_detector.py  # Loop/hata tespiti (K4/K9/K19)
  context_manager.py # Context özetleme (K13)
  system_prompt.py  # Agent kimliği ve davranış kuralları (sistem promptu)
tests/              # pytest test suite'i
test_reports/       # ./run_tests.sh tarafından üretilen tarihli test raporları
DECISIONS.md        # Tüm proje/tasarım kararları (kronolojik, kalıcı)
PROGRESS.md         # Task bazlı ilerleme durumu, oturumlar arası devam notu
install.sh          # Kurulum script'i (bağımlılık + sunucu kontrolü)
INSTALL.md          # Ayrıntılı kurulum ve sorun giderme kılavuzu
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
