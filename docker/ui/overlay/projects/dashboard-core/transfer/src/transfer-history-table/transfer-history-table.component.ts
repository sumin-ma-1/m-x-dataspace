/*
 *  Copyright (c) 2025 Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V.
 *
 *  This program and the accompanying materials are made available under the
 *  terms of the Apache License, Version 2.0 which is available at
 *  https://www.apache.org/licenses/LICENSE-2.0
 *
 *  SPDX-License-Identifier: Apache-2.0
 *
 *  Contributors:
 *       Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V. - initial API and implementation
 *       m-x-dataspace team – empty-state placement for filtered dashboard layout
 */

import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, inject } from '@angular/core';

import { TransferProcess, TransferProcessStates } from '@think-it-labs/edc-connector-client';
import { DatePipe, NgClass } from '@angular/common';
import { TransferHistoryDetailsComponent } from '../transfer-history-details/transfer-history-details.component';
import { DeleteConfirmComponent, ModalAndAlertService } from '@eclipse-edc/dashboard-core';

@Component({
  selector: 'lib-transfer-history-table',
  standalone: true,
  imports: [NgClass, DatePipe],
  templateUrl: './transfer-history-table.component.html',
})
export class TransferHistoryTableComponent implements OnChanges {
  private readonly modalAndAlertService = inject(ModalAndAlertService);

  @Input() transferProcesses: TransferProcess[] | null = [];
  /** Consumer-side empty list: show inline hint (flow layout); Provider keeps generic row. */
  @Input() showFirstTransferHint = false;
  @Output() deprovisionEvent = new EventEmitter<TransferProcess>();

  validStates = new Set<string>([
    TransferProcessStates.INITIAL,
    TransferProcessStates.PROVISIONED,
    TransferProcessStates.REQUESTED,
    TransferProcessStates.STARTED,
    TransferProcessStates.COMPLETED,
  ]);

  exceptionStates = new Set<string>([TransferProcessStates.SUSPENDED, TransferProcessStates.TERMINATED]);

  stateType: Record<string, string> = {};

  async ngOnChanges(changes: SimpleChanges) {
    if (changes['transferProcesses']) {
      if (this.transferProcesses) {
        for (const transferProcess of this.transferProcesses) {
          if (transferProcess.id) {
            this.stateType[transferProcess.id] = this.getStateType(transferProcess.state);
          }
        }
      }
    }
  }

  private getStateType(state: string) {
    if (this.validStates.has(state)) {
      return 'okay';
    } else if (this.exceptionStates.has(state)) {
      return 'error';
    } else {
      return 'neutral';
    }
  }

  openDetails(transferProcess: TransferProcess) {
    this.modalAndAlertService.openModal(TransferHistoryDetailsComponent, {
      transferProcess: transferProcess,
      stateType: this.stateType[transferProcess.id],
    });
  }

  deprovision(transferProcess: TransferProcess) {
    this.modalAndAlertService.openModal(
      DeleteConfirmComponent,
      {
        customText: `Do you really want to request the deprovisioning of transfer process '${transferProcess.id}'?`,
      },
      {
        canceled: () => this.modalAndAlertService.closeModal(),
        confirm: () => {
          this.modalAndAlertService.closeModal();
          this.deprovisionEvent.emit(transferProcess);
        },
      },
    );
  }
}
