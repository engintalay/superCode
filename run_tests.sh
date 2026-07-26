#!/usr/bin/env bash
# run_tests.sh - Tüm unit/entegrasyon test suite'ini çalıştırır ve sonucu
# test_reports/ altına tarih damgalı bir dosya olarak kaydeder.
#
# Amaç: Her geliştirme adımından sonra bu script çalıştırılarak, önceki
# task'larda yazılan kodun/testlerin hâlâ çalıştığından emin olunur
# (regresyon kontrolü).
#
# Kullanım:
#   ./run_tests.sh                 # tüm testleri çalıştır, rapor oluştur
#   ./run_tests.sh -k test_repl     # sadece belirli testleri çalıştır
#
# Not: llama-server çalışmıyorsa sunucu gerektiren testler otomatik skip
# edilir (bkz. her test dosyasındaki requires_server / skipif kullanımı).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

REPORT_DIR="$PROJECT_ROOT/test_reports"
mkdir -p "$REPORT_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_FILE="$REPORT_DIR/test_report_${TIMESTAMP}.md"

echo "Testler çalıştırılıyor..."
echo

# pytest çıktısını CANLI olarak terminale akıt (tee), aynı zamanda rapor için
# bir dosyaya kaydet. `-v` ile her testin PASSED/FAILED/SKIPPED durumu ve
# yüzde ilerlemesi ([ %]) anlık olarak görünür.
RAW_OUTPUT_FILE="$(mktemp)"
trap 'rm -f "$RAW_OUTPUT_FILE"' EXIT

set +e
uv run pytest -v "$@" 2>&1 | tee "$RAW_OUTPUT_FILE"
PYTEST_EXIT_CODE="${PIPESTATUS[0]}"
set -e

PYTEST_OUTPUT="$(cat "$RAW_OUTPUT_FILE")"
echo

{
  echo "# Test Raporu - ${TIMESTAMP}"
  echo
  echo "- Tarih: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- Komut: \`uv run pytest -v $*\`"
  echo "- Çıkış kodu: ${PYTEST_EXIT_CODE}"
  echo "- Sonuç: $([ "$PYTEST_EXIT_CODE" -eq 0 ] && echo 'BAŞARILI ✅' || echo 'BAŞARISIZ ❌')"
  echo
  echo "## Ortam"
  echo
  echo "- Python: $(uv run python --version 2>&1)"
  echo "- llama-server durumu: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8079/v1/models --max-time 2 2>/dev/null | grep -q '^200$' && echo 'çalışıyor' || echo 'çalışmıyor/erişilemedi')"
  echo
  echo "## Pytest Çıktısı"
  echo
  echo '```'
  echo "$PYTEST_OUTPUT"
  echo '```'
} > "$REPORT_FILE"

echo "Rapor kaydedildi: $REPORT_FILE"

exit "$PYTEST_EXIT_CODE"
