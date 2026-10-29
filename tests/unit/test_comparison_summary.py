import pytest
from backend.app.comparison_summary import comparison_verdict, explain_comparison


def comparison(signals, stale=False):
    return {'left': {'stale': stale, 'snapshot_id': 'a'},
            'right': {'stale': False, 'snapshot_id': 'b'},
            'pipeline_version_mismatch': False,
            'rows': [{'signal': signal, 'aspect': str(i)} for i, signal in enumerate(signals)]}


def test_unsupported_features_do_not_create_a_winner():
    value = comparison(['left', 'right', 'insufficient_evidence'])
    assert comparison_verdict(value)['winner'] is None
    assert comparison_verdict(value)['supported_features'] == 2
    value['pipeline_version_mismatch'] = True
    assert comparison_verdict(value)['blocked']


def test_stale_evidence_withholds_recommendation():
    assert comparison_verdict(comparison(['left'], stale=True))['winner'] is None
    with pytest.raises(ValueError):
        explain_comparison(comparison(['left'], stale=True), lambda *args: pytest.fail('Must not generate'))


def test_explanation_receives_only_shared_supported_evidence():
    def generate(system, payload, schema):
        assert payload['verdict']['winner'] == 'left'
        assert len(payload['features']) == 1
        return {'summary': 'Battery feedback favors the first product.', 'trade_off': 'Other features lack shared evidence.'}
    result = explain_comparison(comparison(['left', 'insufficient_evidence']), generate)
    assert result['snapshots'] == ['a', 'b']


def test_feature_takeaways_include_sparse_and_mismatched_evidence():
    from backend.app.comparison_summary import explain_features
    value = comparison(['insufficient_evidence'])
    value['rows'][0]['aspect_id'] = 'battery'
    value['pipeline_version_mismatch'] = True
    def generate(system, payload, schema):
        assert payload['pipeline_version_mismatch']
        return {'features': [{'aspect_id': 'battery', 'takeaway': 'The samples need matching analyses before a preference can be drawn.'}]}
    assert explain_features(value, generate)['features'][0]['aspect_id'] == 'battery'
    with pytest.raises(ValueError):
        explain_features(value, lambda *args: {'features': [{'aspect_id': 'camera', 'takeaway': 'Wrong feature.'}]})
