import { Component, computed, inject, input, signal, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SiEmptyStateComponent } from '@siemens/element-ng/empty-state';
import type { EmployeeSort } from '../api/models';
import { EmployeeList } from '../employees/employee-list';
import { Criterion, formatCriterion, parseCriterion } from '../shared/criteria';
import { SkillCriteria } from './skill-criteria';

/** The criteria live in the URL in the API's format, so a search can be shared as a link. */
@Component({
  selector: 'app-skill-search',
  imports: [EmployeeList, SiEmptyStateComponent, SkillCriteria],
  template: `
    <h1 class="si-h3 mb-2">Skill search</h1>
    <p class="text-secondary mb-6">
      Find employees by skill and minimum level. Employees must have every skill listed; a minimum
      level also finds employees above it.
    </p>

    <section class="mb-8">
      <app-skill-criteria [criteria]="criteria()" (criteriaChange)="search($event)" />
    </section>

    @if (showResults()) {
      <app-employee-list
        embedded
        [skill]="skill()"
        [q]="q()"
        [sort]="sort()"
        [page]="page()"
        [employee]="employee()"
      />
    } @else {
      <si-empty-state
        icon="element-search"
        heading="Who has the skills you need?"
        content="Add a skill above, for example Kubernetes at advanced or higher, and press Search."
      />
    }
  `,
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
  /** Set by a search without criteria, which lists everybody. */
  private readonly searchedAll = signal(false);
  protected readonly showResults = computed(() => this.criteria().length > 0 || this.searchedAll());

  /** Every search sends a request, also when it repeats the current one. */
  protected search(criteria: Criterion[]): void {
    const skill = criteria.map(formatCriterion);
    const urlUnchanged =
      skill.join('\n') === this.skill().join('\n') && (this.page() ?? '1') === '1';
    const results = this.results();
    this.searchedAll.set(skill.length === 0);
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
