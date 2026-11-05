"""Pure scorer regressions, runnable without Odoo or network."""

import importlib.util
from pathlib import Path
import unittest
from datetime import date

SPEC = importlib.util.spec_from_file_location("offer_scoring", Path(__file__).parents[1] / "models/offer_scoring.py")
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)

ELIGIBLE = (
    "Applicants are not required to hold NV1 clearance",
    "NV1 clearance is not a requirement",
    "Previous experience on NV1 projects is desirable",
    "Australian citizens, permanent residents or valid visa holders",
    "We welcome temporary visa holders and permanent residents",
    "No security clearance required", "performance baseline", "Baseline CSS skills", "NV1 projects",
    "Australian citizenship is preferred", "Permanent residency is not required",
)
REQUIRED = (
    "Must hold NV1 clearance", "Australian citizens only", "must be eligible for Baseline clearance",
    "must be an Australian citizen", "Australian citizenship required", "PR required",
    "must be a permanent resident", "must obtain security clearance", "NV2 clearance required",
    "NV1 clearance is not a requirement but Australian citizenship is required",
    "No experience required with mandatory NV1 clearance",
    "Australian citizenship is optional but must hold NV1 clearance",
    "No security clearance required, Australian citizenship is required",
)


class TestOfferScoring(unittest.TestCase):
    def test_eligibility(self):
        for text in ELIGIBLE:
            with self.subTest(text=text):
                self.assertEqual(SCORER.eligibility_reason(text), "")
        for text in REQUIRED:
            with self.subTest(text=text):
                self.assertTrue(SCORER.eligibility_reason(text))

    def test_components_and_seniority(self):
        score, parts, reason = SCORER.score_offer("Junior Frontend React", "visa sponsorship", ["Frontend"],
                                                {"React": 20}, "Perth")
        self.assertEqual(score, sum(parts.values()))
        self.assertEqual(score, 82)
        self.assertFalse(reason)
        for word in ("senior", "lead", "principal", "head", "manager", "architect"):
            self.assertEqual(SCORER.score_offer(word + " developer", "", [], {}, "")[0], 0)
            self.assertTrue(SCORER.score_offer(word + " developer", "", [], {}, "")[2])

    def test_union_years(self):
        intervals = [(date(2020, 1, 1), date(2021, 1, 1)), (date(2020, 6, 1), date(2021, 1, 1)),
                     (date(2023, 1, 1), date(2024, 1, 1))]
        self.assertAlmostEqual(SCORER.usage_years(intervals), 2, places=1)


class TestAdzunaTransport(unittest.TestCase):
    def test_documented_parameters_and_shared_budget(self):
        from unittest.mock import patch, MagicMock
        from urllib.parse import parse_qs, urlparse
        spec = importlib.util.spec_from_file_location("adzuna_client", Path(__file__).parents[1] / "models/adzuna_client.py")
        client_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client_module)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"results": []}'
        with patch.object(client_module, "urlopen", return_value=response) as transport:
            client = client_module.AdzunaClient("synthetic", "synthetic", 1)
            self.assertEqual(client.search("Frontend remote", "Perth"), [])
            request = transport.call_args.args[0]
            self.assertEqual(request.get_header("Accept"), "application/json")
            parsed = urlparse(request.full_url)
            self.assertEqual(parsed.path, "/v1/api/jobs/au/search/1")
            self.assertEqual(set(parse_qs(parsed.query)), {"app_id", "app_key", "what", "where", "results_per_page"})
            with self.assertRaises(client_module.ProviderError):
                client.search("again")
            self.assertEqual(transport.call_count, 1)

    def test_safe_errors_and_attempt_count(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        spec = importlib.util.spec_from_file_location("adzuna_client", Path(__file__).parents[1] / "models/adzuna_client.py")
        client_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client_module)
        with patch.object(client_module, "urlopen", side_effect=HTTPError("sensitive-query", 429, "secret", {}, None)):
            client = client_module.AdzunaClient("synthetic", "synthetic", 2)
            with self.assertRaisesRegex(client_module.ProviderError, "^Provider rate limit reached$"):
                client.search("Frontend")
            self.assertEqual(client.calls, 1)
