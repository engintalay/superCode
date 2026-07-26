"""Test suite genelinde paylaşılan yardımcılar.

`_server_available()` fonksiyonu 3 farklı test dosyasında tekrarlanmıştı;
buraya taşındı. Ayrıca bir bug düzeltildi: `httpx.get()` varsayılan olarak
HTTP hata kodlarını (4xx/5xx) veya beklenmeyen yönlendirmeleri (3xx →
login sayfası gibi) exception olarak görmüyordu, bu da llama-server
gerçekte erişilemez durumdayken (örn. bir ağ/proxy login sayfasına
yönlendirme) testlerin "sunucu var" sanıp çalışmaya başlamasına ve
ortasında patlamasına yol açıyordu. Şimdi `response.status_code == 200`
kontrolü ekli.
"""

from __future__ import annotations

import httpx

from agent.llm_client import DEFAULT_BASE_URL


def server_available(base_url: str = DEFAULT_BASE_URL) -> bool:
    """llama-server'ın gerçekten yanıt verip vermediğini kontrol eder.

    Sadece bağlantının kurulabildiğini değil, `/models` endpoint'inin
    HTTP 200 döndürdüğünü de doğrular (redirect/hata durumlarını
    "sunucu yok" olarak sayar - testlerin ortasında beklenmeyen bir
    hatayla patlamasını önler).
    """
    try:
        response = httpx.get(f"{base_url}/models", timeout=2.0, follow_redirects=False)
    except httpx.HTTPError:
        return False
    return response.status_code == 200
