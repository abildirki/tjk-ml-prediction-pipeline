import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_log, after_log
import structlog
from typing import Optional
import logging

logger = structlog.get_logger()

class TJKClient:
    def __init__(self, base_url: str = "https://www.tjk.org"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=30.0,
            follow_redirects=True
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code != 404),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.WARN),
    )
    async def get(self, url: str, params: Optional[dict] = None) -> str:
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.text
        except Exception as e:
            # logger.error("Request failed", url=url, error=str(e))
            raise

    async def close(self):
        await self.client.aclose()
