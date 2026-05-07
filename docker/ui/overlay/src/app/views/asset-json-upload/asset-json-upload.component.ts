import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type UploadTarget = 'provider-asset' | 'aas-shell';

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
  loading = false;
  error = '';
  result = '';

  onFileSelected(event: Event): void {
    this.error = '';
    this.result = '';
    this.parsedJson = null;
    this.selectedFileName = '';

    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.selectedFileName = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const text = String(reader.result ?? '');
        this.parsedJson = JSON.parse(text);
      } catch (e) {
        this.error = `Invalid JSON file: ${e instanceof Error ? e.message : String(e)}`;
      }
    };
    reader.onerror = () => {
      this.error = 'Failed to read file.';
    };
    reader.readAsText(file, 'utf-8');
  }

  async upload(): Promise<void> {
    this.error = '';
    this.result = '';
    if (!this.parsedJson || typeof this.parsedJson !== 'object') {
      this.error = 'Select a valid JSON file first.';
      return;
    }

    const endpoint =
      this.target === 'provider-asset'
        ? '/provider/api/management/v3/assets'
        : '/aas/api/shells';

    this.loading = true;
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(this.parsedJson),
      });
      const text = await resp.text();
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status} ${text}`);
      }
      this.result = text || 'Upload succeeded (empty response body).';
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }
}

