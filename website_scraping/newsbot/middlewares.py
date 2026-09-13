import logging
from typing import Optional
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from twisted.internet import defer, reactor

logger = logging.getLogger(__name__)

# NOTE: Stock Scrapy's built-in RetryMiddleware ignores the standard HTTP 'Retry-After'
# response header, retrying immediately without respecting the server's instructed
# rate-limiting backoff window. RetryAfterMiddleware fills this critical gap by parsing
# the integer delta-seconds from 'Retry-After', asynchronously scheduling the retry
# through Twisted's non-blocking reactor.callLater, and then delegating to self._retry.


class RetryAfterMiddleware(RetryMiddleware):
    """
    Downloader middleware that honors HTTP 'Retry-After' headers on 429 and 503 responses
    without blocking Twisted's asynchronous reactor.
    """

    def process_response(self, request, response, spider=None):
        # Respect Scrapy's standard dont_retry meta flag
        if request.meta.get("dont_retry", False):
            return response

        # Inspect if this is a rate-limiting or service-unavailable response with a Retry-After header
        if response.status in (429, 503):
            retry_after_header = response.headers.get(b"Retry-After") or response.headers.get("Retry-After")
            if retry_after_header:
                log = spider.logger if spider else logger
                try:
                    if isinstance(retry_after_header, bytes):
                        retry_after_str = retry_after_header.decode("utf-8", errors="ignore")
                    else:
                        retry_after_str = str(retry_after_header)

                    raw_seconds = int(retry_after_str.strip())
                    # Clamp delay between 1 and 300 seconds to prevent starvation or zero delays
                    delay = max(1, min(300, raw_seconds))

                    log.warning(
                        f"Received HTTP {response.status} for {request.url}. "
                        f"Honoring Retry-After backoff: {delay}s before retrying."
                    )

                    # Return an asynchronous Twisted Deferred that fires after the delay
                    # to keep the event loop non-blocking while waiting to retry.
                    d = defer.Deferred()
                    # pyrefly: ignore[bad-argument-type]
                    reactor.callLater(float(delay), d.callback, None)

                    def _retry_callback(_):
                        retry_req = self._retry(
                            request,
                            f"HTTP {response.status} (honored Retry-After: {delay}s)",
                        )
                        return retry_req if retry_req is not None else response

                    d.addCallback(_retry_callback)
                    return d

                except (ValueError, TypeError) as err:
                    log.debug(
                        f"Could not parse integer Retry-After header '{retry_after_header}': {err}"
                    )

        # Fall through to default Scrapy RetryMiddleware logic if no Retry-After is present
        import inspect
        sig = inspect.signature(super().process_response)
        if len(sig.parameters) >= 3:
            return super().process_response(request, response, spider)
        return super().process_response(request, response)
