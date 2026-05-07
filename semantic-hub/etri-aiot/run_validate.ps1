param(
  [string]$CsvPath = "$(Resolve-Path ".\data\etri_aiot\smart_factory_data.csv")",
  [string]$ShapesPath = "$(Resolve-Path ".\semantic-hub\shapes\merged\etri-aiot.v1.ttl")",
  [int]$MaxRows = 20000
)

$ErrorActionPreference = "Stop"

function Ensure-Pyshacl {
  # In some PowerShell setups, a non-zero native exit code becomes a terminating error
  # under ErrorActionPreference=Stop. Use try/catch for a robust dependency check.
  try {
    python -c "import pyshacl" *> $null
  } catch {
    python -m pip install --upgrade pyshacl rdflib
  }
}

Ensure-Pyshacl

python .\scripts\etri_aiot_csv_to_rdf_and_validate.py `
  --csv "$CsvPath" `
  --shapes "$ShapesPath" `
  --max-rows $MaxRows

