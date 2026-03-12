"""
Claude API İstemcisi
────────────────────────────────────────────────────────────────
Anthropic SDK üzerinden claude-3-5-sonnet ile iletişim kurar.
Retry + exponential backoff dahil.
"""

import base64
import time
from typing import Any, Optional

import anthropic

from app.config import settings
from app.utils.logger import logger

# Sabitler
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0   # saniye
MAX_TOKENS = 1024


class ClaudeClient:
    """
    Anthropic Claude API sarmalayıcısı.
    Tek sorumluluk: API çağrısı + hata yönetimi.
    İş mantığı ClassificationService'te.
    """

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = MAX_TOKENS,
        temperature: float = 0.1,   # Tutarlı çıktı için düşük tutuyoruz
    ) -> str:
        """
        Claude'a mesaj gönder, yanıt metnini döndür.
        Geçici hatalar için otomatik retry yapar.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                text = response.content[0].text
                logger.debug(
                    f"[ClaudeClient] Model: {settings.CLAUDE_MODEL} | "
                    f"Input tokens: {response.usage.input_tokens} | "
                    f"Output tokens: {response.usage.output_tokens}"
                )
                return text

            except anthropic.RateLimitError as exc:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"[ClaudeClient] Rate limit — {wait:.1f}s bekleniyor "
                    f"(deneme {attempt}/{MAX_RETRIES})"
                )
                time.sleep(wait)

            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500 and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        f"[ClaudeClient] Sunucu hatası {exc.status_code} — "
                        f"{wait:.1f}s bekleniyor"
                    )
                    time.sleep(wait)
                else:
                    raise

            except anthropic.APIConnectionError as exc:
                if attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        f"[ClaudeClient] Bağlantı hatası — {wait:.1f}s bekleniyor"
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"[ClaudeClient] {MAX_RETRIES} denemede yanıt alınamadı."
        )

    def complete_with_images(
        self,
        system_prompt: str,
        user_message: str,
        images: list[bytes],          # PNG/JPEG baytları listesi
        image_media_type: str = "image/png",
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """
        Claude Vision API'ye metin + görüntü(ler) gönder.
        PDF sayfaları gibi görsel içerikli belgeler için kullanılır.
        """
        # Çoklu içerik bloğu: görüntüler + metin
        content: list[dict] = []
        for img_bytes in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type,
                    "data": base64.standard_b64encode(img_bytes).decode("utf-8"),
                },
            })
        content.append({"type": "text", "text": user_message})

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": content}],
                )
                text = response.content[0].text
                logger.debug(
                    f"[ClaudeClient/Vision] Model: {settings.CLAUDE_MODEL} | "
                    f"Input tokens: {response.usage.input_tokens} | "
                    f"Output tokens: {response.usage.output_tokens}"
                )
                return text

            except anthropic.RateLimitError:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"[ClaudeClient/Vision] Rate limit — {wait:.1f}s bekleniyor "
                    f"(deneme {attempt}/{MAX_RETRIES})"
                )
                time.sleep(wait)

            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500 and attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        f"[ClaudeClient/Vision] Sunucu hatası {exc.status_code} — "
                        f"{wait:.1f}s bekleniyor"
                    )
                    time.sleep(wait)
                else:
                    raise

            except anthropic.APIConnectionError:
                if attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        f"[ClaudeClient/Vision] Bağlantı hatası — {wait:.1f}s bekleniyor"
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(
            f"[ClaudeClient/Vision] {MAX_RETRIES} denemede yanıt alınamadı."
        )


# Uygulama genelinde paylaşılan tek instance
claude_client = ClaudeClient()
