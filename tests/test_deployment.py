"""실패·관측 공백·버전 미전환을 무중단 성공으로 잘못 판정하지 않는지 검증한다."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deploy import summarize


def records():
    rows = []
    for i in range(38):
        rows.append(dict(id=i+1, phase='before' if i<3 else 'during' if i<6 else 'after',
                         started_monotonic=i*1.01, finished_monotonic=i*1.01+.01,
                         started_at=f'2026-11-05T06:00:{i:02d}+00:00', finished_at='end',
                         http=200, ok=True, revision='a'*40 if i<5 else 'b'*40,
                         version='1.0.0' if i<5 else '1.1.0', latency_ms=10,
                         total=6, data_hash='same-data', result='정상', error=''))
    return rows


@pytest.mark.parametrize('fault', ['none','failed-request','no-transition','gap','missing-id','data-change','short-after'])
def test_redeployment_verdict(tmp_path, fault):
    rows = records()
    if fault == 'failed-request':
        rows[4].update(ok=False, http=503, error='unavailable')
    elif fault == 'no-transition':
        for row in rows:
            row['revision'] = 'a'*40
    elif fault == 'gap':
        for row in rows[10:]:
            row['started_monotonic'] += 5
            row['finished_monotonic'] += 5
    elif fault == 'missing-id':
        rows[4]['id'] = 900
    elif fault == 'data-change':
        rows[-1]['data_hash'] = 'lost-data'
    elif fault == 'short-after':
        rows = rows[:15]
    (tmp_path/'requests.jsonl').write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
    success = summarize(tmp_path, 'b'*40, 'a'*40, True, '', [])
    assert success == (fault == 'none')
    result = json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    assert result['verified'] == (fault == 'none')
