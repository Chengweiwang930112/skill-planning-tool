import { Component, computed, inject, input, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import type { EmployeeSort } from '../api/models';
import { EmployeeList } from '../employees/employee-list';
import { Criterion, formatCriterion, parseCriterion } from '../shared/criteria';
import { SkillCriteria } from './skill-criteria';

/** The home page: skill criteria on top, the employees who match below. The criteria live
 * in the URL in the API's format, so a search can be shared as a link. */
@Component({
  selector: 'app-skill-search',
  imports: [EmployeeList, SkillCriteria],
  template: `
    <section class="finder surface-dark">
      <div class="container-fluid">
        <h1 class="finder-title">Find people by skill</h1>
        <p class="finder-lead">
          List the skills you need with the lowest level that will do. People at a higher level
          match too.
        </p>
        <app-skill-criteria [criteria]="criteria()" (criteriaChange)="search($event)" />
      </div>
    </section>

    <div class="container-fluid py-6">
      <app-employee-list
        [skill]="skill()"
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
  readonly skill = input([], {
    transform: (value: unknown): string[] =>
      value == null ? [] : Array.isArray(value) ? value : [String(value)],
  });
  readonly q = input<string>();
  readonly sort = input<EmployeeSort>();
  readonly page = input<unknown>();
  readonly employee = input<unknown>();

  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly results = viewChild(EmployeeList);

  protected readonly criteria = computed(() => this.skill().map(parseCriterion));

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
