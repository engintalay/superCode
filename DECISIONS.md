# Proje Kararları - Local Coding Agent

Bu doküman, projenin gereksinim toplama ve tasarım sürecinde alınan tüm kararları,
elenen seçenekleri ve gerekçelerini kronolojik sırayla tutar.

**Kural:** Bir karar değiştirildiğinde eski karar SİLİNMEZ. Değişiklik, "Güncelleme"
bölümü olarak eski kararın altına eklenir ve nedeni yazılır.

---

## Proje Tanımı

Kiro CLI benzeri, ama local AI modellerini (llama.cpp üzerinden) kullanan, daha basit
ve daha kısıtlı kaynaklı ortamlar için tasarlanmış bir agentic coding agent.
Öncelik: kısıtlı kaynaklı küçük modelin başarısız/belirsiz olduğu durumlarda döngüye
girmeden durup kullanıcıya bilgi vermesi.

---

## Karar Kaydı

### K1: Model Backend
- **Seçilen:** llama.cpp `llama-server`, OpenAI-uyumlu `/v1/chat/completions` API,
  `--jinja` flag ile native tool-calling desteği.
- **Elenen seçenekler:**
  - Ollama (yaygın, kolay kurulum) — kullanıcının zaten llama.cpp kurulu olması nedeniyle tercih edilmedi.
  - LM Studio / diğer OpenAI-uyumlu local server'lar — aynı nedenle değerlendirilmedi.
- **Gerekçe:** Kullanıcının ortamında llama.cpp zaten kurulu.
- **Doğrulama (araştırma):** llama.cpp resmi dokümantasyonu (`function-calling.md`),
  Qwen2.5-Coder GGUF modellerinin "Hermes 2 Pro" native tool-call formatıyla eşleştiğini
  doğruluyor. `llama-server --jinja` flag'i ile yapılandırılmış `tool_calls` JSON'u
  güvenilir şekilde alınabiliyor. Uyarı: KV cache'in agresif quantize edilmesi
  (örn. `-ctk q4_0`) tool-calling kalitesini düşürüyor, bundan kaçınılmalı.

### K2: Programlama Dili ve Platform
- **Seçilen:** Python.
- **Elenen seçenekler:**
  - Rust — performans ve tek binary dağıtım avantajı olsa da, kullanıcı "her tarafta
    sorunsuz çalışır" gerekçesiyle Python'u tercih etti.
  - TypeScript/Node.js — değerlendirilmedi.
- **Gerekçe:** Python, AI/ML ekosisteminde en yaygın ve platformlar arası sorunsuz çalışıyor.

### K3: Agent Kapsamı (Tool Yetenekleri)
- **Seçilen:** Tam agentic — dosya okuma/düzenleme + shell komutu çalıştırma, hata
  durumunda erken durma mekanizması kritik.
- **Elenen seçenekler:**
  - Sadece dosya okuma/analiz (düşük risk, salt-okunur).
  - Dosya düzenleme + basit komut çalıştırma (Kiro'dan daha sınırlı tool seti).
- **Gerekçe:** Kullanıcı, Kiro'ya yakın ama basitleştirilmiş tam agentic bir deneyim istedi.

### K4: Çuvallama Tespiti (Loop/Hata Sinyalleri)
- **Seçilen:** Katmanlı koruma — üç sinyal birlikte çalışır:
  1. Tekrar sayacı (aynı/benzer tool çağrısı art arda)
  2. Adım/tur limiti (toplam X turda ilerleme yoksa dur)
  3. Belirsizlik tespiti (model "bilmiyorum" der veya tool çağrısı parse edilemezse)
- **Elenen seçenekler:**
  - Sadece tekrar sayacı (tek katman, yetersiz bulundu).
  - Sadece adım limiti (tek katman, yetersiz bulundu).
  - Sadece belirsizlik tespiti (tek katman, yetersiz bulundu).
- **Gerekçe:** Tek bir sinyal yeterli koruma sağlamaz; üçü birlikte daha güvenilir.

### K5: MVP Tool Seti
- **Seçilen:** Kiro-benzeri genişletilmiş set — `read`, `edit` (diff-based),
  `glob`/`grep` search, `shell` (5 tool).
- **Elenen seçenekler:**
  - Minimal set: `read_file`, `write_file`, `run_shell` (3 tool).
  - Sadece shell — her şeyi shell komutlarına (cat, sed, find, grep) devretmek.
- **Gerekçe:** Kiro'ya yakın deneyim istendiği için genişletilmiş set seçildi.

### K6: Edit (Kod Düzenleme) Formatı
- **Seçilen:** Search/replace bloğu (Aider-tarzı, `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE`).
- **Elenen seçenekler:**
  - Satır numarasıyla düzenleme — küçük modeller satır numarasını genelde yanlış
    hesapladığı için riskli bulundu.
  - Tam dosya yeniden yazımı — küçük modellerde token/context sınırına çabuk
    çarptığı için elendi.
- **Gerekçe:** Kullanıcı Aider formatının referans alınmasını istedi.
- **Doğrulama (araştırma):** Aider'ın resmi blog yazısı (aider.chat/2023/12/21/unified-diffs.html),
  JSON'a kod gömmenin escape sorunları yarattığını, satır numarası tabanlı formatların
  modeller için güvenilmez olduğunu doğruluyor. Search/replace, en az hata yapılan
  basit formatlardan biri olarak değerlendirildi.

### K7: Onay/Güvenlik Mekanizması
- **Seçilen:** Okuma her zaman serbest; yazma/shell işlemleri için varsayılan onay
  gerekli; kullanıcı tam otonom moda geçebilir (onayları kapatan bir flag/komut).
- **Elenen seçenekler:**
  - Her tool çağrısından önce onay (en güvenli ama yavaş, ademe elendi).
  - Tam otonom, onay hiç yok (riskli, elendi).
- **Gerekçe:** Kullanıcı dengeli bir yaklaşım istedi: okuma serbest, yazma/shell onaylı,
  ama otonom mod seçeneği de bulunsun.

### K8: Otonom Modda Mutlak Güvenlik Sınırları
- **Seçilen:** Otonom mod açıkken bile hem (a) yıkıcı/geri alınamaz işlemler
  (rm -rf, git push --force, git reset --hard vb.) HEM DE (b) proje dizini dışına
  çıkan işlemler onay ister. Bu, otonom modun asla bypass edemeyeceği mutlak bir sınırdır.
- **Elenen seçenekler:**
  - Otonom modda hiçbir istisna olmadan her şeyin otomatik geçmesi — reddedildi.
  - Sadece proje dizini dışı işlemlerin onay istemesi (yıkıcı komut istisnası olmadan) — kullanıcı ikisini birlikte istedi.
- **Gerekçe:** Kaynakları kısıtlı/küçük bir modelin hata yapma riski yüksek;
  geri alınamaz zararın önüne mutlak bir güvenlik ağı gerekiyor.

### K9: Loop/Hata Tespiti Sonrası Davranış
- **Seçilen:** Dur, durumu özetle (ne denendi, neden çuvalladı), varsa 2-3 alternatif
  öner, mutlaka kullanıcı onayı/yönü bekle. Bu davranış otonom modda da değişmez.
- **Elenen seçenekler:**
  - Sadece log'a yazıp kullanıcıya sormadan devam etmek — döngüye girmeme hedefiyle
    çeliştiği için reddedildi.
- **Gerekçe:** Kullanıcının ana önceliği "döngüye girmemek"; bu karar doğrudan o hedefe hizmet ediyor.

### K10: Proje Bağlamı
- **Seçilen:** Sıfırdan yeni Python projesi, superCode reposu içinde.
- **Elenen seçenekler:**
  - Mevcut bir taslak/kod üzerine inşa etmek — repo boş olduğu için (doğrulandı,
    `glob *` sonucu 0 dosya) bu seçenek geçersizdi.
- **Gerekçe:** Repo boş, sıfırdan başlanacak.

### K11: Hedef Donanım / Model Boyutu
- **Seçilen:** Farklı model boyutlarına uyumlu tasarım. Başlangıç/test modeli:
  Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf. İleride daha güçlü donanım/API ile
  büyütülebilir (örn. Qwen Coder Next gibi daha güçlü bir model).
- **Elenen seçenekler:**
  - Sadece CPU-only/küçük GPU (7B-8B) hedeflemek — tek boyuta kilitlenmemek için elendi.
  - Sadece orta seviye GPU (13B-34B) hedeflemek — aynı nedenle elendi.
- **Gerekçe:** Kullanıcının donanımı zamanla değişebilir, esneklik isteniyor.

### K12: Kullanıcı Arayüzü
- **Seçilen:** Etkileşimli REPL/chat modu (Kiro CLI deneyimine yakın).
- **Elenen seçenekler:**
  - Tek seferlik komut modu (`agent "görevi yap"`) — otomasyon senaryosu için
    değerlendirilmedi, öncelik değil.
  - İkisi birden — MVP kapsamı dışında bırakıldı, sadece REPL ile başlanacak.
- **Gerekçe:** Kiro CLI deneyimine en yakın seçenek REPL.

### K13: Context/Geçmiş Yönetimi
- **Seçilen:** Özetleme — context limiti yaklaşınca geçmiş, ayrı bir LLM çağrısıyla özetlenir.
- **Elenen seçenekler:**
  - Basit kesme (sliding window) — eski kararları/bağlamı unutabileceği için elendi.
  - Sabit tur limiti + manuel `/clear` — otomatik yönetim olmadığı, kullanıcıya
    yük bindirdiği için elendi.
- **Gerekçe:** Bağlamı koruma, otomatik ve öngörülebilir bir deneyim sağlamak.

### K14: Otonom Mod Kapsamı (K7/K8'in netleştirilmesi)
- **Seçilen:** K7 ve K8'de belirtilen kural netleştirildi: okuma her zaman serbest;
  yazma/shell için onay varsayılan; kullanıcı otonom moda geçebilir; yıkıcı komutlar
  VE proje-dışı erişimler otonom modda da her koşulda onay ister.
- **Not:** Bu, K7 ve K8'in birleştirilmiş/teyit edilmiş hâlidir, çelişki yok.

### K15: Kod Tabanı / Proje Bağlamı Onayı
- **Seçilen:** K10 ile aynı, teyit edildi — sıfırdan yeni proje.

### K16: llama.cpp Ortam Hazırlığı
- **Seçilen:** Kullanıcının llama.cpp kurulumu `--jinja` flag'ini destekliyor,
  Qwen2.5-Coder-14B GGUF dosyası hazır. "Ortam doğrulama" adımına gerek yok,
  direkt doğru başlatma komutu plana kondu.
- **Elenen seçenekler:**
  - Plana ayrı bir "ortam doğrulama" adımı eklemek — kullanıcı ortamın hazır
    olduğunu belirttiği için gereksiz görüldü.

### K17: Edit Format Referansı (K6'nın netleştirilmesi)
- **Seçilen:** Aider'ın search/replace formatı doğrudan referans alınacak (kendi
  formatını tasarlamak yerine).
- **Elenen seçenekler:**
  - Kendi minimal formatını tasarlamak — kanıtlanmış bir format olduğu için elendi.

### K18: Paket Yöneticisi
- **Seçilen:** `uv` — modern, hızlı, tek dosya lock, git ile kolay yönetim.
- **Elenen seçenekler:**
  - `pip` + `venv` — en basit olsa da, `uv`'nin modern tooling avantajları
    (hız, lock dosyası, dependency resolution) nedeniyle elendi.
- **Gerekçe:** Kullanıcı "modern olalım" dedi, uv önerisi onaylandı.

### K19: Tekrar Tespiti - "Aynı Tool Call" Tanımı (K4'ün detaylandırılması)
- **Seçilen:** Tool adı + parametreler benzer olsa da (örn. aynı dosya farklı satır)
  tekrar olarak sayılabilecek fuzzy/benzerlik tabanlı bir yaklaşım.
- **Elenen seçenekler:**
  - Sadece tam eşleşme (tool adı + parametreler bire bir aynı) — daha basit ama
    yetersiz bulundu, kullanıcı daha akıllı bir tespiti tercih etti.
- **Gerekçe:** Küçük model aynı hatayı ufak varyasyonlarla tekrarlayabilir
  (örn. aynı dosyada farklı satırı düzenlemeye çalışmak); tam eşleşme bunu yakalayamaz.

### K20: Tool-Call Adımlama Stratejisi (Tek vs Paralel)
- **Seçilen:** İki durumlu yaklaşım:
  - Genel agent loop'u: tek adımda tek tool çağrısı (ReAct-tarzı), küçük model
    için daha öngörülebilir.
  - Bağımsız işler için: kullanıcının donanımında multi-thread ile 2-3x hız
    kazanımı olduğu belirtildi (1 thread: 10-15 t/s, 2-3 thread: 2-3x hız).
    Bu nedenle bağımsız/paralelleştirilebilir işler için paralel çalıştırma
    desteği de plana eklenecek (bkz. K21, K22).
- **Gerekçe:** Tek-thread tutarlılığı ana akış için korunurken, kaynak potansiyeli
  (multi-thread hız kazancı) bağımsız işler için değerlendirmeye alındı.

### K21: Paralel Çalıştırmanın Tetiklenmesi
- **Seçilen:** Belirli tool'lar otomatik paralel çalışır — örn. glob/grep sonucu
  birden fazla dosya bulunduğunda, bağımsız okuma/analiz işlemleri otomatik
  paralelleştirilir. Tek bir mantıksal görev/edit akışı her zaman tek thread kalır.
- **Elenen seçenekler:**
  - Modelin kendi kararıyla alt-görevlere bölüp paralel dağıtması — küçük/kısıtlı
    modelin doğru bölme kararı veremeyebileceği riski nedeniyle elendi.
  - Kullanıcının açıkça "bu N dosyayı paralel analiz et" diye tetiklemesi —
    kullanıcı bunun yerine otomatik/örtük tetiklemeyi (c seçeneği) tercih etti.
- **Gerekçe:** "En güvenlisi" olarak değerlendirildi — model karar vermek zorunda
  kalmıyor, kural bazlı ve öngörülebilir bir mekanizma.

### K22: Paralel Mimari (llama-server tarafı)
- **Seçilen:** Tek `llama-server` process'i, `--parallel N` flag'i ile çoklu slot
  yönetimi. Aynı modeli tekrar yüklemeye gerek yok.
- **Elenen seçenekler:**
  - Birden fazla `llama-server` process'i (farklı portlarda) — daha fazla
    RAM/VRAM kullanımı (aynı modelin N kere yüklenmesi) gerektirdiği için elendi.
- **Gerekçe:** Kaynaklar kısıtlı; tek process + `--parallel` daha az overhead ile
  aynı paralellik faydasını sağlıyor.

### K23: Faz Ayrımı (Paralellik MVP'den Ayrıldı)
- **Seçilen:** Paralellik özelliği (K20-K22) MVP'nin (Faz 1) dışına alındı;
  önce tek-thread temel agent sağlam kurulacak, paralellik Faz 2'de eklenecek.
- **Gerekçe:** Küçük artımlı adımlar ilkesiyle örtüşüyor; MVP karmaşıklığını
  kontrol altında tutmak için kullanıcı tarafından onaylandı.

### K24: Kalıcı Karar Dokümantasyonu ve Git Deposu
- **Seçilen:** Tüm gereksinim/tasarım kararları bu dosyada (`DECISIONS.md`)
  kalıcı olarak tutulacak. Her yeni karar bu dosyaya eklenecek. Eski kararlar
  değiştirilirse silinmeyecek, "değiştirildi" notu ve nedeniyle işaretlenecek.
  Proje için bir git deposu oluşturulacak.
- **Gerekçe:** Kararların izlenebilirliği ve gerekçelerin kalıcı kaydı istendi.

### K25: Commit Zamanlaması
- **Seçilen:** Her task tamamlandığında (Task 1, Task 2, ... Task 11) mutlaka
  bir commit atılır. Bu, K24'teki "commit'ler sadece kullanıcı açıkça
  istediğinde atılır" kuralının netleştirilmesidir: task tamamlanması,
  kullanıcının önceden verdiği açık bir commit talebi olarak sayılır.
- **Elenen seçenekler:**
  - Sadece kullanıcı her seferinde ayrıca "commit at" dediğinde atmak —
    kullanıcı bunun tasklar için varsayılan davranış olmasını istedi.
- **Gerekçe:** Kullanıcı, task bazlı ilerlemenin git geçmişinde izlenebilir
  olmasını istedi.

---

## Henüz Karar Verilmemiş / Açık Konular

Aşağıdaki konular tasarım planında yer aldı ama henüz kullanıcı tarafından
teyit edilen ayrı bir "karar" statüsünde değil; implementasyon sırasında
netleşecek teknik detaylardır:

- Loop detector'daki fuzzy benzerlik eşiğinin (örn. Levenshtein/parametre
  benzerlik skoru) tam sayısal değeri.
- Context özetleme tetikleme eşiği (token sayısı/oranı).
- Belirsizlik tespiti için kullanılacak tam heuristik/regex seti.

Bu konular ilgili görev (Task 6, Task 8) uygulanırken netleştirilip bu dosyaya
yeni bir karar kaydı olarak eklenecektir.
