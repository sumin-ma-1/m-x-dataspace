"""Test bootstrap for local package imports.

`catena-x-sw-sample`를 독립 패키지로 아직 설치하지 않았기 때문에
테스트 실행 시 app 모듈 경로를 명시적으로 추가합니다.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
