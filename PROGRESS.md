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
   - Commit: `79a5ec2`.
6. **Task 2 tamamlandı** (temel REPL döngüsü, tool'suz):
   - `agent/repl.py` yazıldı: `run_turn` (tek tur istek/yanıt), `repl`
     (etkileşimli döngü), `main`.
   - Mesaj geçmişi (`messages` listesi) turlar arası korunuyor (K13'ün temeli;
     özetleme henüz yok, Task 8'de eklenecek).
   - Çıkış: `/exit`, `/quit` komutları; Ctrl+D (EOFError) ve Ctrl+C
     (KeyboardInterrupt) da temiz çıkış yapıyor.
   - `tests/test_repl.py`: 5 test - exit komutları, `run_turn` gerçek sunucuyla,
     geçmiş korunumu + `/exit` (gerçek sunucuyla), EOF ile temiz çıkış
     (mock client ile, sunucu gerektirmez), bağlantı hatası durumunda 1
     dönmesi (mock ile).
   - Doğrulama (gerçek çalıştırma ile yapıldı):
     - `uv run pytest -v` → 7/7 test PASSED.
     - Manuel demo: `printf "merhaba, sen kimsin?\n/exit\n" | uv run python -m agent.repl`
       → model kimliğini tanıttı, `/exit` ile "Görüşürüz." basıp çıktı.
     - Geçmiş korunumu doğrulandı: "Benim adım Engin." → sonraki turda
       "Benim adım neydi?" sorusuna model "Rica ederim Engin, ..." diyerek
       ismi doğru hatırladığını gösterdi.
   - Commit: (bu adımda atılacak).

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

**Task 9: Sistem promptu cilalama + uçtan uca gerçek görev testleri**
- Agent'ın kimliğini/davranış kurallarını (K9 davranışı dahil) net bir
  sistem promptuyla pekiştirmek.
- Gerçek, çok adımlı bir görevle (örn. "bu projede X özelliğini ekle")
  uçtan uca test.

### Task 8 TAMAMLANDI - Context yönetimi (özetleme, K13)

- `agent/context_manager.py` (yeni modül):
  - `estimate_tokens()`: karakter/4 heuristiği ile kaba token tahmini
    (tam tokenizer bağımlılığı eklenmedi - amaç kesin sayım değil, eşik
    sinyali).
  - `get_context_limit()`: sunucudan `/v1/models` üzerinden `meta.n_ctx`
    değerini okur (gerçek sunucuda doğrulandı: 65536 doğru alındı),
    alınamazsa `DEFAULT_N_CTX=8192`'e düşer.
  - `should_summarize()`: mesaj sayısı `KEEP_RECENT_MESSAGES=4`'ün altında
    ise VEYA tahmini token `context_limit * SUMMARIZE_THRESHOLD_RATIO=0.75`
    altında ise özetleme gerekmez.
  - `summarize_messages()`: system mesajlarını ve en son 4 mesajı korur,
    aradaki eski mesajları AYRI BİR LLM ÇAĞRISIYLA (K13) tek bir özet
    mesajına indirir.
  - `maybe_summarize()`: `should_summarize` + `summarize_messages`'ı
    birleştiren üst seviye fonksiyon, `repl()`'in kullandığı arayüz.
- `agent/repl.py`: `repl()` döngüsüne entegre edildi - her turdan önce
  `maybe_summarize()` çağrılır, özetleme olduysa kullanıcıya bilgi
  mesajı gösterilir (`[Bağlam özetlendi: ...]`).
- Testler:
  - `tests/test_context_manager.py`: 12 test - 11 mock/birim (token tahmini,
    eşik kontrolü - üstünde/altında/az mesaj durumu, context limit okuma -
    başarı/hata, özetleme - system+recent korunumu, no-op durumu,
    maybe_summarize entegrasyonu) + 1 gerçek sunucu entegrasyon testi.
- Doğrulama:
  - `./run_tests.sh` → 97 passed, 1 skipped (regresyon yok). Rapor:
    `test_reports/test_report_20260727_030825.md`.
  - Gerçek sunucu ile doğrulama: `get_context_limit()` gerçek modelden
    `n_ctx=65536` değerini doğru okudu.
  - Manuel uçtan uca demo: 12 mesajlık sahte bir geçmiş, `context_limit=200`
    ile zorlanarak özetlemeye tabi tutuldu → 5 mesaja indirildi (1 gerçek
    LLM-üretilmiş özet + son 4 mesaj), özet içeriği doğru yakaladı
    ("Kullanıcı 4 adet dolgu mesajı gönderdi...").
- Commit: (bu adımda atılacak).

### Task 7 TAMAMLANDI - Otonom mod aktivasyonu + REPL komutu

- `agent/repl.py`:
  - `_handle_autonomous_command()`: `/autonomous on|off|status` komutunu
    işler, yeni mod + kullanıcıya gösterilecek mesajı döner. Bilinmeyen
    argüman modu değiştirmez, hata mesajı gösterir.
  - `repl()`: giriş döngüsünde `/autonomous` komutu tanınıyor, mod anlık
    değişiyor (sonraki `run_turn` çağrılarına yansır). Başlangıç durumu
    hâlâ `autonomous_mode` parametresiyle ayarlanabilir.
  - `main()`: `--autonomous` CLI flag'i eklendi (`argv` parse ediliyor).
  - Not: Task 4'te zaten kurulan `autonomous_mode` parametresi ve K8
    mutlak sınırları (`agent/approval.py`) değişmedi - bu task sadece
    REPL'de bunu açıp kapatacak kullanıcı arayüzünü ekledi.
- Testler:
  - `tests/test_repl.py`: 7 yeni test - `_handle_autonomous_command`
    (on/off/status/bilinmeyen argüman), `repl()` içinde `/autonomous on`
    yazınca sonraki `run_turn` çağrısının `autonomous_mode=True` ile
    yapıldığının doğrulanması, `main()`'in `--autonomous` flag'ini doğru
    parse ettiğinin (ve flag yoksa `False` kaldığının) doğrulanması.
- Doğrulama:
  - `./run_tests.sh` → 85 passed, 1 skipped (regresyon yok). Rapor:
    `test_reports/test_report_20260727_025455.md`.
  - Manuel demo (gerçek sunucu + gerçek REPL, uçtan uca):
    1. `/autonomous status` → "KAPALI", `/autonomous on` → mod değişti,
       `/autonomous status` → "AÇIK", `/autonomous off` → "KAPALI" - hepsi
       doğru çalıştı.
    2. Otonom mod AÇIK + normal (yıkıcı olmayan) `run_shell` komutu: 3/3
       denemede `[ONAY GEREKLİ]` mesajı ÇIKMADI, komut direkt çalıştı
       (`echo test1` → gerçek "test1" çıktısı üretti).
    3. **K8 mutlak sınırı doğrulandı:** Otonom mod AÇIK + `rm -rf` komutu:
       `[ONAY GEREKLİ]` mesajı YİNE ÇIKTI ("otonom mod bu tür işlemleri
       asla otomatik onaylamaz (K8)" mesajıyla), "h" (hayır) ile reddedildi,
       komut ÇALIŞTIRILMADI.
- Commit: (bu adımda atılacak).

### Task 6 TAMAMLANDI - Loop/hata tespiti (Loop Detector)

- `agent/loop_detector.py` (yeni modül):
  - `LoopDetector` sınıfı: `record_tool_call()`, `record_ambiguous_response()`,
    `record_progress()` ile durum takibi; `check()` üç sinyali de kontrol eder.
  - Sinyal 1 - `detect_repeated_tool_calls()`: K4/K19 - son `REPEAT_THRESHOLD=3`
    tool-call'ın hepsi BAŞARISIZ ve birbirine `SIMILARITY_THRESHOLD=0.85`
    üzerinde benziyorsa (fuzzy, `SequenceMatcher.ratio()` ile - tam eşleşme
    değil) tetiklenir.
  - Sinyal 2 - `detect_ambiguity()`: K4 - art arda `AMBIGUITY_THRESHOLD=3`
    belirsiz/parse edilemeyen yanıttan sonra tetiklenir.
  - Sinyal 3 - `detect_no_progress()`: K4 - `MAX_TURNS_WITHOUT_PROGRESS=8`
    turda ilerleme olmazsa tetiklenir.
  - `contains_uncertainty_phrase()`: model "bilmiyorum"/"emin değilim"/
    "I'm not sure"/"clarify" gibi ifadeler kullanıyorsa tespit eder.
  - `summarize_loop_detection()`: K9 - DUR, sebep, denenenler listesi,
    3 alternatif öneri, "nasıl ilerlemek istersiniz?" formatında özet üretir.
- `agent/repl.py`: `run_turn()` içine entegre edildi - her tool-call hop'u
  sonrası ve her tool-call'sız yanıt sonrası `detector.check()` çağrılır;
  tetiklenirse döngü MAX_TOOL_HOPS'un tamamına gitmeden durur, özet döner.
  Bu davranış `autonomous_mode` fark etmeksizin aynıdır (K9, mutlak).
- Testler:
  - `tests/test_loop_detector.py`: 14 birim testi (boş geçmiş, başarılı
    çağrılar tetiklemiyor, aynı/benzer-ama-farklı başarısız çağrılar
    tetikliyor, farklı tool'lar/farklı argümanlar tetiklemiyor, bir
    başarı sayaçları sıfırlıyor, belirsizlik eşiği, ilerleme sıfırlama,
    uncertainty phrase tespiti, özet formatı).
  - `tests/test_repl.py`: 1 yeni entegrasyon testi - 3 tekrarlı başarısız
    `read_file` çağrısı sonrası (mock ile) loop detector'ın MAX_TOOL_HOPS'un
    tamamına (5) gitmeden 3. denemede durduğunu doğruluyor.
- Doğrulama:
  - `./run_tests.sh` → 78 passed, 1 skipped (regresyon yok).
  - Manuel demo: gerçek REPL'de "asla durma" talimatı verildi; model bunu
    kendi muhakemesiyle reddetti (tool-call zinciri oluşmadı, loop detector
    tetiklenecek bir senaryo doğal olarak oluşmadı) - bu, gerçek modelin
    zaten normalde sonsuz döngüye girmeye istekli olmadığını gösteriyor;
    asıl güvenlik ağı (loop detector) mock testlerle kesin olarak
    doğrulandı çünkü gerçek modelde tekrarlı başarısızlık senaryosu
    güvenilir şekilde tetiklenemiyor (model genelde 1 denemeden sonra
    hata mesajını görüp farklı bir şey deniyor veya durup soruyor).
- Commit: (bu adımda atılacak).

### Ek: llm-server portu 8080 → 8079 değişti

Kullanıcı llama-server'ın portunu 8079 olarak değiştirdi. Güncellenen
yerler: `agent/llm_client.py` (`DEFAULT_BASE_URL`), `run_tests.sh`
(sunucu durum kontrolü), `tests/test_llm_client.py`,
`tests/test_repl.py`, `tests/test_tool_calling_discovery.py` (skip mesajı
metinleri), `README.md` (kullanım talimatı). Doğrulama: `curl` ile 8079
`200` döndü, 8080 artık `000` (erişilemez) - port değişikliği teyit edildi.
`./run_tests.sh` → 77 passed, 2 skipped (1 skip beklenen, 1 flaky test
tekrar çalıştırılınca PASSED oldu - bilinen model non-determinism'i,
port değişikliğiyle ilgisiz).

### Task 5 TAMAMLANDI - edit_file tool'u (Aider-tarzı search/replace)

- `agent/tools.py`:
  - `_parse_search_replace_block()`: `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE`
    formatını ayrıştırır (K6/K17). Marker eksikse/sıra hatalıysa `ToolError`.
  - `edit_file()`: SEARCH bloğu dosyada TAM OLARAK BİR KEZ bulunmalı -
    sıfır eşleşme (bulunamadı) veya birden fazla eşleşme (belirsiz) ayrı
    ayrı, açık hata mesajlarıyla reddedilir. REPLACE boş olabilir (silme).
  - `TOOL_DEFINITIONS`e eklendi; tool açıklaması, girinti/boşluğun BİREBİR
    eşleşmesi gerektiğini modele açıkça vurguluyor (gerçek demo'da tespit
    edilen bir risk sonrası güçlendirildi, aşağıya bakın).
  - `APPROVAL_REQUIRED_TOOLS` setinde zaten vardı (Task 4'te önceden
    eklenmişti) - onay mekanizmasıyla otomatik entegre.
- Testler:
  - `tests/test_tools.py`: 11 yeni test (tek değişiklik uygulama, dosya
    yok, SEARCH bulunamadı, SEARCH belirsiz/birden fazla eşleşme, format
    hataları - marker eksik, boş SEARCH, path traversal, boş REPLACE ile
    silme, dispatcher entegrasyonu, girinti davranışı - 2 test, aşağıya
    bakın).
  - `tests/test_repl.py`: 1 yeni test (`edit_file` onay akışı - mock ile,
    onay + gerçek dosya değişikliği doğrulanıyor).
- **Bulgu (gerçek demo ile tespit edildi):** `edit_file`, satır bazlı değil
  KARAKTER BAZLI tam alt-dize eşleşmesi yapar (Python `str.replace()`).
  Model SEARCH bloğuna girintiyi dahil etmezse VE REPLACE bloğunun
  içinde fazladan bir boş satır varsa, sonuç girintisi bozuk bir dosya
  olabilir (gerçek demo'da gözlendi: `    print("hello")` →
  `    \nprint("hello world")`). Bu bir bug değil - tool verilen metni
  birebir uyguluyor (beklenen davranış), ama model formatı hatalı
  üretebiliyor. Çözüm: tool açıklaması güçlendirildi ("boşluk/girinti dahil
  birebir aynı olmalı" açıkça vurgulandı); davranış iki testle
  (`test_edit_file_search_without_indentation_matches_substring_anywhere`,
  `test_edit_file_replace_with_leading_newline_can_break_indentation`)
  regresyon olarak kayıt altına alındı. Modelin bu tür hataları tekrar
  tekrar yapması durumu Task 6'nın (loop detection) kapsamına giriyor.
- Doğrulama:
  - `./run_tests.sh` → 62 passed, 2 skipped (regresyon yok). Rapor:
    `test_reports/test_report_20260727_013603.md`.
  - Manuel demo (gerçek sunucu + gerçek REPL, 3 deneme): 1/3 denemede
    model doğru SEARCH/REPLACE üretip onayladı, sonuç doğru
    (`def greet():\n    print("hello world")\n`, girinti korunmuş).
    2/3 denemede model non-determinism nedeniyle format hatası yaptı veya
    tool-call üretmedi - bu, `edit_file`'ın kendi implementasyon hatası
    değil, modelin davranışsal kararsızlığı (Task 6'nın çözeceği alan).
- Commit: (bu adımda atılacak).

### Task 4 TAMAMLANDI - Onay mekanizması (Approval Gate) + run_shell

- `agent/approval.py` (yeni modül):
  - `READ_ONLY_TOOLS` / `APPROVAL_REQUIRED_TOOLS` setleri.
  - `is_destructive_shell_command()`: regex tabanlı yıkıcı komut tespiti
    (rm -rf, git push --force, git reset --hard, git clean -f, git branch -D,
    mkfs, dd of=/dev/, fork bomb, vb.) - K8.
  - `is_outside_project()`: path'in proje kökü dışına çıkıp çıkmadığını
    kontrol eder - K8.
  - `requires_approval()`: ana karar fonksiyonu - read-only asla onay
    istemez; yazma/shell normalde onay ister ama otonom modda atlanır;
    YIKICI KOMUT ve PROJE-DIŞI ERİŞİM otonom modda BİLE onay ister (K8'in
    mutlak sınırı, kod seviyesinde garanti edildi).
  - `prompt_user_confirmation()`: gerçek `input()` ile kullanıcıya soran
    fonksiyon (test edilebilirlik için `run_turn`'e enjekte edilebilir).
- `agent/tools.py`: `run_shell` tool'u eklendi (`subprocess.run`,
  `SHELL_TIMEOUT_SECONDS=30` zaman aşımı, `MAX_SHELL_OUTPUT_BYTES=50000`
  çıktı kırpma, proje kökünde çalışır). `TOOL_DEFINITIONS`/`TOOL_FUNCTIONS`'a
  eklendi.
- `agent/repl.py`: `run_turn` onay akışıyla entegre edildi -
  `_handle_tool_call()` her tool-call'da önce `requires_approval()`'a bakıp
  gerekiyorsa `confirm()` çağırıyor; reddedilirse tool ÇALIŞTIRILMIYOR,
  "REDDEDİLDİ" mesajı modele geri veriliyor. `repl()`/`run_turn()` artık
  `autonomous_mode` parametresi alıyor.
- Testler:
  - `tests/test_approval.py`: 9 birim testi (read-only muafiyeti, varsayılan
    onay, otonom modda atlama, yıkıcı komut tespiti - pozitif/negatif,
    K8 mutlak sınırı - yıkıcı komut VE proje-dışı erişim otonom modda da
    onay istiyor, bilinmeyen tool varsayılan onay ister).
  - `tests/test_tools.py`: 6 yeni test (`run_shell` stdout/exit_code/stderr,
    proje kökünde çalışma, zaman aşımı, dispatcher entegrasyonu).
  - `tests/test_repl.py`: 5 yeni test (onay isteme+kabul, onay reddi
    (komut çalışmıyor), otonom modda atlama, K8 mutlak sınırı - otonom
    modda yıkıcı komut yine onay istiyor).
- Doğrulama:
  - `./run_tests.sh` → 49 passed, 2 skipped (regresyon yok). Rapor:
    `test_reports/test_report_20260727_004723.md`.
  - Manuel demo (gerçek sunucu + gerçek REPL, iki senaryo):
    1. Onay + kabul: "run_shell tool'unu kullanarak 'echo merhaba' komutunu
       çalıştır" → `[ONAY GEREKLİ]` gösterildi, "e" girişiyle onaylandı,
       komut gerçekten çalıştı, model "merhaba" çıktısını doğru özetledi.
    2. Onay + red: aynı senaryo "h" (hayır) ile → komut ÇALIŞTIRILMADI,
       model reddedildiğini kabul edip kullanıcıya bildirdi.
- Commit: `d13971c` sonrası, bu adımda yeni commit atılacak.

### Ek düzeltme: test sunucu kontrolü bug'ı + ortam çakışması (K28)

Test suite çalıştırılırken 3 test aniden başarısız oldu. Kök neden:
başka bir coding agent, llama-server'ı kapatıp aynı portta (8080) kendi
PHP tabanlı uygulamasını çalıştırmıştı (`curl` ile `302 Found` +
`Location: login.php` + `X-Powered-By: PHP/8.5.8` tespit edildi - bu
llama-server yanıtı değil). Kullanıcı duruma müdahale edip llama-server'ı
yeniden başlattı, `200 OK` doğrulandı.

Bu sırada test kodunda bir bug bulundu: `_server_available()` (3 dosyada
tekrarlanan), sadece bağlantı hatasını kontrol ediyordu, HTTP yanıt kodunu
kontrol etmiyordu - port başka bir servise kaptırıldığında "sunucu var"
sanıp testleri çalıştırmaya başlıyor, ortasında patlıyordu.

Düzeltme: `tests/_server_check.py` ortak modülü eklendi
(`server_available()`, HTTP 200 kontrolü + `follow_redirects=False`),
3 test dosyasındaki tekrar kaldırıldı. K28 eklendi: agent, bu tür ortam
çakışmalarını tespit ettiğinde otomatik düzeltmeye çalışmadan önce
kullanıcıya haber verip onun kontrol etmesini bekleyecek.

Doğrulama: `./run_tests.sh` → 50 passed, 1 skipped (sunucu tekrar sağlıklı
olduktan sonra). Rapor: `test_reports/test_report_20260727_011557.md`.

### Task 3 TAMAMLANDI - read_file/glob_search/grep_search + agent loop

Task 3'ün kalan kısmı (native tool-calling keşfi + model değişikliği zaten
yukarıda dokümante edildi) tamamlandı:

- `agent/tools.py`: `read_file`, `glob_search`, `grep_search` implementasyonları
  + `TOOL_DEFINITIONS` (OpenAI-uyumlu JSON schema) + `execute_tool` dispatcher.
  - Path traversal koruması (`_resolve_within_root`) - proje kökü dışına
    çıkan okumalar `ToolError` ile reddediliyor (K7/K8'in temeli).
  - `execute_tool`, argüman adlarını küçük harfe normalize ediyor (model
    bazen "Pattern" gibi yanlış büyük/küçük harfli argüman üretebiliyor,
    gerçek testte tespit edildi) ve `TypeError`'ı `ToolError`'a çeviriyor.
  - `glob_search`, `**/*.ext` desenini kök dizindeki dosyalarla da eşleşecek
    şekilde düzeltildi (fnmatch'in doğal davranışı bunu desteklemiyordu -
    gerçek testte tespit edilen bir bug).
- `agent/repl.py`: `run_turn` tam bir tool-calling agent loop'una dönüştürüldü.
  - Native `tool_calls` alanı öncelikli denenir; boşsa
    `extract_tool_call_from_content` ile fallback denenir (K1/K11 uyumlu).
  - Native tool-call: OpenAI formatına uygun `assistant` (tool_calls ile) +
    `tool` (tool_call_id ile) mesaj çifti eklenir, model tekrar çağrılır.
  - Fallback tool-call: gerçek tool_call_id yok, sonuç bir `user` rolü
    notu olarak eklenir (basit ama işlevsel bir çözüm).
  - `MAX_TOOL_HOPS=5` ile sonsuz tool-call zincirine karşı temel bir sınır
    (asıl loop detection Task 6'da gelecek, bu şimdilik kaba bir güvenlik ağı).
- Testler:
  - `tests/test_tools.py`: 14 birim testi (path traversal, kırpma, glob/grep
    davranışı, argüman normalizasyonu, `**` deseni). Sunucu gerektirmiyor.
  - `tests/test_repl.py`: 2 yeni test eklendi -
    `test_run_turn_executes_read_file_tool_and_summarizes` (gerçek sunucu,
    modelin non-determinism'i nedeniyle tool-call üretmezse SKIP eder - bu
    agent kodunun hatası değil, modelin davranışsal kararsızlığı),
    `test_run_turn_executes_tool_via_native_tool_call` (mock client, sunucu
    gerektirmez, tool zincirinin doğru işlediğini kesin olarak doğrular).
- Doğrulama:
  - `./run_tests.sh` → 31 passed, 1 skipped (regresyon yok). Rapor:
    `test_reports/test_report_20260727_003226.md`.
  - Manuel demo: `printf "README.md dosyasını oku ve özetle...\n/exit\n" | uv run python -m agent.repl`
    → model `read_file` tool'unu kullanarak README.md'yi gerçekten okudu,
    doğru bir özet üretti.
- Commit: (bu adımda atılacak).

### README.md ve Remote Repo (K27)

Kullanıcı GitHub'da bir remote repo ekledi (`origin` →
`https://github.com/engintalay/superCode.git`). `README.md` güncel proje
durumuna göre yeniden yazıldı (tamamlanan task'lar, kullanım, proje yapısı).
K27 kararı: README.md her task tamamlandığında güncellenecek.

### Task 3 - Önemli Bulgu (model değişikliği: Qwen2.5-Coder-14B → gemma4-coding)

Gerçek ortam testinde (curl + OpenAI SDK ile), Qwen2.5-Coder-14B-Instruct
modeliyle llama-server'ın native `tool_calls` alanı HİÇ dolmuyordu - model
tool-call JSON'unu `content` içine 3 farklı formattan biriyle gömüyordu:
` ```json{...}``` ` bloğu, `<tools>{...}</tools>` etiketi,
`<call>{...}</call>` etiketi (format tutarsız).

İlk şüpheli KV cache quantization'dı (`-ctk/-ctv q4_0`, K1'in uyardığı
durum). Kullanıcı sunucuyu bu flag'ler OLMADAN yeniden başlattı (doğrulandı:
`ps aux` ile yeni PID, flag'lerin kaldırıldığı teyit edildi) ama davranış
AYNI kaldı → kök neden quantization değil, muhtemelen bu llama-server
derlemesinin Qwen2.5-Coder jinja şablonu/tool-call parser eşleşmesiyle ilgili.

**Kullanıcı test modelini değiştirdi:** `gemma4-coding-Q4_K_M.gguf`.
Doğrulama (8 ayrı gerçek istek): tool gerektiren isteklerde native
`tool_calls` 7/8 dolu geldi (1 istisna - model non-determinism'i, nadir),
tool gerektirmeyen sohbette doğru şekilde `tool_calls: None` + normal
`content` döndü. Bu, `gemma4-coding`'in Qwen2.5-Coder-14B'den çok daha
güvenilir native tool-calling sağladığını kanıtladı.

**Sonuç:** `agent/tool_parsing.py` (fallback parser) KALDIRILMADI - hem
nadir non-determinism durumu için güvenlik ağı, hem de ileride farklı bir
model denenirse tekrar gerekebileceği için korunuyor. Agent loop mantığı:
önce native `tool_calls`'a bak, boşsa fallback parser'ı dene.

Doğrulama:
- `tests/test_tool_calling_discovery.py`: artık her iki durumu (native dolu
  / content'e gömülü) kabul ediyor, hangisinin gerçekleştiğini raporluyor.
  Gerçek sunucuyla 3 kez arka arkaya çalıştırıldı: her seferinde
  `test_native_tool_calls_field_is_not_reliable` PASSED,
  `test_tool_call_json_embedded_in_content_is_extractable` SKIPPED (native
  doldu, fallback test edilemedi - beklenen davranış).
- `tests/test_tool_parsing.py`: 7 birim testi, sunucu gerektirmiyor, hepsi
  PASSED (fallback parser'ın kendisi hâlâ doğru çalışıyor).
- `./run_tests.sh` → 15 passed, 1 skipped (regresyon yok). Rapor:
  `test_reports/test_report_20260726_234627.md`.
- Commit: (bu adımda atılacak).

## Restart Sonrası Yapılacaklar

1. llama-server'ın `http://localhost:8080` adresinde çalıştığını doğrula
   (`curl http://localhost:8080/v1/models`).
2. Bu dosyayı (`PROGRESS.md`) ve `DECISIONS.md`'yi oku, bağlamı tazele.
3. Task 2'den implementasyona devam et (temel REPL döngüsü).

## Önemli Notlar / Hatırlatmalar

- Her yeni karar `DECISIONS.md`'ye eklenmeli, eski kararlar silinmemeli.
- Yıkıcı git komutları (force push, reset --hard vb.) kullanıcı onayı olmadan
  çalıştırılmayacak - bu kural agent'ın kendi geliştirme sürecinde de geçerli.
- Commit'ler her task tamamlandığında mutlaka atılır (K25).
- Her task tamamlandığında `./run_tests.sh` çalıştırılıp tarihli rapor
  `test_reports/` altına kaydedilir (K26) - regresyon kontrolü için.
- README.md her task tamamlandığında güncel duruma göre güncellenir (K27).
