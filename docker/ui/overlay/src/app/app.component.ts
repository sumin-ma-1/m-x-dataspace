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
 * Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V. - initial API and implementation
 * m-x-dataspace team - hide provider-only menus while consuming
 *
 */

import { AfterViewInit, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import {
  AppConfig,
  DashboardAppComponent,
  DashboardStateService,
  EdcConfig,
} from '@eclipse-edc/dashboard-core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Routes managed only on the Provider connector — hide from Consumer in the sidebar. */
const PROVIDER_ONLY_ROUTES = new Set(['assets', 'policies', 'contract-definitions']);
/** Routes managed only on the Consumer connector — hide from Provider in the sidebar. */
const CONSUMER_ONLY_ROUTES = new Set(['catalog']);

@Component({
  selector: 'app-root',
  standalone: true,
  templateUrl: './app.component.html',
  imports: [DashboardAppComponent],
  styleUrl: './app.component.css',
})
export class AppComponent implements AfterViewInit {
  private readonly http = inject(HttpClient);
  private readonly state = inject(DashboardStateService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly themes = [
    'light',
    'dark',
    'dim',
    'aqua',
    'nord',
    'synthwave',
    'forest',
    'dracula',
    'night',
    'coffee',
    'emerald',
  ];
  edcConfigs?: Promise<EdcConfig[]>;
  appConfig?: Promise<AppConfig>;

  constructor() {
    this.edcConfigs = firstValueFrom(this.http.get<EdcConfig[]>('config/edc-connector-config.json'));
    this.appConfig = firstValueFrom(this.http.get<AppConfig>('config/app-config.json'));
  }

  async ngAfterViewInit(): Promise<void> {
    // Runs after child DashboardApp.ngAfterViewInit (sets initial full menu via setAppConfig).
    const base = await this.appConfig!;

    this.state.currentEdcConfig$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(edc => {
        this.state.setAppConfig(this.filterMenuForConnector(base, edc));
        this.redirectIfRoleOnHiddenRoute(edc);
      });
  }

  private filterMenuForConnector(base: AppConfig, edc: EdcConfig | undefined): AppConfig {
    const role = (edc?.connectorName ?? '').toLowerCase();
    const isConsumer = role === 'consumer';
    const isProvider = role === 'provider';

    if (!isConsumer && !isProvider) return base;

    return {
      ...base,
      menuItems: base.menuItems.filter(item => {
        if (isConsumer && PROVIDER_ONLY_ROUTES.has(item.routerPath)) return false;
        if (isProvider && CONSUMER_ONLY_ROUTES.has(item.routerPath)) return false;
        return true;
      }),
    };
  }

  private redirectIfRoleOnHiddenRoute(edc: EdcConfig | undefined): void {
    const role = (edc?.connectorName ?? '').toLowerCase();
    const path = this.router.url.split('?')[0].split('#')[0];
    const segments = path.replace(/^\/+/, '').split('/').filter(Boolean);
    const top = segments[0];
    if (!top) return;

    if (role === 'consumer' && PROVIDER_ONLY_ROUTES.has(top)) {
      void this.router.navigate(['/catalog']);
      return;
    }
    if (role === 'provider' && CONSUMER_ONLY_ROUTES.has(top)) {
      void this.router.navigate(['/assets']);
    }
  }
}
