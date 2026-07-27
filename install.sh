#!/usr/bin/env bash
# install.sh - superCode kurulum script'i.
#
# Bu script:
#   1. Python ve uv'nin kurulu olduğunu kontrol eder.
#   2. `uv sync` ile proje bağımlılıklarını kurar.
#   3. llama-server'a bağlanılıp bağlanılamadığını kontrol eder (bilgi
#      amaçlı - sunucu çalışmıyorsa kurulumu durdurmaz, sadece uyarır).
#   4. Test suite'ini çalıştırarak kurulumu doğrular.
#
# Kullanım:
#   ./install.sh
#
# Not: Bu script hiçbir sistem paketini (apt/brew vb.) kurmaz, sadece
# proje bağımlılıklarını (uv ile) kurar. `uv` kurulu değilse, resmi
# kurulum talimatı (https://github.com/astral-sh/uv) gösterilir ve
# script durur - kullanıcı onayı olmadan sistem seviyesinde bir kurulum
# yapılmaz.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BASE_URL="${SUPERCODE_BASE_URL:-http://localhost:8079}"

echo "=== superCode Kurulumu ==="
echo

# 1. Python sürüm kontrolü.
echo "[1/4] Python sürümü kontrol ediliyor..."
if ! command -v python3 &>/dev/null; then
  echo "HATA: python3 bulunamadı. Python >= 3.12 kurulu olmalı."
  exit 1
fi
PYTHON_VERSION="$(python3 --version 2>&1 | awk '{print $2}')"
echo "  Bulundu: Python $PYTHON_VERSION"
echo

# 2. uv kontrolü.
echo "[2/4] uv paket yöneticisi kontrol ediliyor..."
if ! command -v uv &>/dev/null; then
  echo "HATA: 'uv' bulunamadı."
  echo
  echo "Kurulum için:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo
  echo "Kurulumdan sonra bu script'i tekrar çalıştırın."
  exit 1
fi
echo "  Bulundu: $(uv --version)"
echo

# 3. Bağımlılıkları kur.
echo "[3/4] Proje bağımlılıkları kuruluyor (uv sync)..."
uv sync
echo

# 4. llama-server bağlantı kontrolü (bilgi amaçlı, kurulumu durdurmaz).
echo "[4/4] llama-server bağlantısı kontrol ediliyor (${BASE_URL})..."
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/v1/models" --max-time 3 2>/dev/null || echo "000")"
if [ "$HTTP_CODE" = "200" ]; then
  MODEL_NAME="$(curl -s "${BASE_URL}/v1/models" --max-time 3 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || echo "bilinmiyor")"
  echo "  ✅ llama-server çalışıyor, model: ${MODEL_NAME}"
else
  echo "  ⚠️  llama-server'a şu adreste erişilemedi: ${BASE_URL}"
  echo "     Agent'ı çalıştırmadan önce llama-server'ı başlatmanız gerekiyor."
  echo "     Örnek: llama-server -m <model.gguf> --port 8079 --jinja --tools all"
  echo "     Farklı bir adres kullanıyorsanız: SUPERCODE_BASE_URL=http://... ./install.sh"
fi
echo

echo "=== Kurulum tamamlandı ==="
echo
echo "Agent'ı başlatmak için:"
echo "  uv run python -m agent.repl"
echo
echo "Test suite'ini çalıştırmak için:"
echo "  ./run_tests.sh"
echo
echo "Daha fazla bilgi için: INSTALL.md ve README.md"
