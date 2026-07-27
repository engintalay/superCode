# Kurulum ve Çalıştırma Kılavuzu

Bu doküman, superCode'u sıfırdan kurup çalıştırmak için gereken adımları
içerir.

## Gereksinimler

- **Python ≥ 3.12**
- **[`uv`](https://github.com/astral-sh/uv)** — Python paket yöneticisi
- **[`llama.cpp`](https://github.com/ggml-org/llama.cpp)** (`llama-server`
  binary'si) ve bir GGUF model dosyası

## 1. Hızlı Kurulum (Önerilen)

Proje kök dizininde:

```bash
./install.sh
```

Bu script:
1. Python ve `uv`'nin kurulu olduğunu kontrol eder.
2. `uv sync` ile proje bağımlılıklarını (`openai`, `pytest`) kurar.
3. `llama-server`'a `http://localhost:8079` adresinden bağlanmayı dener
   (bilgi amaçlı - sunucu çalışmıyorsa kurulumu durdurmaz, sadece uyarır).

Farklı bir adres/port kullanıyorsanız:

```bash
SUPERCODE_BASE_URL=http://localhost:9000 ./install.sh
```

`uv` kurulu değilse, script resmi kurulum komutunu gösterip durur (sistem
seviyesinde otomatik bir kurulum yapılmaz):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Manuel Kurulum

`install.sh` kullanmak istemiyorsanız, adımları elle yapabilirsiniz:

```bash
# 1. Bağımlılıkları kur
uv sync

# 2. (llama-server'ı ayrıca başlatmanız gerekiyor, bkz. aşağıdaki bölüm)

# 3. Kurulumu test et
./run_tests.sh
```

## 3. llama-server'ı Başlatma

superCode, kendi başına bir LLM çalıştırmaz - ayrı bir `llama-server`
sürecine OpenAI-uyumlu API üzerinden bağlanır. Örnek başlatma komutu:

```bash
llama-server \
  -m /path/to/model.gguf \
  --port 8079 \
  --host 0.0.0.0 \
  --jinja \
  --tools all \
  --ctx-size 65536 \
  --n-gpu-layers 99
```

**Önemli flag'ler:**
- `--jinja --tools all`: Native tool-calling desteği için zorunlu.
  Olmadan `tools=[...]` parametresi istekte yok sayılır.
- `--port 8079`: superCode'un varsayılan `base_url`'i bu porta bağlanır
  (`agent/llm_client.py` içindeki `DEFAULT_BASE_URL`). Farklı bir port
  kullanırsanız, `agent.repl.repl(base_url=...)` ile veya
  `agent/llm_client.py`'deki sabiti değiştirerek uyarlayabilirsiniz.

**Model seçimi hakkında not:** Projenin geçmiş kararlarında (bkz.
`DECISIONS.md` K1/K11) bazı modellerde (örn. Qwen2.5-Coder-14B, belirli
bir llama.cpp derlemesiyle) native tool-calling güvenilir çalışmadığı
gözlemlendi. `--jinja --tools all` ile başlattıktan sonra, gerçek bir
tool-call isteği göndererek doğrulamanız önerilir:

```bash
curl -s http://localhost:8079/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "MODEL_ADI",
    "messages": [{"role": "user", "content": "test.py dosyasını oku"}],
    "tools": [{"type": "function", "function": {"name": "read_file", "description": "oku", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
  }' | python3 -m json.tool
```

Yanıtta `message.tool_calls` alanı doluysa (boş/`null` değilse), model
native tool-calling'i güvenilir şekilde destekliyor demektir.

## 4. Agent'ı Çalıştırma

```bash
# Etkileşimli mod (onay gerektirir - varsayılan)
uv run python -m agent.repl

# Otonom mod (yazma/shell işlemleri onay istemez - yıkıcı komutlar hariç)
uv run python -m agent.repl --autonomous
```

Oturum içinde:
- `/autonomous on|off|status` — otonom modu değiştir
- `/exit`, `/quit`, veya Ctrl+D — çık

Agent, çalıştırıldığı dizini "proje kökü" kabul eder ve tüm dosya
işlemlerini (`read_file`, `edit_file`, `glob_search`, `grep_search`,
`run_shell`) bu dizinle sınırlar (path traversal engellenir).

## 5. Kurulumu Doğrulama (Test Suite)

```bash
./run_tests.sh
```

Bu, tüm test suite'ini çalıştırır ve `test_reports/` altına tarih damgalı
bir rapor kaydeder. `llama-server` çalışmıyorsa, sunucu gerektiren testler
otomatik olarak `SKIPPED` işaretlenir - suite bozulmaz, sadece o testler
atlanır.

Sadece belirli bir dosyayı/deseni test etmek için:

```bash
./run_tests.sh -k test_repl
```

## Sorun Giderme

**"llama-server'a bağlanılamadı" hatası:**
- `curl http://localhost:8079/v1/models` ile sunucunun çalıştığını doğrulayın.
- Port farklıysa, `SUPERCODE_BASE_URL` ile `install.sh`'ı tekrar çalıştırın
  veya `agent/llm_client.py`'deki `DEFAULT_BASE_URL`'i güncelleyin.

**Model tool-call üretmiyor / `content` içine JSON gömüyor:**
- `--jinja --tools all` flag'lerinin sunucu başlatma komutunda olduğunu
  doğrulayın.
- Yukarıdaki `curl` testiyle native tool-calling'i doğrulayın.
- Bazı modeller/derlemeler bu konuda güvenilmez olabilir (bkz.
  `DECISIONS.md` K1). `agent/tool_parsing.py` bir fallback sağlar ama
  en iyi deneyim için native tool-calling'i destekleyen bir model/derleme
  tercih edin.

**Testler `SKIPPED` görünüyor:**
- Bu, `llama-server`'ın çalışmadığı anlamına gelir - beklenen bir
  güvenlik davranışıdır (suite bozulmaz). Sunucuyu başlatıp tekrar deneyin.

**Bir test rastgele `FAILED` oluyor ama tekrar çalıştırınca geçiyor:**
- Bazı testler (özellikle gerçek modelle etkileşime giren entegrasyon
  testleri) modelin davranışsal non-determinism'ine bağlıdır - bu, kod
  hatası değildir. Bkz. `PROGRESS.md`'deki ilgili task notları.
