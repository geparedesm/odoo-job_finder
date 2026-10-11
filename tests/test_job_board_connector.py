"""Provider contracts tested with HTTP doubles, without optional dependencies."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('connectors_test', Path(__file__).resolve().parents[1] / 'models/job_board_connector.py')
boards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boards)


class NetworkError(Exception):
    pass


class TestConnectors(unittest.TestCase):
    def test_provider_fetch_and_field_mapping(self):
        cases = [
            (boards.AdzunaConnector, {'results': [dict(id='1', title='Python', company={'display_name': 'Acme'}, description='Python', redirect_url='https://job', location={'display_name': 'Berlin'}, created='2026-10-01T00:00:00Z')]}, 'GET'),
            (boards.JoobleConnector, {'jobs': [dict(id='1', title='Python', company='Acme', snippet='Python', link='https://job', location='Berlin', updated='2026-10-01')]}, 'POST'),
            (boards.ArbeitnowConnector, {'data': [dict(slug='1', title='Python', company_name='Acme', description='Python', url='https://job', location='Berlin', created_at=1790812800)]}, 'GET'),
            (boards.RemoteOKConnector, [dict(legal='metadata'), dict(id='1', position='Python', company='Acme', description='Python', url='https://job', location='Berlin', date='2026-10-01')], 'GET'),
        ]
        for provider, payload, method in cases:
            with self.subTest(provider=provider.source):
                response = Mock()
                response.json.return_value = payload
                request = Mock(return_value=response)
                with patch.dict(sys.modules, {'requests': SimpleNamespace(request=request, RequestException=NetworkError)}):
                    rows = provider(dict(adzuna_app_id='id', adzuna_app_key='key', jooble_api_key='key')).fetch('Python and the', 'Berlin')
                self.assertEqual(rows, [dict(source=provider.source, external_id='1', title='Python', company='Acme', description='Python', url='https://job', location='Berlin', posted_date='2026-10-01')])
                self.assertEqual(request.call_args.args[0], method)
                self.assertEqual(request.call_args.kwargs['timeout'], boards.TIMEOUT)
                response.raise_for_status.assert_called_once()
                if provider == boards.AdzunaConnector:
                    self.assertEqual(request.call_args.kwargs['params']['what'], 'python')
                if provider == boards.JoobleConnector:
                    self.assertEqual(request.call_args.kwargs['json']['keywords'], 'python')

    def test_credentials_gate_only_private_providers(self):
        for provider in (boards.AdzunaConnector, boards.JoobleConnector):
            with patch.object(provider, '_request') as request:
                self.assertEqual(provider({}).fetch('Python', ''), [])
                request.assert_not_called()
        config = Mock(get_param=Mock(side_effect=lambda name, default: default))
        with patch.object(boards.ArbeitnowConnector, '_request', return_value={}) as arbeit, patch.object(boards.RemoteOKConnector, '_request', return_value=[]) as remote:
            self.assertEqual(boards.fetch_jobs(config, 'Python', ''), [])
            arbeit.assert_called_once()
            remote.assert_called_once()

    def test_missing_requests_and_http_network_json_errors_are_nonfatal(self):
        provider = boards.RemoteOKConnector()
        with patch.dict(sys.modules, {'requests': None}), self.assertLogs(boards._logger, level='WARNING'):
            self.assertEqual(provider.fetch('Python', ''), [])
        for stage, error in [('request', NetworkError('secret-url')), ('raise_for_status', NetworkError('secret-url')), ('json', ValueError('secret-url'))]:
            response = Mock()
            request = Mock(return_value=response)
            (request if stage == 'request' else getattr(response, stage)).side_effect = error
            with patch.dict(sys.modules, {'requests': SimpleNamespace(request=request, RequestException=NetworkError)}), self.assertLogs(boards._logger, level='WARNING') as logs:
                self.assertEqual(provider.fetch('Python', ''), [])
            self.assertNotIn('secret-url', str(logs.output))

    def test_feed_filter_ignores_stopwords_and_matches_whole_terms(self):
        provider = boards.ArbeitnowConnector()
        rows = [dict(slug=str(i), title=title, url='https://job', location='Berlin') for i, title in enumerate(['Sales and the team', 'Python engineer', 'Pythonic sales'], 1)]
        results = provider._normalize_rows(rows, 'Python and the de con', 'Berlin', True)
        self.assertEqual([row['external_id'] for row in results], ['2'])
        self.assertEqual(provider._normalize_rows(rows, 'Python', 'Madrid', True), [])
        self.assertEqual(provider._normalize_rows([None, {}, {'slug': 'bad'}]), [])
        self.assertEqual(boards._date('invalid'), False)
        self.assertLessEqual(len(boards.search_query(' '.join('term'+str(i) for i in range(100))).split()), 12)
        self.assertEqual(boards.search_query('C++ and C# con Python Python'), 'c++ c# python')
