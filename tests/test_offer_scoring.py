"""Pure scorer regressions, runnable without Odoo or network."""

import importlib.util
from pathlib import Path
import unittest
from datetime import date

SPEC = importlib.util.spec_from_file_location("offer_scoring", Path(__file__).parents[1] / "models/offer_scoring.py")
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)

ELIGIBLE = (
    "Applicants do not need to hold a Baseline clearance",
    "There is no requirement for NV1 clearance", "You do not need to be an Australian citizen",
    "Applicants will not need to hold NV1 clearance", "Applicant does not need to hold NV1 clearance",
    "You don't need to hold NV1 clearance", "Applicant doesn't need to hold NV1 clearance",
    "No need for NV1 clearance", "Must be an Australian citizen, permanent resident or hold a valid visa with full work rights",
    "Must be an Australian citizen or have a valid work visa",
    "Must be Australian citizen or PR, or hold a visa with full work rights",
    "No NV1 and NV2 clearance required", "No NV1, NV2 or Baseline clearance required",

    "Customs clearance", "stock clearance sale", "height clearance",
    "Must obtain customs clearance", "Height clearance is necessary",
    "Australian citizenship, permanent residency or full work rights required",
    "Australian citizenship or other full work rights required",
    "Australian citizenship or any full work rights required",
    "Applicants are not required to hold NV1 clearance", "NV1 clearance is not a requirement",
    "Previous experience on NV1 projects is desirable", "NV1 clearance requirement does not apply to this position",
    "NV1 clearance requirement has been waived", "Baseline clearance is an advantage but not required",
    "No security clearance needed", "No security clearance required",
    "Australian citizens, permanent residents or valid visa holders with full work rights are welcome to apply",
    "Must be an Australian citizen, permanent resident or have full work rights in Australia",
    "Must have full working rights in Australia", "Visa sponsorship available",
    "Australian citizens, permanent residents or valid visa holders",
    "We welcome temporary visa holders and permanent residents", "performance baseline", "Baseline CSS skills",
    "NV1 projects", "Australian citizenship is preferred", "Permanent residency is not required",
    "No permanent residency required", "No PR required", "Optional NV1 clearance requirement",
    "No negative vetting required", "No PV required", "No TSSC required",
    "Australian citizenship or permanent residency or full work rights required",
    "Clearance sale of office furniture", "clearance of tickets", "Role requires clearance of tickets",
    "Australian citizenship required, alternatively full work rights are accepted",
    "No NV1 clearance required", "No NV1 or NV2 clearance required",
)
REQUIRED = (
    "Must hold, or be able to obtain, an NV1 clearance",
    "Australian citizenship required (NV1 clearance preferred)",
    "React experience preferred with mandatory NV1 clearance",

    "NV1 clearance needed", "Australian citizenship is necessary", "Permanent residency is essential",
    "Australian citizenship required and full work rights",
    "AGSVA clearance required", "Eligible to obtain clearance",
    "Security clearance required or full work rights",
    "NV1 required", "Baseline required", "Software Engineer — Baseline required", "Must hold an NV1",
    "Must hold Baseline", "Must hold NV1", "NV2 is mandatory",
    "Successful applicant must hold or be able to obtain an NV1 security clearance",
    "must hold or be able to obtain an NV1 security clearance",
    "Must be able to obtain NV1 clearance", "must have the ability to obtain a Baseline clearance",
    "Must hold NV1 and NV2 clearance", "Must hold a NV1 or NV2 clearance", "must be eligible for clearance",
    "Baseline security clearance is essential", "Negative Vetting 1 clearance required",
    "Must be an Australian citizen or permanent resident with full working rights",
    "Australian citizenship required, applicants must also have full work rights",
    "Australian citizens only", "Must be an Australian citizen", "PR required", "Permanent residency is mandatory",
    "Must hold NV1 clearance", "must be eligible for Baseline clearance", "must be a permanent resident",
    "must obtain security clearance", "NV2 clearance required",
    "NV1 clearance is not a requirement but Australian citizenship is required",
    "No experience required with mandatory NV1 clearance",
    "Australian citizenship is optional but must hold NV1 clearance",
    "No security clearance required, Australian citizenship is required",
    "PV required", "Positive vetting is mandatory", "TSSC required", "Negative Vetting level 2 is required",
    "NV1 required. Must hold an NV1.", "Negative vetting required", "Must undergo negative vetting",
    "This role requires Baseline clearance", "Requires an NV1 security clearance",
    "Role requires Australian citizenship", "Applicants are required to hold NV2 clearance",
    "Requiring permanent residency", "Australian citizenship needed", "NV1 clearance is necessary",
    "React experience preferred and NV1 clearance required",
    "No security clearance required and Australian citizenship required",
    "Australian citizenship required, full work rights are also required",
    "Australian citizenship required as well as full work rights",
    "NV1 clearance preferred and NV2 clearance required",
    "Must obtain and maintain NV1 clearance", "NV1 and NV2 clearance are required",
)


class TestOfferScoring(unittest.TestCase):
    def test_eligibility(self):
        for text in ELIGIBLE:
            with self.subTest(text=text):
                self.assertEqual(SCORER.eligibility_reason(text), "")
                score, _, reason = SCORER.score_offer("Junior Frontend", text, ["Frontend"], {}, "Perth")
                self.assertGreater(score, 0)
                self.assertFalse(reason)
        for text in REQUIRED:
            with self.subTest(text=text):
                expected = SCORER.CITIZENSHIP_REASON if any(word in text.lower() for word in
                    ("citizen", "permanent resident", "pr required", "residency")) and "optional" not in text else "Security clearance required"
                self.assertEqual(SCORER.eligibility_reason(text), expected)
                score, _, reason = SCORER.score_offer("Junior Frontend", text, ["Frontend"], {}, "Perth")
                self.assertEqual((score, reason), (0, expected))
                self.assertEqual(SCORER.score_offer(text, "", [], {}, "")[2], expected)

    def test_components_and_seniority(self):
        score, parts, reason = SCORER.score_offer("Junior Frontend React", "visa sponsorship", ["Frontend"],
                                                {"React": 20}, "Perth")
        self.assertEqual(score, sum(parts.values()))
        self.assertEqual(score, 82)
        self.assertFalse(reason)
        for word in ("senior", "lead", "principal", "head", "manager", "architect"):
            self.assertEqual(SCORER.score_offer(word + " developer", "", [], {}, "")[0], 0)
            self.assertTrue(SCORER.score_offer(word + " developer", "", [], {}, "")[2])

    def test_configured_locations(self):
        cases = [("Melbourne, Victoria", ["Melbourne"], 10), ("Perth", ["Melbourne"], 0),
                 ("Darwin", ["Australia"], 10), ("Remote", ["remote"], 10),
                 ("Remote", ["Perth"], 0), ("North Perth", ["Perth"], 10),
                 ("Perthshire", ["Perth"], 0), ("  MELBOURNE, AU", [" Melbourne "], 10)]
        for location, target, expected in cases:
            with self.subTest(location=location, target=target):
                _, parts, _ = SCORER.score_offer("Junior Frontend", "", ["Frontend"], {}, location, target)
                self.assertEqual(parts["location"], expected)
        for targets, expected in ((["remote"], 10), (["Perth"], 0)):
            _, parts, _ = SCORER.score_offer("Junior Frontend", "Remote role", ["Frontend"], {}, "", targets)
            self.assertEqual(parts["location"], expected)
        self.assertEqual(SCORER.score_offer("Baseline required", "Citizenship is optional", [], {}, "")[0], 0)
        _, parts, _ = SCORER.score_offer("Junior Frontend", "Visa sponsorship available", ["Frontend"], {}, "Perth")
        self.assertEqual(parts["sponsorship"], 7)

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
