"""Base API client with shared retry and rate-limiting logic."""

import asyncio
from typing import Any

import httpx


class BaseAPIClient:
    """Base class for HTTP API clients with retry and rate-limiting.

    Subclasses should set class attributes:
        BASE_URL: Base URL for the API
        MAX_CONCURRENT_REQUESTS: Semaphore limit for concurrent requests
        RETRY_STATUS_CODES: Set of status codes to retry on (default: 5xx)

    Optional class attributes:
        MAX_RETRIES: Max retry attempts (default: 3)
        RETRY_BACKOFF: Tuple of backoff delays in seconds (default: 1, 2, 4)
        TIMEOUT: Request timeout in seconds (default: 30)
        DEFAULT_HEADERS: Additional headers to include in requests
    """

    BASE_URL: str = ""
    MAX_CONCURRENT_REQUESTS: int = 5
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: tuple[float, ...] = (1.0, 2.0, 4.0)
    RETRY_STATUS_CODES: set[int] = set()  # 5xx always retried; add 429 etc here
    TIMEOUT: float = 30.0
    DEFAULT_HEADERS: dict[str, str] = {}

    # Shared User-Agent for all clients
    USER_AGENT = "WxDXX/0.8.3 (https://github.com/c-ancell/wxdxx, wxdxxapp@gmail.com)"

    def __init__(self) -> None:
        headers = {"User-Agent": self.USER_AGENT}
        headers.update(self.DEFAULT_HEADERS)

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.TIMEOUT,
            headers=headers,
        )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a rate-limited GET request with retry on transient failures.

        Retries on:
            - Transport errors (connection issues)
            - Timeout exceptions
            - 5xx server errors
            - Status codes in RETRY_STATUS_CODES (e.g., 429 rate limit)

        Args:
            url: URL path (relative to BASE_URL) or absolute URL
            **kwargs: Additional arguments passed to httpx.get()

        Returns:
            httpx.Response object

        Raises:
            httpx.TransportError: On network failure after all retries
            httpx.TimeoutException: On timeout after all retries
        """
        async with self._semaphore:
            last_error: Exception | None = None

            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    response = await self._client.get(url, **kwargs)

                    # Retry on server errors (5xx) or configured status codes
                    should_retry = (
                        response.status_code >= 500
                        or response.status_code in self.RETRY_STATUS_CODES
                    )
                    if should_retry and attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_BACKOFF[attempt])
                        continue

                    return response

                except (httpx.TransportError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_BACKOFF[attempt])
                    else:
                        raise

            # Should not reach here, but satisfy type checker
            if last_error:
                raise last_error
            raise RuntimeError("Unexpected retry loop exit")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "BaseAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
