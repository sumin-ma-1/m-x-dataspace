/*
 * Copyright (c) 2025 Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { DashboardStateService, EdcConfig } from '@eclipse-edc/dashboard-core';
import { map, take } from 'rxjs/operators';

function resolveConnector(edc: EdcConfig | undefined): EdcConfig | undefined {
  if (edc) {
    return edc;
  }
  try {
    const raw = localStorage.getItem('currentConnector');
    if (!raw) {
      return undefined;
    }
    return JSON.parse(raw) as EdcConfig;
  } catch {
    return undefined;
  }
}

/**
 * Block Provider-management routes when the selected connector is Consumer.
 * Prevents direct URL / bookmark / refresh from showing those pages.
 */
export const consumerCannotAccessProviderManagementGuard: CanActivateFn = () => {
  const state = inject(DashboardStateService);
  const router = inject(Router);

  return state.currentEdcConfig$.pipe(
    take(1),
    map(edc => resolveConnector(edc)),
    map(edc => {
      const isConsumer = (edc?.connectorName ?? '').toLowerCase() === 'consumer';
      return isConsumer ? router.createUrlTree(['/catalog']) : true;
    }),
  );
};
