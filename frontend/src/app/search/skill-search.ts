import { Component, computed, inject, input, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Filter, SiFilterBarComponent } from '@siemens/element-ng/filter-bar';
import type { EmployeeSort } from '../api/models';
import { EmployeeFilterValues, EmployeeFilters } from '../employees/employee-filters';
import { EmployeeList } from '../employees/employee-list';
import { Criterion, formatCriterion, parseCriterion } from '../shared/criteria';
import { toList } from '../shared/query-params';
import { SkillCriteria } from './skill-criteria';

/** The home page: what to look for on top — skills, departments, locations — and the
 * employees who match below. All of it lives in the URL in the API's format, so a search
 * can be shared as a link, and all of it narrows down every employee, not one page. */
@Component({
  selector: 'app-skill-search',
  imports: [EmployeeFilters, EmployeeList, SiFilterBarComponent, SkillCriteria],
  template: `
    <section class="finder surface-dark">
      <div class="container-fluid">
        <h1 class="finder-title">Find people by skill</h1>
        <p class="finder-lead">
          List the skills you need with the lowest level that will do. People at a higher level
          match too.
        </p>
        <app-skill-criteria [criteria]="criteria()" (criteriaChange)="search($event)" />
        <app-employee-filters
          class="finder-filters"
          [values]="filterValues()"
          (valuesChange)="applyFilters($event)"
        >
          @if (activeFilters().length) {
            <si-filter-bar
              allowReset
              resetText="Clear all"
              [filters]="activeFilters()"
              (filtersChange)="keepFilters($event)"
            />
          }
        </app-employee-filters>
      </div>
    </section>

    <div class="container-fluid py-6">
      <app-employee-list
        [skill]="skill()"
        [department]="department()"
        [location]="location()"
        [q]="q()"
        [sort]="sort()"
        [page]="page()"
        [employee]="employee()"
      />
    </div>
  `,
  styleUrl: './skill-search.scss',
})
export class SkillSearch {
  readonly skill = input([], { transform: toList });
  readonly department = input([], { transform: toList });
  readonly location = input([], { transform: toList });
  readonly q = input<string>();
  readonly sort = input<EmployeeSort>();
  readonly page = input<unknown>();
  readonly employee = input<unknown>();

  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly results = viewChild(EmployeeList);

  protected readonly criteria = computed(() => this.skill().map(parseCriterion));
  protected readonly filterValues = computed<EmployeeFilterValues>(() => ({
    department: this.department(),
    location: this.location(),
  }));
  protected readonly activeFilters = computed<Filter[]>(() => [
    ...this.department().map((name) => pill('department', 'Department', name)),
    ...this.location().map((name) => pill('location', 'Location', name)),
  ]);

  protected applyFilters({ department, location }: EmployeeFilterValues): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        department: department.length ? department : null,
        location: location.length ? location : null,
        page: null,
      },
      queryParamsHandling: 'merge',
    });
  }

  /** The filter bar reports the filters left after one was removed. */
  protected keepFilters(filters: Filter[]): void {
    const values = (field: string) =>
      filters.filter((f) => f.filterName.startsWith(`${field}:`)).map((f) => f.description ?? '');
    this.applyFilters({ department: values('department'), location: values('location') });
  }

  /** Every search sends a request, also when it repeats the current one. */
  protected search(criteria: Criterion[]): void {
    const skill = criteria.map(formatCriterion);
    const urlUnchanged =
      skill.join('\n') === this.skill().join('\n') && (this.page() ?? '1') === '1';
    const results = this.results();
    if (!urlUnchanged) {
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { skill, page: null },
        queryParamsHandling: 'merge',
      });
    } else if (results) {
      // The router ignores a navigation to the current URL, so ask for the results again.
      results.reload();
    }
  }
}

function pill(field: string, title: string, name: string): Filter {
  return { filterName: `${field}:${name}`, title, description: name };
}
