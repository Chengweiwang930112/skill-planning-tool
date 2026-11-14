import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, input, linkedSignal, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SiTypeaheadDirective, TypeaheadOptionSource } from '@siemens/element-ng/typeahead';
import { map } from 'rxjs';
import type { Level, SkillPage } from '../api/models';
import { Criterion, formatCriterion } from '../shared/criteria';
import { LEVELS } from '../shared/level';

export const MAX_CRITERIA = 10;

/** Criteria are edited as a draft; every Search (or Enter) runs the search again. */
@Component({
  selector: 'app-skill-criteria',
  imports: [FormsModule, SiTypeaheadDirective],
  templateUrl: './skill-criteria.html',
  styleUrl: './skill-criteria.scss',
})
export class SkillCriteria {
  /** The criteria of the current results. */
  readonly criteria = input.required<Criterion[]>();
  readonly criteriaChange = output<Criterion[]>();

  private readonly http = inject(HttpClient);

  protected readonly levels = LEVELS;
  protected readonly maxCriteria = MAX_CRITERIA;
  protected readonly draft = linkedSignal(() => this.criteria());
  protected readonly pending = computed(
    () => this.draft().map(formatCriterion).join() !== this.criteria().map(formatCriterion).join(),
  );
  protected newSkill = '';
  protected newLevel: Level | '' = 'advanced';

  protected readonly suggestions: TypeaheadOptionSource = (q: string) =>
    this.http
      .get<SkillPage>('/api/v1/skills', { params: q ? { q, page_size: 10 } : { page_size: 10 } })
      .pipe(map((page) => page.items.map((skill) => skill.name).filter((name) => !this.has(name))));

  protected setLevel(index: number, level: Level | ''): void {
    this.draft.update((draft) =>
      draft.map((c, i) => (i === index ? { name: c.name, ...(level && { level }) } : c)),
    );
  }

  protected remove(index: number): void {
    this.draft.update((draft) => draft.filter((_, i) => i !== index));
  }

  /** Adds the typed skill to the draft without searching. */
  protected add(): void {
    const name = this.newSkill.trim().replace(/\s+/g, ' ');
    if (!name || this.has(name) || this.draft().length >= MAX_CRITERIA) {
      return;
    }
    this.newSkill = '';
    const level = this.newLevel;
    this.draft.update((draft) => [...draft, { name, ...(level && { level }) }]);
  }

  /** Searches for the draft, including a skill that was typed but not added yet. */
  protected search(): void {
    this.add();
    this.criteriaChange.emit(this.draft());
  }

  private has(name: string): boolean {
    return this.draft().some((c) => c.name.toLowerCase() === name.trim().toLowerCase());
  }
}
