"""HTTP job providers. Failures never include credential-bearing URLs in logs."""

from datetime import datetime, timezone
import re

import requests


TIMEOUT = 5


def _date(value):
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return False


class JobBoardConnector:
    source = ""

    def __init__(self, config=None):
        self.config = config

    def _parameter(self, name, default=""):
        return self.config.get_param(name, default) if self.config is not None else default

    def _request(self, method, url, **kwargs):
        try:
            response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            return None

    def _normalize_rows(self, rows, query="", location="", filter_feed=False):
        results = []
        if not isinstance(rows, list):
            return results
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                posting = self.normalize(row)
            except (TypeError, ValueError, AttributeError):
                continue
            if not posting["external_id"] or not posting["title"] or not posting["url"]:
                continue
            if filter_feed:
                text = " ".join(str(row.get(key) or "") for key in (
                    "title", "position", "description", "tags",
                )).casefold()
                keywords = re.findall(r"[\w+#]+", query.casefold())
                if keywords and not any(word in text for word in keywords):
                    continue
                place = posting["location"].casefold()
                if location and location.casefold() not in place and not row.get("remote") and self.source != "remoteok":
                    continue
            results.append(posting)
        return results

    def _posting(self, external_id, title, company, description, url, location, date):
        return dict(source=self.source, external_id=str(external_id) if external_id else "",
                    title=title or "", company=company or "", description=description or "",
                    url=url or "", location=location or "", posted_date=_date(date))


class AdzunaConnector(JobBoardConnector):
    source = "adzuna"

    def fetch(self, query, location):
        app_id = self._parameter("adzuna_app_id")
        app_key = self._parameter("adzuna_app_key")
        if not app_id or not app_key:
            return []
        country = self._parameter("adzuna_country", "gb")
        if country not in {"at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "mx", "nl", "nz", "pl", "sg", "us", "za"}:
            country = "gb"
        data = self._request("GET", f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                             params=dict(app_id=app_id, app_key=app_key, what=query,
                                         where=location, results_per_page=50))
        return self._normalize_rows(data.get("results") if isinstance(data, dict) else [])

    def normalize(self, row):
        return self._posting(row.get("id"), row.get("title"),
                             (row.get("company") or {}).get("display_name"), row.get("description"),
                             row.get("redirect_url"), (row.get("location") or {}).get("display_name"),
                             row.get("created"))


class JoobleConnector(JobBoardConnector):
    source = "jooble"

    def fetch(self, query, location):
        key = self._parameter("jooble_api_key")
        if not key:
            return []
        data = self._request("POST", f"https://jooble.org/api/{key}",
                             json=dict(keywords=query, location=location))
        return self._normalize_rows(data.get("jobs") if isinstance(data, dict) else [])

    def normalize(self, row):
        return self._posting(row.get("id"), row.get("title"), row.get("company"),
                             row.get("snippet"), row.get("link"), row.get("location"), row.get("updated"))


class ArbeitnowConnector(JobBoardConnector):
    source = "arbeitnow"

    def fetch(self, query, location):
        data = self._request("GET", "https://www.arbeitnow.com/api/job-board-api")
        return self._normalize_rows(data.get("data") if isinstance(data, dict) else [],
                                    query, location, filter_feed=True)

    def normalize(self, row):
        return self._posting(row.get("slug"), row.get("title"), row.get("company_name"),
                             row.get("description"), row.get("url"), row.get("location"), row.get("created_at"))


class RemoteOKConnector(JobBoardConnector):
    source = "remoteok"

    def fetch(self, query, location):
        data = self._request("GET", "https://remoteok.com/api",
                             headers={"User-Agent": "JobFinder/1.0"})
        return self._normalize_rows(data, query, location, filter_feed=True)

    def normalize(self, row):
        return self._posting(row.get("id"), row.get("position"), row.get("company"),
                             row.get("description"), row.get("url"), row.get("location") or "Remote",
                             row.get("date") or row.get("epoch"))


CONNECTORS = (AdzunaConnector, JoobleConnector, ArbeitnowConnector, RemoteOKConnector)
