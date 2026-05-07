# ETRI AIoT (Machining) – RDF/SHACL MVP

This folder contains a minimal, standards-based semantic validation setup for the dataset:

> ETRI, 산업용 AIoT(가공기계) 이상진단 데이터, 2022, `https://doi.org/10.22648/ETRI.2022.D.94`

## What we validate (SHACL)

- Dataset rows (operation record) are represented as RDF resources.
- Each record must have required numeric fields and a `label`.
- Numeric fields must be `xsd:decimal` (or `xsd:double`) within a reasonable min/max range derived from sampling the CSV.

## Files

- `semantic-hub/shapes/core.ttl`: core constraints (required fields/cardinality/datatype), reusable across datasets.
- `semantic-hub/profiles/etri-aiot/v1.ttl`: dataset/profile-specific bounds and label set for ETRI AIoT.
- `semantic-hub/shapes/merged/etri-aiot.v1.ttl`: merged execution shape set (core + profile).
- `run_validate.ps1`: helper to run validation locally (requires Python + `pyshacl`).
- `scripts/etri_aiot_shacl_tevv.py`: TEVV helper that builds positive/negative test cases and reports
  confusion matrix + accuracy/precision/recall/F1 for non-conformance detection.

## Why split core/profile?

- SHACL defines constraints as independent node/property shapes that can be combined (Shapes Graph model).
- OWL 2 defines profiles/sub-languages to trade expressivity vs performance; the same design principle applies to
  validation policies: keep stable core semantics, separate domain/profile constraints.

References:
- W3C SHACL Recommendation: https://www.w3.org/TR/shacl
- W3C OWL 2 Overview: https://www.w3.org/TR/owl2-overview/

## Notes

- The CSV itself is large and should generally not be committed to git. Keep it under `data/` and add it to `.gitignore`.

## TEVV quick run

```powershell
python .\scripts\etri_aiot_shacl_tevv.py `
  --csv .\data\etri_aiot\smart_factory_data.csv `
  --shapes .\semantic-hub\shapes\merged\etri-aiot.v1.ttl `
  --base-rows 200
```

