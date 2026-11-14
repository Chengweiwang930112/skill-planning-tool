import { HttpClient } from '@angular/common/http';
import { Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  SiTypeaheadDirective,
  TypeaheadMatch,
  TypeaheadOptionSource,
} from '@siemens/element-ng/typeahead';
import { map } from 'rxjs';
import type { Skill, SkillPage } from '../api/models';

/**
 * Typed text only searches the catalogue; a skill counts once it is chosen from it.
 * Its hint is shown by SkillPickerHint, below the form row, so it cannot misalign the row.
 */
@Component({
  selector: 'app-skill-picker',
  imports: [FormsModule, SiTypeaheadDirective],
  template: `
    <label class="form-label" [for]="inputId()">{{ label() }}</label>
    <input
      class="form-control"
      autocomplete="off"
      maxlength="100"
      placeholder="Search the catalogue, e.g. Kubernetes"
      [id]="inputId()"
      [disabled]="disabled()"
      [siTypeahead]="suggestions"
      typeaheadOptionField="name"
      [typeaheadProcess]="false"
      typeaheadFullWidth
      [attr.aria-invalid]="hint() ? true : null"
      [ngModel]="text()"
      [ngModelOptions]="{ standalone: true }"
      (ngModelChange)="typed($event)"
      (typeaheadOnSelect)="choose($event)"
    />
  `,
})
export class SkillPicker {
  readonly label = input('Skill');
  readonly inputId = input('skill-picker');
  readonly disabled = input(false);
  readonly exclude = input<string[]>([]);
  readonly skillChange = output<Skill | undefined>();

  private readonly http = inject(HttpClient);

  protected readonly text = signal('');
  readonly hint = signal<string | undefined>(undefined);
  readonly notFound = signal(false);
  private chosen: Skill | undefined;
  private last: { q: string; skills: Skill[]; offered: number } | undefined;

  protected readonly suggestions: TypeaheadOptionSource = (q: string) =>
    this.http
      .get<SkillPage>('/api/v1/skills', { params: q ? { q, page_size: 10 } : { page_size: 10 } })
      .pipe(
        map((page) => page.items.map(({ id, name }) => ({ id, name }))),
        map((skills) => {
          const excluded = new Set(this.exclude().map((name) => name.toLowerCase()));
          const offered = skills.filter((skill) => !excluded.has(skill.name.toLowerCase()));
          this.last = { q, skills, offered: offered.length };
          return offered;
        }),
      );

  get skill(): Skill | undefined {
    return this.chosen;
  }

  get query(): string {
    return this.text().trim();
  }

  /** Whether a skill is chosen; explains why not if something was typed. */
  validate(): boolean {
    const typed = this.query;
    if (this.chosen || !typed) {
      return !!this.chosen;
    }
    const searched = this.last?.q.trim() === typed ? this.last : undefined;
    const exact = searched?.skills.find((s) => s.name.toLowerCase() === typed.toLowerCase());
    if (exact) {
      this.text.set(exact.name);
      this.select(exact);
      return true;
    }
    this.notFound.set(searched?.skills.length === 0);
    this.hint.set(
      this.notFound()
        ? `“${typed}” is not in the skill catalogue.`
        : searched?.offered === 0
          ? `Every skill matching “${typed}” is listed already.`
          : 'Choose a skill from the suggestions.',
    );
    return false;
  }

  clear(): void {
    this.text.set('');
    this.select(undefined);
  }

  protected typed(text: string): void {
    this.text.set(text);
    if (this.chosen && text !== this.chosen.name) {
      this.select(undefined);
    }
    this.hint.set(undefined);
  }

  protected choose(match: TypeaheadMatch): void {
    // Without its own processing, the typeahead wraps each option as { text, option }.
    const option = match.option as Skill | { option: Skill };
    const { id, name } = 'option' in option ? option.option : option;
    this.text.set(name);
    this.select({ id, name });
  }

  private select(skill: Skill | undefined): void {
    this.chosen = skill;
    this.hint.set(undefined);
    this.skillChange.emit(skill);
  }
}

@Component({
  selector: 'app-skill-picker-hint',
  imports: [RouterLink],
  template: `
    @if (picker().hint(); as message) {
      <p class="si-caption text-danger mt-2 mb-0" role="alert">
        {{ message }}
        @if (picker().notFound()) {
          <a routerLink="/skills">Open the skill catalogue</a>
        }
      </p>
    }
  `,
})
export class SkillPickerHint {
  readonly picker = input.required<SkillPicker>();
}
