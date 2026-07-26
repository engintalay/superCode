"""Read-only tool'lar (read_file, glob_search, grep_search) ve run_shell.

Karar referansları (bkz. DECISIONS.md):
- K5: MVP tool seti (read, glob/grep search, edit, shell).
- K7: Okuma her zaman serbest (onay gerektirmez); shell/yazma onay ister
  (onay mekanizması `agent/approval.py`'de, agent loop'ta uygulanır).
- K8: Proje dizini dışına çıkan işlemler ve yıkıcı komutlar onay ister -
  bu modülde path traversal koruması (`_resolve_within_root`) uygulanıyor,
  yıkıcı komut tespiti `agent/approval.py`'de.

Bu modül, hem tool'ların gerçek Python implementasyonlarını hem de
OpenAI-uyumlu `tools=[...]` isteğinde kullanılacak JSON schema
tanımlarını (`TOOL_DEFINITIONS`) içerir.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path
from typing import Any

MAX_READ_FILE_BYTES = 200_000
MAX_GREP_MATCHES = 200
MAX_GLOB_RESULTS = 500
SHELL_TIMEOUT_SECONDS = 30
MAX_SHELL_OUTPUT_BYTES = 50_000


class ToolError(Exception):
    """Tool çalıştırma sırasında oluşan, modele geri bildirilecek hata."""


def _resolve_within_root(path: str, root: Path) -> Path:
    """`path`'i `root` altında çözümler; `root` dışına çıkarsa hata verir.

    Path traversal (`../../etc/passwd` gibi) girişimlerini engeller.
    """
    root = root.resolve()
    candidate = (root / path).resolve() if not os.path.isabs(path) else Path(path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise ToolError(
            f"Erişim reddedildi: '{path}' proje dizini ({root}) dışına çıkıyor. "
            "Bu read-only araç sadece proje içinde çalışır."
        )
    return candidate


def read_file(path: str, root: str | Path = ".") -> str:
    """Bir dosyanın içeriğini metin olarak okur.

    Büyük dosyalar `MAX_READ_FILE_BYTES` ile kırpılır (modelin context'ini
    boşuna doldurmamak için).
    """
    root_path = Path(root)
    target = _resolve_within_root(path, root_path)

    if not target.exists():
        raise ToolError(f"Dosya bulunamadı: {path}")
    if not target.is_file():
        raise ToolError(f"'{path}' bir dosya değil.")

    try:
        data = target.read_bytes()
    except OSError as exc:
        raise ToolError(f"Dosya okunamadı: {path} ({exc})")

    truncated = len(data) > MAX_READ_FILE_BYTES
    if truncated:
        data = data[:MAX_READ_FILE_BYTES]

    text = data.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[... dosya {MAX_READ_FILE_BYTES} byte'ta kırpıldı ...]"
    return text


def glob_search(pattern: str, root: str | Path = ".") -> list[str]:
    """Verilen glob deseniyle eşleşen dosyaları proje kökü altında arar.

    Sonuçlar `root`'a göre relatif yol olarak döner, sıralanmış haldedir.
    """
    root_path = Path(root).resolve()
    matches: list[str] = []

    # `**/*.ext` gibi desenler kök dizindeki dosyalarla da eşleşsin diye
    # (fnmatch'in "**" için özel bir davranışı yok, `*` gibi davranır ama
    # `/` karakteri zorunlu hale getirir). `**/` önekini kaldırıp aynı
    # desenle bir de öneksiz eşleşmeyi deniyoruz.
    stripped_pattern = pattern[3:] if pattern.startswith("**/") else None

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Yaygın gürültü kaynaklarını dışla (performans + alaka için).
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "node_modules"}]

        for filename in filenames:
            full_path = Path(dirpath) / filename
            rel_path = full_path.relative_to(root_path).as_posix()
            is_match = (
                fnmatch.fnmatch(rel_path, pattern)
                or fnmatch.fnmatch(filename, pattern)
                or (stripped_pattern is not None and fnmatch.fnmatch(rel_path, stripped_pattern))
            )
            if is_match:
                matches.append(rel_path)
                if len(matches) >= MAX_GLOB_RESULTS:
                    break
        if len(matches) >= MAX_GLOB_RESULTS:
            break

    return sorted(matches)


def grep_search(query: str, root: str | Path = ".", file_pattern: str = "*") -> list[dict[str, Any]]:
    """Proje içinde metin arar, eşleşen dosya/satır/içerik listesi döner.

    Basit (regex olmayan) alt-dize araması yapar; büyük/küçük harf duyarsız.
    """
    root_path = Path(root).resolve()
    query_lower = query.lower()
    results: list[dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "node_modules"}]

        for filename in filenames:
            if not fnmatch.fnmatch(filename, file_pattern):
                continue

            full_path = Path(dirpath) / filename
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if query_lower in line.lower():
                    results.append(
                        {
                            "file": full_path.relative_to(root_path).as_posix(),
                            "line": line_no,
                            "content": line.strip(),
                        }
                    )
                    if len(results) >= MAX_GREP_MATCHES:
                        return results

    return results


def run_shell(command: str, root: str | Path = ".") -> dict[str, Any]:
    """Verilen shell komutunu proje kökünde çalıştırır, çıktısını döner.

    Onay mekanizması bu fonksiyonun DIŞINDA uygulanır (bkz. agent/approval.py,
    agent/repl.py) - bu fonksiyon sadece çalıştırma mantığını içerir, kendi
    başına bir güvenlik kontrolü yapmaz (çağıran taraf onayı almış olmalı).

    Çıktı `MAX_SHELL_OUTPUT_BYTES` ile kırpılır, komut `SHELL_TIMEOUT_SECONDS`
    sonra zaman aşımına uğrar (askıda kalan komutların agent'ı kilitlememesi
    için).
    """
    root_path = Path(root).resolve()

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=root_path,
            capture_output=True,
            timeout=SHELL_TIMEOUT_SECONDS,
            text=True,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"Komut {SHELL_TIMEOUT_SECONDS} saniye içinde tamamlanmadı (zaman aşımı).")
    except OSError as exc:
        raise ToolError(f"Komut çalıştırılamadı: {exc}")

    stdout = completed.stdout[:MAX_SHELL_OUTPUT_BYTES]
    stderr = completed.stderr[:MAX_SHELL_OUTPUT_BYTES]

    return {
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"


def _parse_search_replace_block(diff: str) -> tuple[str, str]:
    """Aider-tarzı search/replace bloğunu ayrıştırır (K6/K17).

    Beklenen format:
        <<<<<<< SEARCH
        (aranacak orijinal metin)
        =======
        (yeni metin)
        >>>>>>> REPLACE

    Döner: `(search_text, replace_text)`. Format hatalıysa `ToolError`.
    """
    if SEARCH_MARKER not in diff:
        raise ToolError(
            f"Geçersiz düzenleme formatı: '{SEARCH_MARKER}' işaretçisi bulunamadı. "
            "Format: <<<<<<< SEARCH\\n(eski metin)\\n=======\\n(yeni metin)\\n>>>>>>> REPLACE"
        )
    if DIVIDER_MARKER not in diff:
        raise ToolError(f"Geçersiz düzenleme formatı: '{DIVIDER_MARKER}' ayırıcısı bulunamadı.")
    if REPLACE_MARKER not in diff:
        raise ToolError(f"Geçersiz düzenleme formatı: '{REPLACE_MARKER}' işaretçisi bulunamadı.")

    try:
        _, rest = diff.split(SEARCH_MARKER, 1)
        search_text, rest = rest.split(DIVIDER_MARKER, 1)
        replace_text, _ = rest.split(REPLACE_MARKER, 1)
    except ValueError:
        raise ToolError("Geçersiz düzenleme formatı: işaretçiler beklenen sırada değil.")

    # İlk/son satırdaki tek bir yeni satırı temizle (marker'lardan hemen
    # sonra/önce gelen \n ayırıcı amaçlıdır, içeriğin parçası değildir).
    search_text = search_text[1:] if search_text.startswith("\n") else search_text
    replace_text = replace_text[1:] if replace_text.startswith("\n") else replace_text
    search_text = search_text[:-1] if search_text.endswith("\n") else search_text
    replace_text = replace_text[:-1] if replace_text.endswith("\n") else replace_text

    return search_text, replace_text


def edit_file(path: str, diff: str, root: str | Path = ".") -> str:
    """Aider-tarzı search/replace bloğuyla bir dosyayı düzenler (K6/K17).

    `diff`, `_parse_search_replace_block` formatına uygun olmalı. Arama
    metni dosyada TAM OLARAK BİR KEZ bulunmalı - hiç bulunamazsa veya
    birden fazla bulunursa (belirsizlik, küçük modelin en sık yaptığı
    hata türü) işlem reddedilir ve modele açık bir hata mesajı döner.
    """
    root_path = Path(root)
    target = _resolve_within_root(path, root_path)

    if not target.exists():
        raise ToolError(f"Dosya bulunamadı: {path}")
    if not target.is_file():
        raise ToolError(f"'{path}' bir dosya değil.")

    search_text, replace_text = _parse_search_replace_block(diff)

    if search_text == "":
        raise ToolError("SEARCH bloğu boş olamaz - düzenlenecek metni belirtmelisiniz.")

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Dosya okunamadı: {path} ({exc})")

    occurrences = original.count(search_text)
    if occurrences == 0:
        raise ToolError(
            f"SEARCH bloğu '{path}' dosyasında bulunamadı. Metnin dosyadaki "
            "haliyle (boşluk/girinti dahil) BİREBİR eşleşmesi gerekir."
        )
    if occurrences > 1:
        raise ToolError(
            f"SEARCH bloğu '{path}' dosyasında {occurrences} kez bulundu - "
            "belirsiz, hangi eşleşmenin değiştirileceği anlaşılamıyor. "
            "SEARCH bloğuna daha fazla bağlam (çevresindeki satırlar) ekleyin."
        )

    updated = original.replace(search_text, replace_text, 1)
    try:
        target.write_text(updated, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Dosya yazılamadı: {path} ({exc})")

    return f"'{path}' başarıyla düzenlendi (1 değişiklik uygulandı)."


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Bir dosyanın içeriğini okur. Sadece proje dizini içindeki dosyalar okunabilir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Proje köküne göre relatif veya mutlak dosya yolu.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "Verilen glob desenine (örn. '*.py', '**/*.md') uyan dosyaları proje içinde arar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob deseni, örn. '*.py' veya 'src/*.ts'.",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Proje içindeki dosyalarda verilen metni arar, eşleşen dosya/satır/içerik listesini döner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Aranacak metin (büyük/küçük harf duyarsız, alt-dize araması).",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Aramanın sınırlandırılacağı dosya glob deseni (varsayılan: '*', tüm dosyalar).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Bir dosyayı search/replace bloğuyla düzenler. Yazma işlemi olduğu için "
                "kullanıcı onayı gerektirir. `diff` formatı: "
                "'<<<<<<< SEARCH\\n(dosyadaki birebir eşleşecek eski metin)\\n"
                "=======\\n(yeni metin)\\n>>>>>>> REPLACE'. "
                "ÖNEMLİ: SEARCH bloğu, dosyadaki satırı BOŞLUK/GİRİNTİ dahil "
                "birebir aynı şekilde içermelidir (örn. 4 boşluklu girinti varsa "
                "SEARCH bloğunda da aynı 4 boşluk olmalı). SEARCH bloğu dosyada "
                "TAM OLARAK BİR KEZ bulunmalı; birden fazla veya sıfır eşleşme "
                "işlemi reddeder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Düzenlenecek dosyanın proje köküne göre relatif yolu.",
                    },
                    "diff": {
                        "type": "string",
                        "description": (
                            "'<<<<<<< SEARCH\\n...\\n=======\\n...\\n>>>>>>> REPLACE' "
                            "formatında search/replace bloğu."
                        ),
                    },
                },
                "required": ["path", "diff"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Verilen shell komutunu proje dizininde çalıştırır. "
                "Yazma/etkili bir işlem olduğu için kullanıcı onayı gerektirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Çalıştırılacak shell komutu (örn. 'ls -la', 'pytest').",
                    }
                },
                "required": ["command"],
            },
        },
    },
]


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "glob_search": glob_search,
    "grep_search": grep_search,
    "edit_file": edit_file,
    "run_shell": run_shell,
}


def execute_tool(name: str, arguments: dict[str, Any], root: str | Path = ".") -> Any:
    """İsme göre tool'u bulup çalıştırır, sonucu döner.

    Model bazen argüman adlarını yanlış büyük/küçük harfle üretebiliyor
    (örn. "Pattern" yerine "pattern" beklenirken) - bu fonksiyon argüman
    adlarını küçük harfe normalize ederek bu tür küçük hataları tolere eder.

    Bilinmeyen tool adı, bilinmeyen argüman veya `ToolError` durumunda hata
    modele geri bildirilecek bir mesaj olarak yakalanmalı - bu fonksiyon
    exception'ı olduğu gibi fırlatır, çağıran (agent loop) yakalayıp mesaja
    çevirir.
    """
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        raise ToolError(f"Bilinmeyen tool: {name}")

    normalized_arguments = {key.lower(): value for key, value in arguments.items()}
    try:
        return func(root=root, **normalized_arguments)
    except TypeError as exc:
        raise ToolError(f"'{name}' için geçersiz argümanlar: {exc}")
