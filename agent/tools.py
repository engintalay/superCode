"""Read-only tool'lar: read_file, glob_search, grep_search.

Karar referansları (bkz. DECISIONS.md):
- K5: MVP tool seti (read, glob/grep search, edit, shell).
- K7: Okuma her zaman serbest (onay gerektirmez).
- K8: Proje dizini dışına çıkan işlemler onay ister - bu task'ta henüz
  onay mekanizması yok (Task 4'te gelecek), ama read-only tool'lar da
  proje kökü dışına path traversal ile çıkamasın diye temel bir sınır
  (`_resolve_within_root`) burada uygulanıyor.

Bu modül, hem tool'ların gerçek Python implementasyonlarını hem de
OpenAI-uyumlu `tools=[...]` isteğinde kullanılacak JSON schema
tanımlarını (`TOOL_DEFINITIONS`) içerir.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

MAX_READ_FILE_BYTES = 200_000
MAX_GREP_MATCHES = 200
MAX_GLOB_RESULTS = 500


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
]


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "glob_search": glob_search,
    "grep_search": grep_search,
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
