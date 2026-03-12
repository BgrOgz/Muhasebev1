"""
Loguru tabanlı uygulama logger'ı
Kullanım: from app.utils.logger import logger
"""

import sys
from loguru import logger
from app.config import settings

# Varsayılan handler'ı kaldır
logger.remove()

# Konsol çıktısı
logger.add(
    sys.stdout,
    level="DEBUG" if settings.DEBUG else "INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# Dosya çıktısı (rotasyonlu)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    level="INFO",
    rotation="00:00",       # Her gece sıfırla
    retention="30 days",    # 30 gün sakla
    compression="zip",
    encoding="utf-8",
)

__all__ = ["logger"]
