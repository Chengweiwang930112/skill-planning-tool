import { DatePipe } from '@angular/common';
import { HttpClient, httpResource } from '@angular/common/http';
import {
  Component,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { SiTypeaheadDirective, TypeaheadOptionSource } from '@siemens/element-ng/typeahead';
import { firstValueFrom, map } from 'rxjs';
import type { Employee, Level, SkillPage } from '../api/models';
import { problemMessage } from '../api/problem';
import { LEVELS } from '../shared/level';

export interface DraftSkill {
  name: string;
  level: Level;
}

function draftOf(employee: Employee): DraftSkill[] {
  return employee.skills.map(({ skill, level }) => ({ name: skill.name, level }));
}

function sameSkills(a: DraftSkill[], b: DraftSkill[]): boolean {
  const key = (skills: DraftSkill[]) =>
    skills
      .map((s) => `${s.name.toLowerCase()}:${s.level}`)
      .sort()
      .join();
  return key(a) === key(b);
}

/** Skill edits change a draft; Save sends the whole draft in one request. */
@Component({
  selector: 'app-employee-panel',
  imports: [
    DatePipe,
    FormsModule,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SiTypeaheadDirective,
  ],
  templateUrl: './employee-panel.html',
  styleUrl: './employee-panel.scss',
})
export class EmployeePanel {
  readonly employeeId = input.required<number>();
  /** The employee as stored, after it is loaded and after every save. */
  readonly changed = output<Employee>();
  readonly exit = output<void>();

  private readonly http = inject(HttpClient);

  protected readonly levels = LEVELS;
  protected readonly employee = httpResource<Employee>(
    () => `/api/v1/employees/${this.employeeId()}`,
  );
  protected readonly loadError = computed(() => {
    const error = this.employee.error();
    return error ? problemMessage(error) : undefined;
  });

  /** Starts over from the stored skills whenever they change. */
  protected readonly draft = linkedSignal<DraftSkill[]>(() =>
    this.employee.hasValue() ? draftOf(this.employee.value()) : [],
  );
  protected readonly dirty = computed(
    () => this.employee.hasValue() && !sameSkills(this.draft(), draftOf(this.employee.value())),
  );
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly saveError = signal<string | undefined>(undefined);

  protected newSkill = '';
  protected newLevel: Level = 'intermediate';

  protected readonly suggestions: TypeaheadOptionSource = (q: string) =>
    this.http
      .get<SkillPage>('/api/v1/skills', { params: q ? { q, page_size: 10 } : { page_size: 10 } })
      .pipe(
        map((page) => page.items.map((skill) => skill.name).filter((name) => !this.find(name))),
      );

  constructor() {
    effect(() => {
      if (this.employee.hasValue()) {
        this.changed.emit(this.employee.value());
      }
    });
  }

  protected changeLevel(name: string, level: Level): void {
    this.edit((skills) => skills.map((s) => (s.name === name ? { ...s, level } : s)));
  }

  protected remove(name: string): void {
    this.edit((skills) => skills.filter((s) => s.name !== name));
  }

  protected add(): void {
    const name = this.newSkill.trim().replace(/\s+/g, ' ');
    if (!name) {
      return;
    }
    const level = this.newLevel;
    this.newSkill = '';
    const existing = this.find(name);
    this.edit((skills) =>
      existing
        ? skills.map((s) => (s === existing ? { ...s, level } : s))
        : [...skills, { name, level }],
    );
  }

  protected async save(): Promise<void> {
    this.saving.set(true);
    this.saveError.set(undefined);
    try {
      const employee = await firstValueFrom(
        this.http.put<Employee>(`/api/v1/employees/${this.employeeId()}/skills`, {
          skills: this.draft(),
        }),
      );
      this.employee.value.set(employee);
      this.saved.set(true);
    } catch (error) {
      this.saveError.set(problemMessage(error));
    } finally {
      this.saving.set(false);
    }
  }

  private edit(change: (skills: DraftSkill[]) => DraftSkill[]): void {
    this.draft.update(change);
    this.saved.set(false);
  }

  private find(name: string): DraftSkill | undefined {
    const key = name.trim().toLowerCase();
    return this.draft().find((s) => s.name.toLowerCase() === key);
  }
}
