import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-aas-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './aas-view.component.html',
})
export class AasViewComponent {
  loadingAssets = false;
  loadingDataset = false;
  loadingShells = false;
  loadingRegister = false;
  error = '';

  assetId = '';
  counterPartyId = 'counter-party-id';
  counterPartyAddress = 'http://app:8000/proxy/provider/protocol/2025-1';

  aasAssets: Record<string, unknown>[] = [];
  datasetResult: Record<string, unknown> | null = null;
  shells: Record<string, unknown>[] = [];

  async loadAasAssets(): Promise<void> {
    this.error = '';
    this.loadingAssets = true;
    this.datasetResult = null;
    try {
      const body = {
        '@context': {
          '@vocab': 'https://w3id.org/edc/v0.0.1/ns/',
        },
        '@type': 'QuerySpec',
        limit: 200,
      };

      const resp = await fetch('/provider/api/management/v3/assets/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        throw new Error(`Asset query failed: HTTP ${resp.status}`);
      }
      const data = (await resp.json()) as Record<string, unknown>[];
      this.aasAssets = data.filter(item => {
        const props = item['properties'] as Record<string, unknown> | undefined;
        return !!props?.['aasShellId'] || !!props?.['aasSubmodelId'] || !!props?.['aasSemanticId'];
      });
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loadingAssets = false;
    }
  }

  async requestDataset(): Promise<void> {
    this.error = '';
    this.datasetResult = null;
    this.loadingDataset = true;
    try {
      if (!this.assetId.trim()) {
        throw new Error('assetId is required.');
      }
      const body = {
        '@context': { edc: 'https://w3id.org/edc/v0.0.1/ns/' },
        '@type': 'DatasetRequest',
        '@id': this.assetId.trim(),
        counterPartyId: this.counterPartyId.trim(),
        counterPartyAddress: this.counterPartyAddress.trim(),
        protocol: 'dataspace-protocol-http:2025-1',
      };
      const resp = await fetch('/consumer/api/management/v3/catalog/dataset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Dataset request failed: HTTP ${resp.status} ${text}`);
      }
      this.datasetResult = (await resp.json()) as Record<string, unknown>;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loadingDataset = false;
    }
  }

  async loadShellDescriptors(): Promise<void> {
    this.error = '';
    this.loadingShells = true;
    try {
      const resp = await fetch('/aas/api/shells', {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`AAS shell query failed: HTTP ${resp.status} ${text}`);
      }
      const data = (await resp.json()) as unknown;
      this.shells = Array.isArray(data) ? (data as Record<string, unknown>[]) : [];
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loadingShells = false;
    }
  }

  async registerSampleShell(): Promise<void> {
    this.error = '';
    this.loadingRegister = true;
    try {
      const uid = crypto.randomUUID();
      const shellId = `urn:uuid:${crypto.randomUUID()}`;
      const body = {
        id: shellId,
        idShort: `SampleShell-${uid.substring(0, 8)}`,
        assetInformation: {
          assetKind: 'INSTANCE',
          globalAssetId: `urn:uuid:${crypto.randomUUID()}`,
        },
        submodels: [],
      };
      const resp = await fetch('/aas/api/shells', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`AAS sample register failed: HTTP ${resp.status} ${text}`);
      }
      await this.loadShellDescriptors();
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loadingRegister = false;
    }
  }

  setAssetId(assetId: string): void {
    this.assetId = assetId;
  }

  getItemId(item: Record<string, unknown>): string {
    const id = item['@id'] ?? item['id'];
    return typeof id === 'string' ? id : '';
  }

  getProp(item: Record<string, unknown>, key: string): string {
    const props = item['properties'];
    if (!props || typeof props !== 'object') {
      return '-';
    }
    const value = (props as Record<string, unknown>)[key];
    return typeof value === 'string' && value.length > 0 ? value : '-';
  }
}
