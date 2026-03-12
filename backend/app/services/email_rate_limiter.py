"""
Email Rate Limiter
────────────────────────────────────
Tedarikçi başına günlük maksimum mail sayısını sınırlar.
Redis yoksa in-memory dict kullanır (geliştirme ortamı için yeterli).
"""

from collections import defaultdict
from datetime import date
from typing import Dict, Tuple

from app.utils.logger import logger

# Günlük limit
DAILY_LIMIT = 100


class InMemoryRateLimiter:
    """
    Basit in-memory rate limiter.
    Üretim ortamı için Redis tabanlı versiyona geçilebilir.
    """

    def __init__(self):
        # {(email, date): count}
        self._counts: Dict[Tuple[str, date], int] = defaultdict(int)

    def is_allowed(self, supplier_email: str) -> bool:
        """
        Supplier bu bugün limit içinde mi?
        True → işleme devam et
        False → limitı aştı, atla
        """
        key = (supplier_email.lower(), date.today())
        current = self._counts[key]

        if current >= DAILY_LIMIT:
            logger.warning(
                f"Rate limit aşıldı: {supplier_email} "
                f"(bugün {current} mail işlendi, limit: {DAILY_LIMIT})"
            )
            return False

        self._counts[key] += 1
        return True

    def get_count(self, supplier_email: str) -> int:
        """Tedarikçinin bugünkü mail sayısını döndür"""
        key = (supplier_email.lower(), date.today())
        return self._counts[key]

    def reset(self, supplier_email: str) -> None:
        """Manuel sıfırla (test için)"""
        key = (supplier_email.lower(), date.today())
        self._counts[key] = 0


# Uygulama genelinde paylaşılan tek instance
rate_limiter = InMemoryRateLimiter()
