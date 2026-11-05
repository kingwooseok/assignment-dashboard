"""실행한 Docker 이미지에서 저장·조회·재시작용 데이터 읽기를 점검한다."""
import argparse
import json
import time
from urllib.request import Request, urlopen


def request(base, path, data=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = Request(base + path, data=body, method=method,
                  headers={"Content-Type": "application/json", "Origin": base})
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    for attempt in range(60):
        try:
            health = request(args.url, '/api/health')
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(1)
    assert health['revision'] == args.revision
    item = request(args.url, '/api/assignments', {
        'subject': 'CI 검증', 'title': '컨테이너 저장 확인', 'due_at': '2026-12-31'})
    try:
        state = request(args.url, '/api/dashboard')
        assert state['release']['revision'] == args.revision
        assert any(row['id'] == item['id'] for row in state['assignments'])
        request(args.url, f"/api/assignments/{item['id']}/completion", {'completed': True}, 'PATCH')
        assert any(row['id'] == item['id'] for row in request(args.url, '/api/dashboard?status=completed')['assignments'])
    finally:
        request(args.url, f"/api/assignments/{item['id']}", method='DELETE')
    print('PASS: health, revision, SQLite write/read, completion, deletion')


if __name__ == '__main__':
    main()
