"""Paralel tool execution altyapısı (Faz 2 - Task 10).

Karar referansları (bkz. DECISIONS.md):
- K20: Genel agent loop tek adımda tek tool çağrısı kalır (ReAct-tarzı,
  küçük model için öngörülebilir). Paralellik SADECE bağımsız/
  paralelleştirilebilir işler için ayrı bir mekanizma olarak eklenir.
- K21: Paralel çalıştırma OTOMATİK/ÖRTÜK tetiklenir - modelin kendi
  kararıyla alt-görevlere bölmesi YA DA kullanıcının açıkça istemesi
  DEĞİL. Kural bazlı tetikleme: `glob_search`/`grep_search` sonucu
  birden fazla dosya bulunduğunda, bu dosyaların okunması otomatik
  olarak paralelleştirilir.
- K22: llama-server tarafında tek process + çoklu slot (`total_slots`)
  ile paralellik sağlanıyor (gerçek ortamda doğrulandı: 3 eşzamanlı
  istek, sıralıya göre ~%32 daha hızlı tamamlandı - bkz. K22 güncellemesi).

Bu modül, `read_file` gibi BAĞIMSIZ (birbirine veri bağımlılığı olmayan)
tool çağrılarını `concurrent.futures.ThreadPoolExecutor` ile eşzamanlı
çalıştıran bir yardımcı sağlar. Ağ G/Ç'ye (LLM'e istek) veya disk G/Ç'ye
(dosya okuma) dayalı işler için thread-based paralellik yeterlidir (GIL
sorun yaratmaz, çünkü asıl bekleme I/O'da).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

# Bir glob/grep sonucunda kaç dosyaya kadar otomatik paralel okuma
# tetiklenir. Çok fazla dosya varsa (örn. yüzlerce), hepsini paralel
# okumak context'i patlatır - bu yüzden bir üst sınır var.
MAX_PARALLEL_FILES = 8

# Eşzamanlı çalışacak maksimum worker (thread) sayısı. Sunucudaki
# `total_slots` ile uyumlu, makul bir üst sınır (K22'de 4 slot görüldü).
MAX_WORKERS = 4


def run_parallel(tasks: list[Callable[[], Any]], max_workers: int = MAX_WORKERS) -> list[Any]:
    """Bağımsız (birbirine bağımlı olmayan) fonksiyonları eşzamanlı çalıştırır.

    `tasks`: argümansız çağrılabilir (`lambda` veya `functools.partial`)
    listesi. Sonuçlar, GİRİŞ SIRASIYLA aynı sırada döner (hangi task'ın
    hangi sonuca ait olduğu karışmaz).

    Bir task exception fırlatırsa, o task'ın sonucu exception objesinin
    kendisi olur (fırlatılmaz) - çağıran taraf `isinstance(r, Exception)`
    ile kontrol edip hangi task'ların başarısız olduğunu ayırt edebilir.
    """
    if not tasks:
        return []
    if len(tasks) == 1:
        # Tek görev için thread pool overhead'ine gerek yok.
        try:
            return [tasks[0]()]
        except Exception as exc:  # noqa: BLE001 - kasıtlı: hata sonuç olarak döner
            return [exc]

    def _safe_call(task: Callable[[], Any]) -> Any:
        try:
            return task()
        except Exception as exc:  # noqa: BLE001
            return exc

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # executor.map GİRİŞ SIRASINI korur (concurrent.futures garantisi).
        return list(executor.map(_safe_call, tasks))


def should_parallelize_file_reads(file_paths: list[str]) -> bool:
    """K21: Bir glob/grep sonucunun paralel okumayı tetikleyip
    tetiklemeyeceğine karar verir.

    Birden fazla (2+) ve MAX_PARALLEL_FILES'tan az/eşit dosya varsa True.
    """
    return 2 <= len(file_paths) <= MAX_PARALLEL_FILES


def read_files_in_parallel(
    file_paths: list[str],
    read_func: Callable[[str], Any],
) -> dict[str, Any]:
    """Verilen dosya yollarını paralel olarak okur (K21).

    `read_func`: tek bir dosya yolunu alıp içeriğini/sonucunu döndüren
    fonksiyon (örn. `agent.tools.read_file`'ın `root`'a bağlı bir partial'ı).

    Döner: `{dosya_yolu: sonuç_veya_exception}` sözlüğü. Bir dosya
    okunamazsa (ToolError vb.), o dosyanın değeri exception objesi olur -
    diğer dosyaların okunmasını engellemez.
    """
    paths = file_paths[:MAX_PARALLEL_FILES]
    tasks = [(lambda p=path: read_func(p)) for path in paths]
    results = run_parallel(tasks)
    return dict(zip(paths, results))
