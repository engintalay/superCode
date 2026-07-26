"""Onay mekanizması (Approval Gate) - yazma/shell işlemleri için.

Karar referansları (bkz. DECISIONS.md):
- K7: Okuma her zaman serbest; yazma/shell işlemleri için varsayılan onay
  gerekli; kullanıcı tam otonom moda geçebilir.
- K8/K14: Otonom mod açıkken bile (a) yıkıcı/geri alınamaz işlemler VE
  (b) proje dizini dışına çıkan işlemler onay ister - bu mutlak bir
  sınırdır, otonom mod bunu asla bypass edemez.

Bu modül, bir tool çağrısının onay gerektirip gerektirmediğine karar veren
ve (gerektiğinde) kullanıcıdan onay isteyen mantığı içerir. Gerçek
kullanıcı etkileşimi (input()) test edilebilirlik için ayrı bir fonksiyona
(`prompt_user_confirmation`) izole edilmiştir.
"""

from __future__ import annotations

import re
from pathlib import Path

# Read-only olarak kabul edilen tool'lar - hiçbir zaman onay istemez (K7).
READ_ONLY_TOOLS = {"read_file", "glob_search", "grep_search"}

# Yazma/etkili tool'lar - varsayılan olarak onay ister (K7), otonom modda
# otomatik geçer (K8'deki mutlak sınırlar hariç).
APPROVAL_REQUIRED_TOOLS = {"run_shell", "write_file", "edit_file"}

# Yıkıcı/geri alınamaz kabul edilen komut desenleri (K8). Bunlar otonom
# modda DA onay ister - mutlak sınır, bypass edilemez.
_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*)\b",  # rm -rf, rm -fr, rm -Rf, vb.
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+.*-f",
    r"\bgit\s+branch\s+.*-D\b",
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    r"\bchmod\s+-R\s+000\b",
    r"\b:\(\)\s*\{\s*:\|:&\s*\};\s*:",  # fork bomb
    r">\s*/dev/sd[a-z]\b",
]
_DESTRUCTIVE_REGEX = re.compile("|".join(_DESTRUCTIVE_PATTERNS), re.IGNORECASE)


class ApprovalDenied(Exception):
    """Kullanıcı onay istenen bir işlemi reddettiğinde fırlatılır."""


def is_read_only_tool(name: str) -> bool:
    return name in READ_ONLY_TOOLS


def is_destructive_shell_command(command: str) -> bool:
    """Komutun K8'de tanımlı yıkıcı/geri alınamaz kalıplardan birine
    uyup uymadığını kontrol eder."""
    return bool(_DESTRUCTIVE_REGEX.search(command))


def is_outside_project(path: str, project_root: str | Path) -> bool:
    """Verilen yolun proje kökü dışına çıkıp çıkmadığını kontrol eder."""
    root = Path(project_root).resolve()
    candidate = Path(path)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    try:
        candidate.relative_to(root)
        return False
    except ValueError:
        return True


def requires_approval(
    tool_name: str,
    arguments: dict,
    *,
    autonomous_mode: bool,
    project_root: str | Path = ".",
) -> tuple[bool, str | None]:
    """Bir tool çağrısının onay gerektirip gerektirmediğine karar verir.

    Döner: `(onay_gerekli, sebep)`. `sebep` None ise onay gerekmiyor.

    Mantık (K7/K8/K14):
    1. Read-only tool'lar hiçbir zaman onay istemez.
    2. Yazma/shell tool'ları normalde onay ister; ama `autonomous_mode=True`
       ise otomatik geçer - AŞAĞIDAKİ İKİ İSTİSNA HARİÇ (mutlak sınır):
       a. Komut yıkıcı/geri alınamaz bir kalıba uyuyorsa (shell tool'u için).
       b. Hedef yol proje kökü dışına çıkıyorsa (dosya bazlı tool'lar için).
       Bu iki durumda otonom mod bile onay ister.
    """
    if is_read_only_tool(tool_name):
        return False, None

    # Mutlak sınır (a): yıkıcı shell komutu - otonom modda BİLE onay ister.
    if tool_name == "run_shell":
        command = str(arguments.get("command", ""))
        if is_destructive_shell_command(command):
            return True, (
                "Bu komut yıkıcı/geri alınamaz olarak sınıflandırıldı "
                "(örn. rm -rf, git push --force, git reset --hard vb.). "
                "Otonom mod bu tür işlemleri asla otomatik onaylamaz (K8)."
            )

    # Mutlak sınır (b): proje dışına çıkan dosya işlemi - otonom modda BİLE onay ister.
    path_arg = arguments.get("path")
    if path_arg and is_outside_project(str(path_arg), project_root):
        return True, (
            f"Hedef yol ('{path_arg}') proje dizini dışına çıkıyor. "
            "Otonom mod proje-dışı erişimleri asla otomatik onaylamaz (K8)."
        )

    if tool_name not in APPROVAL_REQUIRED_TOOLS:
        # Bilinmeyen/tanımsız tool - güvenli taraf: onay iste.
        return True, f"Tanımlanmamış tool '{tool_name}' için varsayılan olarak onay isteniyor."

    if autonomous_mode:
        return False, None

    return True, f"'{tool_name}' bir yazma/etkili işlem, varsayılan olarak onay gerekir (K7)."


def prompt_user_confirmation(tool_name: str, arguments: dict, reason: str) -> bool:
    """Kullanıcıya tool çağrısını gösterip onay ister. Onaylanırsa True döner."""
    print(f"\n[ONAY GEREKLİ] {reason}")
    print(f"  Tool: {tool_name}")
    print(f"  Argümanlar: {arguments}")
    answer = input("Bu işlemi çalıştırmama izin veriyor musunuz? [e/h]: ").strip().lower()
    return answer in {"e", "evet", "y", "yes"}
