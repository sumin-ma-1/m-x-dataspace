import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type UploadTarget = 'provider-asset' | 'aas-shell';
type StepState = 'idle' | 'loading' | 'done' | 'error';

interface ValidateResult {
  valid: boolean;
  warnings: string[];
  errors: string[];
  extracted_columns: string[];
}

interface MappingResult {
  profile_id: string;
  input_columns: string[];
  mappings: {
    sourceColumn: string;
    canonicalField: string;
    targetPath: string;
    confidence: number;
    required: boolean;
    rationale: string;
  }[];
  coverage: {
    requiredTotal: number;
    requiredMapped: number;
    missingRequired: string[];
    isReadyForDraft: boolean;
  };
  aas_submodel_draft: Record<string, unknown>;
}

@Component({
  selector: 'app-asset-json-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './asset-json-upload.component.html',
})
export class AssetJsonUploadComponent {
  target: UploadTarget = 'provider-asset';
  selectedFileName = '';
  parsedJson: unknown = null;

  // Upload state
  uploadState: StepState = 'idle';
  uploadResult = '';
  uploadError = '';

  // Validate state
  validateState: StepState = 'idle';
  validateResult: ValidateResult | null = null;
  validateError = '';

  // Mapping agent state
  mappingState: StepState = 'idle';
  mappingResult: MappingResult | null = null;
  mappingError = '';
  showAasDraft = false;

  get aasDraftJson(): string {
    return this.mappingResult
      ? JSON.stringify(this.mappingResult.aas_submodel_draft, null, 2)
      : '';
  }

  onFileSelected(event: Event): void {
    this.validateState = 'idle';
    this.validateResult = null;
    this.validateError = '';
    this.mappingState = 'idle';
    this.mappingResult = null;
    this.mappingError = '';
    this.showAasDraft = false;
    this.uploadState = 'idle';
    this.uploadResult = '';
    this.uploadError = '';
    this.parsedJson = null;
    this.selectedFileName = '';

    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.selectedFileName = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        this.parsedJson = JSON.parse(String(reader.result ?? ''));
      } catch (e) {
        this.uploadError = `Invalid JSON: ${e instanceof Error ? e.message : String(e)}`;
      }
    };
    reader.onerror = () => { this.uploadError = 'Failed to read file.'; };
    reader.readAsText(file, 'utf-8');
  }

  async validate(): Promise<void> {
    this.validateError = '';
    this.validateResult = null;
    this.mappingState = 'idle';
    this.mappingResult = null;
    this.mappingError = '';
    this.showAasDraft = false;

    if (!this.parsedJson || typeof this.parsedJson !== 'object') {
      this.validateError = 'Select a valid JSON file first.';
      return;
    }

    this.validateState = 'loading';
    try {
      const resp = await fetch('/api/v1/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: this.target, payload: this.parsedJson }),
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      this.validateResult = await resp.json() as ValidateResult;
      this.validateState = 'done';
    } catch (e) {
      this.validateError = e instanceof Error ? e.message : String(e);
      this.validateState = 'error';
    }
  }

  async runMappingAgent(): Promise<void> {
    this.mappingError = '';
    this.mappingResult = null;
    this.showAasDraft = false;

    const columns = this.validateResult?.extracted_columns ?? [];
    if (columns.length === 0) {
      this.mappingError = 'No columns extracted — validate the JSON first.';
      return;
    }

    this.mappingState = 'loading';
    try {
      const resp = await fetch('/api/v1/semantic/mapping-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns }),
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      this.mappingResult = await resp.json() as MappingResult;
      this.mappingState = 'done';
      this.showAasDraft = true;
    } catch (e) {
      this.mappingError = e instanceof Error ? e.message : String(e);
      this.mappingState = 'error';
    }
  }

  async upload(): Promise<void> {
    this.uploadError = '';
    this.uploadResult = '';

    if (!this.parsedJson || typeof this.parsedJson !== 'object') {
      this.uploadError = 'Select a valid JSON file first.';
      return;
    }

    const endpoint =
      this.target === 'provider-asset'
        ? '/provider/api/management/v3/assets'
        : '/aas/api/shells';

    this.uploadState = 'loading';
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(this.parsedJson),
      });
      const text = await resp.text();
      if (!resp.ok) throw new Error(`HTTP ${resp.status} ${text}`);
      this.uploadResult = text || 'Upload succeeded (empty response body).';
      this.uploadState = 'done';
    } catch (e) {
      this.uploadError = e instanceof Error ? e.message : String(e);
      this.uploadState = 'error';
    }
  }
}
