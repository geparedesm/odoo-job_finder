"""Bounded Adzuna HTTPS transport. Errors deliberately omit request URLs and credentials."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(Exception):
    """Safe provider failure."""


class AdzunaClient:
    """One shared budget for every attempted request in a run."""

    def __init__(self, app_id, app_key, limit):
        self.app_id = app_id
        self.app_key = app_key
        self.limit = limit
        self.calls = 0

    def search(self, keywords, city="", page=1):
        """Only parameters verified in developer.adzuna.com/docs/search are used."""
        if self.calls >= self.limit:
            raise ProviderError("Call budget reached")
        self.calls += 1
        params = dict(app_id=self.app_id, app_key=self.app_key, what=keywords, results_per_page=20)
        if city:
            params["where"] = city
        request = Request("https://api.adzuna.com/v1/api/jobs/au/search/" + str(page) + "?" + urlencode(params),
                          headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=20) as response:  # nosec B310: fixed HTTPS provider host
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ProviderError("Provider response too large")
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ProviderError("Invalid provider response")
            return payload["results"]
        except HTTPError as error:
            raise ProviderError("Provider rate limit reached" if error.code == 429 else "Provider HTTP failure") from None
        except (URLError, TimeoutError, ValueError, OSError):
            raise ProviderError("Provider unavailable or invalid response") from None
