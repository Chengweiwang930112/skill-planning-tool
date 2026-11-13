import { httpResource } from '@angular/common/http';
import { Component, computed, inject, input, numberAttribute } from '@angular/core';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { SiBadgeComponent } from '@siemens/element-ng/badge';
import { SiEmptyStateComponent } from '@siemens/element-ng/empty-state';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import { SiSearchBarComponent } from '@siemens/element-ng/search-bar';
import type { EmployeePage, EmployeeSort } from '../api/models';
import { problemMessage } from '../api/problem';
import { LEVEL_BADGE } from '../shared/level';

export const PAGE_SIZE = 20;
const DEFAULT_SORT: EmployeeSort = 'last_name';

type SortField = 'last_name' | 'employee_number' | 'department' | 'location';

/** Filters, sorting and paging live in the URL, so every view can be bookmarked. */
@Component({
  selector: 'app-employee-list',
  imports: [
    SiBadgeComponent,
    SiEmptyStateComponent,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SiPaginationComponent,
    SiSearchBarComponent,
  ],
  templateUrl: './employee-list.html',
  styleUrl: './employee-list.scss',
})
export class EmployeeList {
  readonly q = input<string>();
  readonly sort = input<EmployeeSort>();
  readonly page = input(1, { transform: (value: unknown) => numberAttribute(value, 1) });

  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly pageSize = PAGE_SIZE;
  protected readonly columns: { label: string; sort?: SortField }[] = [
    { label: 'Name', sort: 'last_name' },
    { label: 'Employee no.', sort: 'employee_number' },
    { label: 'Department', sort: 'department' },
    { label: 'Job title' },
    { label: 'Location', sort: 'location' },
    { label: 'Skills' },
  ];
  protected readonly levelBadge = LEVEL_BADGE;
  protected readonly employees = httpResource<EmployeePage>(() => {
    const q = this.q();
    return {
      url: '/api/v1/employees',
      params: {
        page: this.page(),
        page_size: PAGE_SIZE,
        sort: this.sort() ?? DEFAULT_SORT,
        ...(q ? { q } : {}),
      },
    };
  });
  protected readonly error = computed(() => {
    const error = this.employees.error();
    return error ? problemMessage(error) : undefined;
  });

  private readonly activeSort = computed(() => this.sort() ?? DEFAULT_SORT);

  protected sortDirection(field: SortField): 'ascending' | 'descending' | 'none' {
    const sort = this.activeSort();
    return sort === field ? 'ascending' : sort === `-${field}` ? 'descending' : 'none';
  }

  protected sortBy(field: SortField): void {
    const next = this.activeSort() === field ? `-${field}` : field;
    this.navigate({ sort: next === DEFAULT_SORT ? null : next, page: null });
  }

  protected search(q: string): void {
    this.navigate({ q: q || null, page: null });
  }

  protected goToPage(page: number): void {
    this.navigate({ page: page === 1 ? null : page });
  }

  private navigate(queryParams: Params): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge',
    });
  }
}
