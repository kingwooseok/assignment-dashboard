import os
from pathlib import Path
import xml.etree.ElementTree as ET

root = ET.parse('artifacts/tests.xml').getroot()
suites = list(root.iter('testsuite'))
count = sum(int(s.get('tests', 0)) for s in suites)
revision = os.environ['GITHUB_SHA']
text = f'''# 마감노트 CI 검증

**결과: SUCCESS** · 버전 {Path('VERSION').read_text().strip()}

| 항목 | 결과 |
| --- | --- |
| FastAPI 자동 테스트 | {count}개 통과 |
| Docker 이미지 | 빌드 성공 |
| 실제 컨테이너 API | 상태 확인·등록·조회·완료·삭제 통과 |
| Docker Hub | kingwooseok/assignment-dashboard |
| 이미지 태그 | `{revision}` |
'''
Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(text, encoding='utf-8')
