/*
 * Copyright (c) 2025 Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Apache License, Version 2.0 which is available at
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Contributors:
 *      Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V. - initial API and implementation
 *      m-x-dataspace team - expose AAS metadata fields in catalog cards
 *
 */

import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';

import { CatalogDataset } from '../catalog-dataset';

@Component({
  selector: 'lib-catalog-card',
  standalone: true,
  imports: [],
  templateUrl: './catalog-card.component.html',
  styleUrl: './catalog-card.component.css',
})
export class CatalogCardComponent implements OnInit {
  @Input() catalogDataset?: CatalogDataset;
  @Input() showButtons = true;

  @Output() detailsEvent = new EventEmitter<CatalogDataset>();
  @Output() negotiateEvent = new EventEmitter<CatalogDataset>();

  name?: string;
  version?: string;
  contentType?: string;
  participantId?: string;
  aasShellId?: string;
  aasSubmodelId?: string;
  aasSemanticId?: string;
  aasSubmodelEndpoint?: string;

  ngOnInit() {
    this.name = this.catalogDataset?.assetId;
    this.version = this.catalogDataset?.dataset?.['asset:prop:version']?.[0]?.['@value'];
    this.contentType = this.catalogDataset?.dataset.mandatoryValue('edc', 'contenttype');
    this.participantId = this.catalogDataset?.participantId;

    const dataset: Record<string, unknown> | undefined = this.catalogDataset?.dataset as unknown as
      | Record<string, unknown>
      | undefined;
    if (!dataset) return;

    this.aasShellId = (dataset['edc:aasShellId'] as string | undefined) ?? (dataset['aasShellId'] as string | undefined);
    this.aasSubmodelId =
      (dataset['edc:aasSubmodelId'] as string | undefined) ?? (dataset['aasSubmodelId'] as string | undefined);
    this.aasSemanticId =
      (dataset['edc:aasSemanticId'] as string | undefined) ?? (dataset['aasSemanticId'] as string | undefined);
    this.aasSubmodelEndpoint =
      (dataset['edc:aasSubmodelEndpoint'] as string | undefined) ??
      (dataset['aasSubmodelEndpoint'] as string | undefined);
  }
}

