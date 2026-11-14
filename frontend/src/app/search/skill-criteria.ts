import { Component, computed, input, linkedSignal, output, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { Level } from '../api/models';
import { Criterion, formatCriterion } from '../shared/criteria';
import { LEVELS } from '../shared/level';
import { SkillPicker, SkillPickerHint } from '../shared/skill-picker';

export const MAX_CRITERIA = 10;

/** Criteria are edited as a draft; every Search (or Enter) runs the search again. */
@Component({
  selector: 'app-skill-criteria',
  imports: [FormsModule, SkillPicker, SkillPickerHint],
  templateUrl: './skill-criteria.html',
  styleUrl: './skill-criteria.scss',
})
export class SkillCriteria {
  /** The criteria of the current results. */
  readonly criteria = input.required<Criterion[]>();
  readonly criteriaChange = output<Criterion[]>();

  protected readonly levels = LEVELS;
  protected readonly maxCriteria = MAX_CRITERIA;
  protected readonly draft = linkedSignal(() => this.criteria());
  protected readonly pending = computed(
    () => this.draft().map(formatCriterion).join() !== this.criteria().map(formatCriterion).join(),
  );
  protected readonly draftNames = computed(() => this.draft().map((c) => c.name));
  protected readonly picker = viewChild(SkillPicker);
  protected newLevel: Level | '' = 'advanced';

  protected setLevel(index: number, level: Level | ''): void {
    this.draft.update((draft) =>
      draft.map((c, i) => (i === index ? { name: c.name, ...(level && { level }) } : c)),
    );
  }

  protected remove(index: number): void {
    this.draft.update((draft) => draft.filter((_, i) => i !== index));
  }

  /** Adds the chosen skill to the draft without searching; false if nothing is chosen. */
  protected add(): boolean {
    const picker = this.picker();
    if (!picker?.validate() || !picker.skill) {
      return false;
    }
    const { name } = picker.skill;
    const level = this.newLevel;
    picker.clear();
    if (!this.draft().some((c) => c.name === name) && this.draft().length < MAX_CRITERIA) {
      this.draft.update((draft) => [...draft, { name, ...(level && { level }) }]);
    }
    return true;
  }

  /** Searches for the draft and a chosen skill not added yet, but never for unchosen text. */
  protected search(): void {
    if (this.picker()?.query && !this.add()) {
      return;
    }
    this.criteriaChange.emit(this.draft());
  }
}
