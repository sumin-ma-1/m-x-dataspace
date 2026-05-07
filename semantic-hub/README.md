# Semantic Hub (RDF/OWL/SHACL)

시맨틱 허브 기반 데이터 정합성 검증 자산을 모아 둔 폴더입니다.

핵심 구조:

- `shapes/core.ttl`  
  공통 제약(필수값, cardinality, datatype)
- `profiles/etri-aiot/v1.ttl`  
  ETRI AIoT 데이터셋 전용 프로파일 제약(범위, label 집합)
- `shapes/merged/etri-aiot.v1.ttl`  
  실행 편의를 위한 병합본(core + profile)
- `etri-aiot/run_validate.ps1`  
  CSV → RDF 변환 + SHACL 검증 실행

빠른 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\semantic-hub\etri-aiot\run_validate.ps1
```

데이터 출처:

- ETRI, 산업용 AIoT(가공기계) 이상진단 데이터, 2022  
  DOI: `https://doi.org/10.22648/ETRI.2022.D.94`

