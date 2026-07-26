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
5. Proje henüz kod içermiyor - implementasyona başlanmadı.

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

**Task 1: Proje iskeleti ve llama-server bağlantı testi**
- `uv init` ile proje kurulumu
- `openai` Python SDK bağımlılığını ekle
- `base_url="http://localhost:8080/v1"` ile llama-server'a bağlanan basit bir
  `llm_client.py` modülü yaz
- Test: llama-server çalışırken basit bir mesajın cevaplandığını doğrulayan
  entegrasyon testi (server yoksa skip)
- Demo: `python -m agent.llm_client "merhaba de"` çalışıp modelden cevap alır

## Restart Sonrası Yapılacaklar

1. llama-server'ı `--jinja` flag'i ve Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf
   modeliyle başlat (henüz tam başlatma komutu netleştirilmedi - Task 1
   sırasında netleştirilecek).
2. Bu dosyayı (`PROGRESS.md`) ve `DECISIONS.md`'yi oku, bağlamı tazele.
3. Task 1'den implementasyona başla.

## Önemli Notlar / Hatırlatmalar

- Her yeni karar `DECISIONS.md`'ye eklenmeli, eski kararlar silinmemeli.
- Yıkıcı git komutları (force push, reset --hard vb.) kullanıcı onayı olmadan
  çalıştırılmayacak - bu kural agent'ın kendi geliştirme sürecinde de geçerli.
- Commit'ler sadece kullanıcı açıkça istediğinde atılacak.
