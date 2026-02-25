from connectors.loki import LokiConnector


def test_loki_normalizes_empty_and_empty_compatible_matchers():
    assert LokiConnector._normalize_query("{}") == '{service=~".+"}'
    assert LokiConnector._normalize_query("") == '{service=~".+"}'
    assert LokiConnector._normalize_query('{app=~".*"}') == '{app=~".+"}'
    assert LokiConnector._normalize_query('{service=~".+"}') == '{service=~".+"}'
