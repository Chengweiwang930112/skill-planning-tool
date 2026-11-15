import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom, Observable } from 'rxjs';
import type { Skill, SkillPage } from '../api/models';
import { SkillPicker } from './skill-picker';

const CATALOGUE: Skill[] = [
  { id: 1, name: 'Go' },
  { id: 2, name: 'Google Cloud' },
  { id: 3, name: 'Python' },
];

interface PickerInternals {
  suggestions: (q: string) => Observable<Skill[]>;
  choose: (match: { option: { text: string; option: Skill } }) => void;
}

describe('SkillPicker', () => {
  let fixture: ComponentFixture<SkillPicker>;
  let http: HttpTestingController;
  let changes: (Skill | undefined)[];

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SkillPicker);
    changes = [];
    fixture.componentInstance.skillChange.subscribe((skill) => changes.push(skill));
    TestBed.tick();
  });

  const picker = () => fixture.componentInstance;
  const internals = () => picker() as unknown as PickerInternals;
  const view = () => fixture.nativeElement as HTMLElement;
  const hint = () => picker().hint() ?? '';

  afterEach(() => {
    answer();
    http.verify();
  });

  /** Answers searches like the API does: by part of the name. */
  function answer(): void {
    for (const request of http.match((r) => r.url === '/api/v1/skills')) {
      if (request.cancelled) {
        continue;
      }
      const q = (request.request.params.get('q') ?? '').toLowerCase();
      const items = CATALOGUE.filter((s) => s.name.toLowerCase().includes(q));
      request.flush({
        items: items.map((s) => ({ ...s, employee_count: 0 })),
        total: items.length,
        page: 1,
        page_size: 10,
      } satisfies SkillPage);
    }
  }

  async function type(text: string): Promise<void> {
    const input = view().querySelector('input')!;
    input.value = text;
    input.dispatchEvent(new Event('input'));
    for (let round = 0; round < 3; round++) {
      await new Promise((resolve) => setTimeout(resolve));
      TestBed.tick();
      answer();
    }
    TestBed.tick();
  }

  async function search(q: string): Promise<Skill[]> {
    const result = firstValueFrom(internals().suggestions(q));
    answer();
    return result;
  }

  function validate(): boolean {
    const valid = picker().validate();
    TestBed.tick();
    return valid;
  }

  it('suggests catalogue skills that are not excluded', async () => {
    // Given
    fixture.componentRef.setInput('exclude', ['go']);

    // When / Then
    expect(await search('go')).toEqual([{ id: 2, name: 'Google Cloud' }]);
  });

  it('has a skill once one is chosen from the suggestions', async () => {
    // Given
    await type('goo');

    // When
    internals().choose({
      option: { text: 'Google Cloud', option: { id: 2, name: 'Google Cloud' } },
    });

    // Then
    expect(picker().skill).toEqual({ id: 2, name: 'Google Cloud' });
    expect(validate()).toBe(true);
    expect(changes).toEqual([{ id: 2, name: 'Google Cloud' }]);
  });

  it('forgets the chosen skill when the text is changed', async () => {
    // Given
    internals().choose({ option: { text: 'Go', option: { id: 1, name: 'Go' } } });

    // When
    await type('Gol');

    // Then
    expect(picker().skill).toBeUndefined();
    expect(changes).toEqual([{ id: 1, name: 'Go' }, undefined]);
  });

  it('takes a typed name that is exactly a suggestion', async () => {
    // When
    await type('python');

    // Then
    expect(validate()).toBe(true);
    expect(picker().skill).toEqual({ id: 3, name: 'Python' });
    await fixture.whenStable();
    expect(view().querySelector('input')!.value).toBe('Python');
  });

  it('asks to choose when the typed text only partly matches', async () => {
    // When
    await type('goo');

    // Then
    expect(validate()).toBe(false);
    expect(hint()).toBe('Choose a skill from the suggestions.');
  });

  it('says when nothing in the catalogue matches and links to it', async () => {
    // When
    await type('Cobol');

    // Then
    expect(validate()).toBe(false);
    expect(hint()).toBe('“Cobol” is not in the skill catalogue.');
    expect(picker().notFound()).toBe(true);
  });

  it('says when every match is listed already', async () => {
    // Given
    fixture.componentRef.setInput('exclude', ['Python']);

    // When
    await type('pyth');

    // Then
    expect(validate()).toBe(false);
    expect(hint()).toBe('Every skill matching “pyth” is listed already.');
  });

  it('has nothing to explain while the input is empty', () => {
    // When / Then
    expect(validate()).toBe(false);
    expect(hint()).toBe('');
  });

  it('clears the text and the chosen skill', async () => {
    // Given
    internals().choose({ option: { text: 'Go', option: { id: 1, name: 'Go' } } });

    // When
    picker().clear();
    await fixture.whenStable();

    // Then
    expect(picker().skill).toBeUndefined();
    expect(picker().query).toBe('');
    expect(view().querySelector('input')!.value).toBe('');
  });
});
