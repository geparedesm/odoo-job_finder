"""Pure scorer regressions, runnable without Odoo or network."""

import importlib.util
from pathlib import Path
import unittest
from datetime import date

SPEC = importlib.util.spec_from_file_location("offer_scoring", Path(__file__).parents[1] / "models/offer_scoring.py")
SCORER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORER)

MUST_DISCARD = (
    ('Must be an Australian citizen', SCORER.CITIZENSHIP_REASON),
    ('Must be Australian citizens', SCORER.CITIZENSHIP_REASON),
    ('Must be an Australian citizen or permanent resident', SCORER.CITIZENSHIP_REASON),
    ('Must be an Australian permanent resident', SCORER.CITIZENSHIP_REASON),
    ('Must have Australian citizenship', SCORER.CITIZENSHIP_REASON),
    ('Must hold Australian citizenship', SCORER.CITIZENSHIP_REASON),
    ('Must have permanent residency', SCORER.CITIZENSHIP_REASON),
    ('Must hold Australian permanent residency', SCORER.CITIZENSHIP_REASON),
    ('Australian citizenship is required', SCORER.CITIZENSHIP_REASON),
    ('Australian citizenship or permanent residency mandatory', SCORER.CITIZENSHIP_REASON),
    ('Permanent residency essential', SCORER.CITIZENSHIP_REASON),
    ('Australian citizens only', SCORER.CITIZENSHIP_REASON),
    ('Only Australian citizens', SCORER.CITIZENSHIP_REASON),
    ('Must hold a current Baseline security clearance', "Security clearance required"),
    ('Must have an active security clearance', "Security clearance required"),
    ('NV1 clearance is required', "Security clearance required"),
    ('Security clearance mandatory', "Security clearance required"),
    ('Must be eligible to obtain an NV2 security clearance', "Security clearance required"),
    ('Must be able to obtain a Negative Vetting 1 clearance', "Security clearance required"),
    ('Negative Vetting 2 security clearance essential', "Security clearance required"),
    ('PV clearance required', "Security clearance required"),
    ('Positive Vetting clearance mandatory', "Security clearance required"),
    ('Must hold NV1 clearance', "Security clearance required"),
    ('Must be eligible for clearance', "Security clearance required"),
    ('Must be able to obtain clearance', "Security clearance required"),
)
MUST_NOT_DISCARD = (
    'You must raise a PR for every change',
    'Must be comfortable with PR reviews',
    'No requirement to hold a security clearance',
    'Applicants are not required to hold NV1 clearance',
    'NV1 clearance is not a requirement',
    'Previous experience on NV1 projects is desirable',
    'Must be an Australian citizen, PR, or hold a valid working visa',
    'Australian citizenship or valid working visa required',
    'Must be an Australian citizen or have the right to work in Australia',
    'Baseline clearance is an advantage',
    'Australian citizens, permanent residents or valid visa holders',
    'Australian citizenship is preferred',
    'performance baseline',
    'Must be an Australian citizen or have full work rights',
    'Must be an Australian citizen or have valid working rights',
    'Security clearance required, not',
    'Security clearance required, no',
    'Security clearance required, without',
    "Security clearance required, don't",
    "Security clearance required, doesn't",
    "Security clearance required, isn't",
    "Security clearance required, aren't",
    'Security clearance required, never',
    'Security clearance required, desirable',
    'Security clearance required, preferred',
    'Security clearance required, advantage',
    'Security clearance required, advantageous',
    'Security clearance required, nice to have',
    'Security clearance required, bonus',
    'Security clearance required, highly regarded',
    'Security clearance required, optional',
    'Must hold NV1 clearance but no experience required',
    'Australian citizenship required (optional)',
    'Must be an Australian citizen or one two three four five visa',
    'xmust be an Australian citizen',
    'Australian citizenship requiredness',
)


class TestOfferScoring(unittest.TestCase):
    def test_eligibility(self):
        for text in MUST_NOT_DISCARD:
            with self.subTest(text=text):
                self.assertEqual(SCORER.eligibility_reason(text), "")
                score, _, reason = SCORER.score_offer("Junior Frontend", text, ["Frontend"], {}, "Perth")
                self.assertGreater(score, 0)
                self.assertFalse(reason)
        for text, expected in MUST_DISCARD:
            with self.subTest(text=text):
                self.assertEqual(SCORER.eligibility_reason(text), expected)
                score, _, reason = SCORER.score_offer("Junior Frontend", text, ["Frontend"], {}, "Perth")
                self.assertEqual((score, reason), (0, expected))
                self.assertEqual(SCORER.score_offer(text, "", [], {}, "")[2], expected)

    def test_sentence_boundaries_and_case(self):
        for separator in (".", ";", "!", "?", "\n", "\r"):
            text = "No experience required" + separator + "NV1 CLEARANCE REQUIRED"
            self.assertEqual(SCORER.eligibility_reason(text), "Security clearance required")
        self.assertEqual(SCORER.eligibility_reason("We don’t require experience, security clearance required"), "")
        self.assertEqual(SCORER.eligibility_reason(
            "Must be an Australian citizen or one two three four five six visa"), SCORER.CITIZENSHIP_REASON)
        self.assertEqual(SCORER.eligibility_reason(
            "Security clearance required or valid visa"), "Security clearance required")

    def test_eligibility_mention(self):
        for text in ("citizen", "citizens", "citizenship", "permanent resident",
                     "permanent residents", "permanent residency", "permanent residence",
                     "clearance", "Baseline", "NV1", "NV2", "Negative Vetting 1",
                     "Negative Vetting 2", "PV", "Positive Vetting"):
            with self.subTest(text=text):
                self.assertTrue(SCORER.eligibility_mention(text.upper()))
        for text in ("You must raise a PR for every change", "Must be comfortable with PR reviews",
                     "Junior Frontend", "citizenshipx", "NV12"):
            self.assertFalse(SCORER.eligibility_mention(text))

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
