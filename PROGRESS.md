# PROGRESS.md - Devam Notu

Bu dosya, oturumlar arası (örn. bilgisayar restart sonrası) kaldığımız yerden
devam edebilmek için tutulur. Güncel durumu ve sıradaki adımı gösterir.

## Şu Ana Kadar Yapılanlar

1. Gereksinim toplama tamamlandı (bkz. `DECISIONS.md` - K1 ile K24 arası).
2. `DECISIONS.md` dosyası oluşturuldu - tüm kararlar, elenen seçenekler ve
   gerekçeleri içerir. Yeni her kararda bu dosyaya EKLEME yapılacak, eski
   kararlar SİLİNMEYECEK (değişirse "değiştirildi + neden" notu eklenecek).
3. Git deposu `superCode` dizininde `git init` ile oluşturuldu (dal: `master`).
4. İlk commit atıldı: `DECISIONS.md`.
5. **Task 1 tamamlandı** (proje iskeleti + llama-server bağlantı testi):
   - `uv init` ile proje kuruldu (`pyproject.toml`, `.python-version=3.12`, `uv.lock`).
   - `openai` SDK bağımlılık olarak eklendi (`uv add openai`), dev bağımlılık
     olarak `pytest` eklendi.
   - `agent/llm_client.py` yazıldı: `create_client`, `get_model_id`, `chat`,
     `main` fonksiyonları. `base_url="http://localhost:8080/v1"` ile
     llama-server'a bağlanıyor.
   - `tests/test_llm_client.py`: llama-server çalışmıyorsa `skipif` ile testler
     atlanıyor; çalışırken gerçek sunucuya bağlanıp doğruluyor.
   - Doğrulama (gerçek çalıştırma ile yapıldı):
     - `uv run pytest -v` → 2/2 test PASSED (gerçek llama-server'a bağlanarak).
     - `uv run python -m agent.llm_client "merhaba de"` → model gerçek yanıt
       verdi: "Merhaba! Size nasıl yardımcı olabilirim?"
     - Sunucu doğrulaması: `curl http://localhost:8080/v1/models` →
       `Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf` yüklü, `n_ctx=32768`.
   - `.gitignore` eklendi (`.venv/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`).
   - Not: Bu ortamda llama-server zaten çalışır durumda bulundu (kullanıcı
     teyit etti), ayrıca başlatma komutu netleştirme adımına gerek kalmadı.

## Proje Özeti (Kısa)

Kiro CLI benzeri, ama llama.cpp (`llama-server`, `--jinja` flag, OpenAI-uyumlu
API) üzerinden local model (Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf) kullanan,
Python + `uv` ile yazılan, tam agentic (read/edit/glob/grep/shell tool'ları
olan) bir coding agent. Öncelik: küçük/kısıtlı modelin çuvalladığı yerlerde
döngüye girmeden durup kullanıcıya bilgi vermesi (loop detection + onay
mekanizması + context özetleme).

Detaylı mimari ve 11 görevlik (Task 1-11) plan bu sohbet geçmişinde verildi;
plan `DECISIONS.md`'deki kararlara dayanıyor. Plan özet olarak:
- Faz 1 (MVP, tek-thread): Task 1-9
  1. Proje iskeleti + llama-server bağlantı testi
  2. Temel REPL döngüsü (tool'suz)
  3. Read-only tool'lar (read_file, glob_search, grep_search) + tool-calling
  4. Onay mekanizması (Approval Gate) + run_shell tool'u
  5. edit_file tool'u (search/replace blok formatı, Aider-tarzı)
  6. Loop/hata tespiti (Loop Detector: tekrar + adım limiti + belirsizlik)
  7. Otonom mod + mutlak güvenlik sınırları (yıkıcı komut / proje-dışı erişim)
  8. Context yönetimi (özetleme)
  9. Sistem promptu cilalama + uçtan uca gerçek görev testleri
- Faz 2 (Paralellik): Task 10-11
  10. `llama-server --parallel N` ile paralel tool execution altyapısı
  11. Paralel + onay + loop-detection entegrasyonu, uçtan uca doğrulama

## Sıradaki Adım

**Task 2: Temel REPL döngüsü (tool'suz)**
- Kullanıcıdan girdi alan, `agent.llm_client` üzerinden modele gönderen,
  yanıtı basan basit bir etkileşimli döngü (K12: REPL/chat modu).
- Konuşma geçmişi (messages listesi) turlar arası korunmalı (tool'suz halde
  bile, ileride context yönetimi/K13 için temel oluşturacak).
- Çıkış komutu (örn. `/exit` veya Ctrl+D/Ctrl+C ile temiz çıkış).
- Demo: `python -m agent.repl` (veya benzeri) ile interaktif sohbet açılır,
  birden fazla tur boyunca önceki mesajlar hatırlanır.

## Restart Sonrası Yapılacaklar

1. llama-server'ın `http://localhost:8080` adresinde çalıştığını doğrula
   (`curl http://localhost:8080/v1/models`).
2. Bu dosyayı (`PROGRESS.md`) ve `DECISIONS.md`'yi oku, bağlamı tazele.
3. Task 2'den implementasyona devam et (temel REPL döngüsü).

## Önemli Notlar / Hatırlatmalar

- Her yeni karar `DECISIONS.md`'ye eklenmeli, eski kararlar silinmemeli.
- Yıkıcı git komutları (force push, reset --hard vb.) kullanıcı onayı olmadan
  çalıştırılmayacak - bu kural agent'ın kendi geliştirme sürecinde de geçerli.
- Commit'ler sadece kullanıcı açıkça istediğinde atılacak.
