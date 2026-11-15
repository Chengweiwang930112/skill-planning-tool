import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import type { Employee, Skill, SkillPage } from '../api/models';
import { EmployeePanel } from './employee-panel';

const anna: Employee = {
  id: 1,
  employee_number: 'E-1001',
  first_name: 'Anna',
  last_name: 'Schmidt',
  email: 'anna.schmidt@example.com',
  department: 'Digital Industries',
  job_title: 'Senior Software Engineer',
  location: null,
  hire_date: '2019-04-01',
  skills: [
    { skill: { id: 2, name: 'Kubernetes' }, level: 'expert' },
    { skill: { id: 1, name: 'Python' }, level: 'beginner' },
  ],
};

const CATALOGUE: Skill[] = [
  { id: 9, name: 'Apache Kafka' },
  { id: 2, name: 'Kubernetes' },
  { id: 1, name: 'Python' },
  { id: 5, name: 'Terraform' },
];

describe('EmployeePanel', () => {
  let fixture: ComponentFixture<EmployeePanel>;
  let http: HttpTestingController;
  let changes: Employee[];
  let exits: number;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(EmployeePanel);
    fixture.componentRef.setInput('employeeId', 1);
    changes = [];
    exits = 0;
    fixture.componentInstance.changed.subscribe((employee) => changes.push(employee));
    fixture.componentInstance.exit.subscribe(() => exits++);
    (await request('GET', '/api/v1/employees/1')).flush(anna);
    await settle();
  });

  afterEach(() => {
    flushSuggestions();
    http.verify();
  });

  const view = () => fixture.nativeElement as HTMLElement;

  /** Answers the typeahead's searches like the API does: by part of the name. */
  function flushSuggestions(): void {
    for (const request of http.match((r) => r.url === '/api/v1/skills' && r.method === 'GET')) {
      if (request.cancelled) {
        continue;
      }
      const q = (request.request.params.get('q') ?? '').toLowerCase();
      const items = CATALOGUE.filter((skill) => skill.name.toLowerCase().includes(q));
      request.flush({
        items: items.map((skill) => ({ ...skill, employee_count: 1 })),
        total: items.length,
        page: 1,
        page_size: 10,
      } satisfies SkillPage);
    }
  }

  /** Waits for a request without awaiting stability, which would need its response. */
  async function request(
    method: string,
    url: string,
    accept: (params: string) => boolean = () => true,
  ): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      TestBed.tick();
      const [match] = http.match(
        (r) => r.method === method && r.url === url && accept(r.params.toString()),
      );
      if (match) {
        return match;
      }
      await new Promise((resolve) => setTimeout(resolve));
    }
    throw new Error(`No ${method} ${url}`);
  }

  async function settle(): Promise<void> {
    flushSuggestions();
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  function shownSkills(): string[] {
    return [...view().querySelectorAll('li')].map(
      (li) => `${li.querySelector('span')?.textContent} ${li.querySelector('select')?.value}`,
    );
  }

  function button(label: string): HTMLButtonElement {
    return [...view().querySelectorAll<HTMLButtonElement>('footer button')].find(
      (b) => b.textContent?.trim() === label,
    )!;
  }

  function status(): string {
    return view().querySelector('footer [role=status]')?.textContent?.trim() ?? '';
  }

  async function setLevel(name: string, level: string): Promise<void> {
    const select = view().querySelector<HTMLSelectElement>(
      `select[aria-label="Level of ${name}"]`,
    )!;
    select.value = level;
    select.dispatchEvent(new Event('change'));
    await settle();
  }

  async function add(name: string, level: string): Promise<void> {
    const input = view().querySelector<HTMLInputElement>('#new-skill')!;
    input.value = name;
    input.dispatchEvent(new Event('input'));
    await settle();
    await settle();
    const select = view().querySelector<HTMLSelectElement>('#new-level')!;
    select.value = level;
    select.dispatchEvent(new Event('change'));
    await settle();
    view().querySelector('form')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  it('shows the employee and reports it as stored', () => {
    // Then
    expect(view().querySelector('h2')?.textContent).toBe('Anna Schmidt');
    expect(view().querySelector('dl')?.textContent).toContain('E-1001');
    expect(view().querySelector('dl')?.textContent).toContain('—');
    expect(shownSkills()).toEqual(['Kubernetes expert', 'Python beginner']);
    expect(changes).toEqual([anna]);
    expect(button('Save').disabled).toBe(true);
  });

  it('collects edits without sending them', async () => {
    // When
    await setLevel('Python', 'advanced');
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Kubernetes"]')!.click();
    await settle();
    await add('Terraform', 'expert');

    // Then
    expect(shownSkills()).toEqual(['Python advanced', 'Terraform expert']);
    expect(status()).toBe('Unsaved changes');
    expect(button('Save').disabled).toBe(false);
    http.expectNone((r) => r.method !== 'GET');
    expect(changes).toEqual([anna]);
  });

  it('saves all edits in one request', async () => {
    // Given
    await setLevel('Python', 'advanced');
    await add('apache kafka', 'beginner');

    // When
    button('Save').click();
    await settle();

    // Then
    expect(button('Saving…').disabled).toBe(true);
    const save = await request('PUT', '/api/v1/employees/1/skills');
    expect(save.request.body).toEqual({
      skills: [
        { skill_id: 2, level: 'expert' },
        { skill_id: 1, level: 'advanced' },
        { skill_id: 9, level: 'beginner' },
      ],
    });

    // When
    const stored: Employee = {
      ...anna,
      skills: [
        { skill: { id: 2, name: 'Kubernetes' }, level: 'expert' },
        { skill: { id: 1, name: 'Python' }, level: 'advanced' },
        { skill: { id: 9, name: 'Apache Kafka' }, level: 'beginner' },
      ],
    };
    save.flush(stored);
    await settle();

    // Then
    expect(changes.at(-1)).toEqual(stored);
    expect(status()).toBe('All changes saved');
    expect(button('Save').disabled).toBe(true);
  });

  it('keeps the draft when saving fails, so the user can retry', async () => {
    // Given
    await setLevel('Python', 'expert');

    // When
    button('Save').click();

    (await request('PUT', '/api/v1/employees/1/skills')).flush(
      { title: 'Unprocessable Entity', status: 422, detail: 'Invalid request parameters' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await settle();

    // Then
    expect(view().textContent).toContain('The changes were not saved.');
    expect(view().textContent).toContain('Invalid request parameters');
    expect(shownSkills()).toEqual(['Kubernetes expert', 'Python expert']);
    expect(button('Save').disabled).toBe(false);
  });

  it('sees no change once an edit is undone by hand', async () => {
    // Given
    await setLevel('Python', 'expert');

    // When
    await setLevel('Python', 'beginner');

    // Then
    expect(status()).toBe('');
    expect(button('Save').disabled).toBe(true);
  });

  it('changes the level when the added skill is already in the list', async () => {
    // When
    await add('KUBERNETES', 'beginner');

    // Then
    expect(shownSkills()).toEqual(['Kubernetes beginner', 'Python beginner']);
  });

  it('asks to exit without saving anything', async () => {
    // Given
    await setLevel('Python', 'expert');

    // When
    button('Exit').click();

    // Then
    expect(exits).toBe(1);
    http.expectNone({ method: 'PUT', url: '/api/v1/employees/1/skills' });
  });

  it('only adds skills from the catalogue', async () => {
    // When
    await add('Cobol', 'expert');

    // Then
    expect(view().querySelector('[role=alert]')?.textContent).toContain(
      '“Cobol” is not in the skill catalogue.',
    );
    expect(shownSkills()).toEqual(['Kubernetes expert', 'Python beginner']);
    expect(button('Save').disabled).toBe(true);
  });
});

describe('EmployeePanel without data', () => {
  it('shows why the employee could not be loaded', async () => {
    // Given
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(EmployeePanel);
    fixture.componentRef.setInput('employeeId', 99);
    TestBed.tick();

    // When
    http
      .expectOne('/api/v1/employees/99')
      .flush(
        { title: 'Not Found', status: 404, detail: 'Employee 99 does not exist' },
        { status: 404, statusText: 'Not Found' },
      );
    await fixture.whenStable();

    // Then
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Employee 99 does not exist',
    );
  });
});
