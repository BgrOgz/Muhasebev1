"""
E-posta doğrulama yardımcıları
Header injection saldırılarını önlemek için SMTP kullanımı öncesinde e-postalar doğrulanır.
"""

import re
from typing import Optional


def validate_email_address(email: str) -> str:
    """
    E-posta adresini doğrula ve normalleştir.

    Header injection saldırılarını önlemek için:
    - Yeni satır (\n, \r), null byte (\0), tab (\t) reddedilir
    - Çift @ reddedilir
    - Boşluklar kesilir
    - Küçük harfe normalleştirilir

    Args:
        email: Doğrulanacak e-posta adresi

    Returns:
        Normalleştirilmiş e-posta adresi

    Raises:
        ValueError: E-posta formatı geçersizse
    """
    if not email or not isinstance(email, str):
        raise ValueError("E-posta adresi geçerli bir string olmalıdır.")

    # Boşlukları kır
    email = email.strip()

    # Header injection karakterlerini kontrol et
    dangerous_chars = ['\n', '\r', '\0', '\t']
    for char in dangerous_chars:
        if char in email:
            raise ValueError(f"E-posta adresinde geçersiz karakter: {repr(char)}")

    # Temel format kontrolü
    if email.count('@') != 1:
        raise ValueError("E-posta adresinde tam olarak bir '@' simgesi olmalıdır.")

    local, domain = email.rsplit('@', 1)

    # Boş parçalar
    if not local or not domain:
        raise ValueError("E-posta adresi geçersiz formatda: yerel bölüm veya alan adı boş.")

    # Alan adında en az bir nokta ve geçerli karakterler
    if '.' not in domain:
        raise ValueError("Alan adında en az bir nokta (.) olmalıdır.")

    # Temel regex doğrulaması (RFC 5321 basitleştirilmiş)
    # İleri sınırlandırmalar SMTP seviyesinde yapılır
    if not re.match(r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+$', local):
        raise ValueError("E-posta yerel bölümü geçersiz karakterler içeriyor.")

    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', domain):
        raise ValueError("E-posta alan adı geçersiz formatda.")

    # Normalleştir
    normalized = email.lower()

    return normalized


def validate_email_list(emails: list[str]) -> list[str]:
    """
    E-posta adresleri listesini doğrula.

    Args:
        emails: Doğrulanacak e-posta adresleri

    Returns:
        Normalleştirilmiş e-posta adresleri listesi

    Raises:
        ValueError: Herhangi bir e-posta adresinde hata varsa
    """
    if not isinstance(emails, list):
        raise ValueError("E-postalar bir liste olmalıdır.")

    if not emails:
        raise ValueError("E-posta listesi boş olamaz.")

    validated = []
    for email in emails:
        validated.append(validate_email_address(email))

    return validated
