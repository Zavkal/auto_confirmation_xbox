import imaplib
import email
import logging
import re
import time
from email import policy

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.yandex.com"
IMAP_RETRY_DELAY_SEC = 2
IMAP_MAX_ATTEMPTS = 5


class GetLastMailService:

    def __init__(self,):
        self._last_code: str | None = None

    def prime(self, from_email: dict) -> None:
        """Запоминает код из последнего письма, чтобы не выдать его как новый."""
        text = self._read_latest_mail_with_retry(from_email)
        code = self.extract_code(text) if text else None
        self._last_code = code
        if code:
            logger.info("IMAP: зафиксирован текущий код в ящике (не используем его как новый)")
        else:
            logger.info("IMAP: в ящике нет кода Microsoft — ждём новое письмо")

    def run(self, from_email: dict) -> str | None:
        """Одна проверка inbox: новый код или None, если письма ещё нет."""
        text = self._read_latest_mail_with_retry(from_email)
        code = self.extract_code(text) if text else None
        if not code or code == self._last_code:
            return None
        self._last_code = code
        return code

    def _read_latest_mail_with_retry(self, from_email: dict) -> str | None:
        for attempt in range(1, IMAP_MAX_ATTEMPTS + 1):
            try:
                return self._read_latest_mail(from_email)
            except (imaplib.IMAP4.error, OSError, TimeoutError) as exc:
                logger.warning(
                    "IMAP connect failed (%s/%s): %s",
                    attempt, IMAP_MAX_ATTEMPTS, exc,
                )
                if attempt == IMAP_MAX_ATTEMPTS:
                    return None
                time.sleep(IMAP_RETRY_DELAY_SEC)
        return None

    def _read_latest_mail(self, from_email: dict) -> str | None:
        with imaplib.IMAP4_SSL(IMAP_HOST) as server:
            server.login(from_email['email'], from_email['password'])
            server.select("INBOX")

            status, data = server.search(
                None, "FROM",
                "account-security-noreply@accountprotection.microsoft.com"
            )
            if status != 'OK' or not data[0]:
                return None

            num = data[0].split()[-1]
            _, data = server.fetch(num, '(RFC822)')
            email_message = email.message_from_bytes(data[0][1], policy=policy.default)

            text = None
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    text = part.get_content()
                    break
            if text is None:
                for part in email_message.walk():
                    if part.get_content_type() == 'text/html':
                        text = part.get_content()
                        break
            return text


    def extract_code(self, text: str) -> str | None:
        patterns = [
            r'(?:разовый код|одноразовый код)[:\s]*([0-9]{6})',
            r'(?:one-time code|verification code|code)[:\s]*([0-9]{6})',
            r'\b([0-9]{6})\b',
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None