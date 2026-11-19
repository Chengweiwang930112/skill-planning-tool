import { DatePipe } from '@angular/common';
import { HttpClient, HttpErrorResponse, httpResource } from '@angular/common/http';
import {
  Component,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { firstValueFrom } from 'rxjs';
import type { Employee, Level } from '../api/models';
import { problemMessage } from '../api/problem';
import { LEVELS } from '../shared/level';
import { SkillPicker, SkillPickerHint } from '../shared/skill-picker';

interface DraftSkill {
  id: number;
  name: string;
  level: Level;
}

function draftOf(employee: Employee): DraftSkill[] {
  return employee.skills.map(({ skill, level }) => ({ id: skill.id, name: skill.name, level }));
}

function sameSkills(a: DraftSkill[], b: DraftSkill[]): boolean {
  const key = (skills: DraftSkill[]) =>
    skills
      .map((s) => `${s.id}:${s.level}`)
      .sort()
      .join();
  return key(a) === key(b);
}

/** Skill edits change a draft; Save sends the whole draft in one request, for the version
 * of the employee it was made from, so that it cannot overwrite changes saved since. */
@Component({
  selector: 'app-employee-panel',
  imports: [
    DatePipe,
    FormsModule,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SkillPicker,
    SkillPickerHint,
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
  /** The version the draft is based on: as loaded, then as last saved. */
  private readonly version = linkedSignal(() => this.employee.headers()?.get('ETag') ?? '');
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
  /** Someone else saved changes since the employee was loaded. */
  protected readonly outdated = signal(false);

  protected readonly picker = viewChild(SkillPicker);
  protected readonly draftNames = computed(() => this.draft().map((s) => s.name));
  protected newLevel: Level = 'intermediate';

  constructor() {
    effect(() => {
      if (this.employee.hasValue()) {
        this.changed.emit(this.employee.value());
      }
    });
  }

  protected changeLevel(id: number, level: Level): void {
    this.edit((skills) => skills.map((s) => (s.id === id ? { ...s, level } : s)));
  }

  protected remove(id: number): void {
    this.edit((skills) => skills.filter((s) => s.id !== id));
  }

  protected add(): void {
    const picker = this.picker();
    if (!picker?.validate() || !picker.skill) {
      return;
    }
    const { id, name } = picker.skill;
    const level = this.newLevel;
    picker.clear();
    this.edit((skills) =>
      skills.some((s) => s.id === id)
        ? skills.map((s) => (s.id === id ? { ...s, level } : s))
        : [...skills, { id, name, level }],
    );
  }

  protected async save(): Promise<void> {
    this.saving.set(true);
    this.saveError.set(undefined);
    try {
      const response = await firstValueFrom(
        this.http.put<Employee>(
          `/api/v1/employees/${this.employeeId()}/skills`,
          { skills: this.draft().map(({ id, level }) => ({ skill_id: id, level })) },
          { headers: { 'If-Match': this.version() }, observe: 'response' },
        ),
      );
      this.employee.value.set(response.body!);
      this.version.set(response.headers.get('ETag') ?? '');
      this.saved.set(true);
    } catch (error) {
      this.outdated.set(error instanceof HttpErrorResponse && error.status === 412);
      this.saveError.set(problemMessage(error));
    } finally {
      this.saving.set(false);
    }
  }

  /** Drops the draft for the employee as stored now, with the changes saved since. */
  protected loadLatest(): void {
    this.outdated.set(false);
    this.saveError.set(undefined);
    this.employee.reload();
  }

  private edit(change: (skills: DraftSkill[]) => DraftSkill[]): void {
    this.draft.update(change);
    this.saved.set(false);
  }
}
