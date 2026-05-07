import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { AssetViewComponent } from '@eclipse-edc/dashboard-core/assets';
import { AssetJsonUploadComponent } from '../asset-json-upload/asset-json-upload.component';

@Component({
  selector: 'app-assets-merged',
  standalone: true,
  imports: [CommonModule, AssetViewComponent, AssetJsonUploadComponent],
  templateUrl: './assets-merged.component.html',
})
export class AssetsMergedComponent {
  tab: 'assets' | 'json' = 'assets';
  assetViewComponent = AssetViewComponent;
}

