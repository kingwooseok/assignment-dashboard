"""배포와 별도 프로세스에서 실제 과제 목록 API 응답을 기록한다."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def probe(url):
    started = time.perf_counter()
    row = {'started_at': utc_now(), 'started_monotonic': started,
           'http': None, 'ok': False, 'revision': '', 'version': '', 'error': ''}
    try:
        with urlopen(url + '/api/dashboard', timeout=3) as response:
            row['http'] = response.status
            data = json.load(response)
            release = data['release']
            assignments = data['assignments']
            assert isinstance(assignments, list)
            assert isinstance(data['summary']['total'], int)
            assert len(assignments) == data['summary']['total']
            assert response.headers['X-App-Revision'] == release['revision']
            assert release['revision']
            row.update(ok=response.status == 200, **release, total=len(assignments))
            stable = [{key: item[key] for key in ('id', 'subject', 'title', 'due_at', 'completed')}
                      for item in assignments]
            row['data_hash'] = hashlib.sha256(json.dumps(stable, sort_keys=True,
                                                        ensure_ascii=False).encode()).hexdigest()
            row['result'] = f"과제 {len(assignments)}개 · 목록·집계 정상"
    except Exception as error:
        row['error'] = str(error)
    row['finished_at'] = utc_now()
    row['finished_monotonic'] = time.perf_counter()
    row['latency_ms'] = round((row['finished_monotonic'] - started) * 1000, 2)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sequence = 0
    deadline = time.monotonic() + 1200
    with (args.output / 'requests.jsonl').open('w', encoding='utf-8', buffering=1) as log:
        while not (args.output / 'stop').exists() and time.monotonic() < deadline:
            sequence += 1
            # 단계는 요청 시작 시점 기준이다. 응답이 끝나면 1초 뒤 다음 요청을 보낸다.
            phase = (args.output / 'phase').read_text(encoding='utf-8').strip()
            row = {'id': sequence, 'phase': phase, **probe(args.url)}
            line = json.dumps(row, ensure_ascii=False)
            log.write(line + '\n')
            print(line, flush=True)
            if sequence == 1:
                (args.output / 'ready').write_text('ok' if row['ok'] else 'failed', encoding='utf-8')
            time.sleep(1)


if __name__ == '__main__':
    main()
