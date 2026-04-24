# syntax=docker/dockerfile:1
# Python 앱 샘플 이미지.
# 빌드 컨텍스트는 저장소 루트(.) 를 사용합니다.
#   docker build -f catena-x-sw-sample/Dockerfile .
#
# 테스트 단계는 공식 Python 이미지 권장 패턴을 따릅니다.
# https://hub.docker.com/_/python

FROM python:3.12-slim AS test
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY catena-x-sw-sample/ /app/catena-x-sw-sample/
RUN python -m pytest /app/catena-x-sw-sample/tests -q

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY catena-x-sw-sample/ /app/catena-x-sw-sample/
WORKDIR /app/catena-x-sw-sample
# 샘플 컨테이너: 실제 서비스 진입점으로 교체하세요 (FastAPI/uvicorn 등).
CMD ["python", "-c", "print('catena-x-sw-sample: OK'); __import__('time').sleep(999999)"]
