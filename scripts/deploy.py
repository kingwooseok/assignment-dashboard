"""새 컨테이너 검증 → Nginx 연결 전환 → 30초 연속 확인 → 이전 컨테이너 종료."""
import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from monitor import probe, utc_now

PREFIX = 'assignment-dashboard'
LABEL = 'project=assignment-dashboard'
PROXY = PREFIX + '-proxy'
NETWORK = PREFIX + '-network'
VOLUME = PREFIX + '-data'
URL = 'http://127.0.0.1:8000'


def docker(*args, check=True):
    command = shutil.which('docker')
    if not command:
        for directory in (Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin',
                          Path('C:/Program Files/Docker/Docker/resources/bin')):
            if (directory / 'docker.exe').exists():
                command = str(directory / 'docker.exe')
                break
    if not command:
        raise RuntimeError('Docker 실행 파일을 찾을 수 없습니다.')
    result = subprocess.run([command, *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if check and result.returncode:
        raise RuntimeError(f"docker {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result


def inspect(name):
    result = docker('inspect', name, check=False)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def owned(name):
    value = inspect(name)
    if value and (value.get('Config', {}).get('Labels') or {}).get('project') != PREFIX:
        raise RuntimeError(f'{name} 이름을 다른 컨테이너가 사용하고 있습니다.')
    return value


def wait_ready(url, revision, timeout=90):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        row = probe(url)
        if row['ok'] and row['revision'] == revision:
            return row
        time.sleep(1)
    raise RuntimeError(f'새 버전 응답 확인 실패: {url}')


def nginx_config(container):
    return f'''# active: {container}
server {{
    listen 80;
    client_max_body_size 3m;
    location / {{
        proxy_pass http://{container}:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
        proxy_connect_timeout 3s;
        proxy_read_timeout 30s;
        add_header X-Deployment-Slot {container} always;
    }}
}}
'''


def put_config(text, output):
    path = output / 'active-nginx.conf'
    path.write_text(text, encoding='utf-8')
    docker('cp', str(path), PROXY + ':/etc/nginx/conf.d/default.conf')


def summarize(output, revision, old_revision, deployed, error, events):
    log = output / 'requests.jsonl'
    rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    before = [r for r in rows if r['phase'] == 'before']
    during = [r for r in rows if r['phase'] == 'during']
    after = [r for r in rows if r['phase'] == 'after']
    failed = [r for r in rows if not r['ok']]
    gaps = [b['started_monotonic'] - a['finished_monotonic'] for a, b in zip(rows, rows[1:])]
    intervals = [b['started_monotonic'] - a['started_monotonic'] for a, b in zip(rows, rows[1:])]
    max_gap = max(gaps, default=0)
    sequence_ok = [r['id'] for r in rows] == list(range(1, len(rows)+1))
    transitioned = bool(old_revision and old_revision != revision and
                        any(r['ok'] and r['revision'] == old_revision for r in before) and
                        any(r['ok'] and r['revision'] == revision for r in during))
    after_seconds = (after[-1]['finished_monotonic'] - after[0]['started_monotonic']) if after else 0
    stable_after = bool(after and all(r['ok'] and r['revision'] == revision for r in after))
    data_preserved = bool(before and after and before[-1].get('data_hash') == after[-1].get('data_hash'))
    verified = bool(deployed and not failed and sequence_ok and max_gap <= 2.5 and
                    transitioned and stable_after and after_seconds >= 30 and data_preserved)
    success = deployed and (verified if old_revision else stable_after and not failed)
    result = 'SUCCESS' if success else 'FAILED'
    mode = '무중단 재배포 검증' if old_revision else '최초 배포 검증'
    lines = [f'# 마감노트 {mode}', '', f'**결과: {result}** · 접속 주소: {URL}', '',
             f"실제 API: `{URL}/api/dashboard` · 총 **{len(rows)}회**, 성공 **{len(rows)-len(failed)}회**, 실패 **{len(failed)}회**", '',
             '| 단계 | 성공 / 전체 | 대표 요청 | 요청 시작 (UTC) | HTTP | 응답 버전 | 결과 |',
             '| --- | ---: | ---: | --- | ---: | --- | --- |']
    for label, group in [('배포 전', before), ('배포 중', during), ('배포 후', after)]:
        if group:
            representative = next((r for r in group if r['revision'] == revision), group[-1])
            lines.append(f"| {label} | {sum(r['ok'] for r in group)}/{len(group)} | #{representative['id']} | {representative['started_at']} | {representative['http']} | {representative['version']} / `{representative['revision'][:7]}` | {representative.get('result', representative['error'])} |")
        else:
            lines.append(f'| {label} | 0/0 | - | - | - | - | 측정 없음 |')
    lines += ['', f"- 관측 구간 (UTC): {rows[0]['started_at'] if rows else '-'} ~ {rows[-1]['finished_at'] if rows else '-'}",
              f'- 요청 번호 연속: {sequence_ok} · 요청 종료 후 간격 최대: **{max_gap:.3f}초** (설정 1초)',
              f'- 요청 시작 간격 평균 / 최대: **{statistics.mean(intervals) if intervals else 0:.3f} / {max(intervals, default=0):.3f}초**',
              f'- 배포 후 관측: **{after_seconds:.1f}초** · 과제 데이터 유지: **{data_preserved if old_revision else "최초 배포"}**']
    if old_revision:
        lines.append(f'- 응답 전환: `{old_revision[:7]}` → `{revision[:7]}` · 전환 관측: **{transitioned}**')
        lines.append('- 판정: ' + ('관측한 요청 전부 정상 응답, 버전 전환과 데이터 유지 확인.' if verified else '위 검증 항목 중 실패한 항목이 있습니다.'))
    if error:
        lines += ['', f'배포 오류: `{error.replace(chr(10), " ")[:900]}`']
    summary = '\n'.join(lines) + '\n'
    (output / 'summary.md').write_text(summary, encoding='utf-8')
    metadata = dict(result=result, mode=mode, url=URL, target_revision=revision,
                    previous_revision=old_revision, total=len(rows), failed=len(failed),
                    verified=verified, deployed=deployed, max_gap_seconds=max_gap,
                    after_seconds=after_seconds, data_preserved=data_preserved,
                    events=events, error=error)
    (output / 'result.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    if rows:
        keys = ['id','phase','started_at','finished_at','http','ok','version','revision','latency_ms','total','data_hash','error']
        with (output / 'requests.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
    print(summary, flush=True)
    return success


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.revision):
        parser.error('revision must be a full commit SHA')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'requests.jsonl').exists():
        parser.error('새 출력 폴더를 지정해 주세요. 기존 검증 기록은 유지합니다.')
    process = None
    monitor_out = None
    old_revision = ''
    old_config = ''
    old_container = ''
    candidate = ''
    changed_proxy = False
    deployed = False
    error = ''
    events = []

    def event(message):
        events.append({'time': utc_now(), 'message': message})
        print(f'{utc_now()} {message}', flush=True)

    def start_monitor(phase):
        nonlocal process, monitor_out
        (output / 'phase').write_text(phase, encoding='utf-8')
        monitor_out = (output / 'monitor-console.log').open('w', encoding='utf-8')
        process = subprocess.Popen([sys.executable, '-u', str(Path(__file__).with_name('monitor.py')),
                                    '--url', URL, '--output', str(output)], stdout=monitor_out,
                                   stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                   env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        end = time.monotonic() + 15
        while not (output / 'ready').exists():
            if process.poll() is not None or time.monotonic() > end:
                raise RuntimeError('연속 모니터 시작 실패')
            time.sleep(.2)
        if (output / 'ready').read_text() != 'ok':
            raise RuntimeError('배포 전 실제 API 요청 실패')

    try:
        if docker('info', '--format', '{{.OSType}}').stdout.strip() != 'linux':
            raise RuntimeError('Docker Linux 컨테이너 모드가 필요합니다.')
        proxy = owned(PROXY)
        if proxy:
            if not proxy['State']['Running']:
                raise RuntimeError('기존 프록시가 중지되어 있습니다.')
            old_config = docker('exec', PROXY, 'cat', '/etc/nginx/conf.d/default.conf').stdout
            match = re.search(r'^# active: (assignment-dashboard-(?:blue|green))$', old_config, re.M)
            if not match:
                raise RuntimeError('현재 서비스 컨테이너를 확인할 수 없습니다.')
            old_container = match[1]
            owned(old_container)
            before = probe(URL)
            if not before['ok']:
                raise RuntimeError('기존 FastAPI 응답 실패')
            old_revision = before['revision']
            if old_revision == args.revision:
                raise RuntimeError('이미 서비스 중인 커밋입니다. 새 커밋을 배포해 주세요.')
            start_monitor('before')
            time.sleep(3)
            (output / 'phase').write_text('during', encoding='utf-8')
        event('배포 시작: ' + args.revision)
        image = 'kingwooseok/assignment-dashboard:' + args.revision
        docker('pull', image)
        if not proxy:
            docker('pull', 'nginx:1.28-alpine')
        for kind, name in [('network', NETWORK), ('volume', VOLUME)]:
            info = docker(kind, 'inspect', name, check=False)
            if info.returncode:
                docker(kind, 'create', '--label', LABEL, name)
            elif (json.loads(info.stdout)[0].get('Labels') or {}).get('project') != PREFIX:
                raise RuntimeError(f'{name} 자원을 다른 프로젝트가 사용하고 있습니다.')
        candidate = PREFIX + ('-green' if old_container.endswith('-blue') else '-blue')
        if owned(candidate):
            docker('rm', '-f', candidate)
        docker('run', '-d', '--name', candidate, '--label', LABEL, '--restart', 'unless-stopped',
               '--network', NETWORK, '-p', '127.0.0.1::8000', '-v', VOLUME + ':/data', image)
        candidate_info = inspect(candidate)
        port = candidate_info['NetworkSettings']['Ports']['8000/tcp'][0]['HostPort']
        wait_ready('http://127.0.0.1:' + port, args.revision)
        event('새 컨테이너 목록·집계·버전 응답 정상: ' + candidate)
        if not proxy:
            docker('create', '--name', PROXY, '--label', LABEL, '--restart', 'unless-stopped',
                   '--network', NETWORK, '-p', '127.0.0.1:8000:80', 'nginx:1.28-alpine')
        put_config(nginx_config(candidate), output)
        if proxy:
            docker('exec', PROXY, 'nginx', '-t')
            changed_proxy = True
            docker('exec', PROXY, 'nginx', '-s', 'reload')
        else:
            docker('start', PROXY)
        wait_ready(URL, args.revision)
        event('고정 접속 주소에서 새 버전 응답 확인')
        if not process:
            start_monitor('after')
        else:
            # 연속 모니터에도 배포 중 새 응답이 기록되도록 한 뒤 after로 전환한다.
            end = time.monotonic() + 10
            while time.monotonic() < end:
                content = (output / 'requests.jsonl').read_text(encoding='utf-8')
                if any(json.loads(line).get('revision') == args.revision for line in content.splitlines()):
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('모니터에서 새 버전 전환을 관측하지 못했습니다.')
            (output / 'phase').write_text('after', encoding='utf-8')
        time.sleep(32)
        wait_ready(URL, args.revision, timeout=5)
        observed = [json.loads(line) for line in (output / 'requests.jsonl').read_text(encoding='utf-8').splitlines()]
        if any(not row['ok'] for row in observed):
            raise RuntimeError('배포 중 실패 응답이 기록되었습니다.')
        if old_container:
            docker('stop', '--time', '30', old_container)
            event('이전 컨테이너 정상 종료: ' + old_container)
            # 이전 컨테이너 종료 후에도 새 버전의 정상 응답을 기록한다.
            time.sleep(3)
            wait_ready(URL, args.revision, timeout=5)
        deployed = True
        event('배포 완료')
    except Exception as exception:
        error = str(exception)
        event('배포 실패: ' + error)
        if changed_proxy and old_config:
            try:
                if not inspect(old_container)['State']['Running']:
                    docker('start', old_container)
                put_config(old_config, output)
                docker('exec', PROXY, 'nginx', '-t')
                docker('exec', PROXY, 'nginx', '-s', 'reload')
                wait_ready(URL, old_revision)
                event('이전 버전으로 복구 완료')
            except Exception as rollback_error:
                error += '\n복구 오류: ' + str(rollback_error)
    finally:
        if process:
            (output / 'stop').write_text('stop', encoding='utf-8')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
                error += '\n모니터 종료 시간 초과'
        if monitor_out:
            monitor_out.close()
        for name in [PROXY, candidate, old_container]:
            if name:
                result = docker('logs', '--tail', '250', name, check=False)
                (output / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        success = summarize(output, args.revision, old_revision, deployed, error, events)
    return 0 if success and not error else 1


if __name__ == '__main__':
    sys.exit(main())
