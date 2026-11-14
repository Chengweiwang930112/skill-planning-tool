import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { firstValueFrom, Observable } from 'rxjs';
import type { Employee, SkillPage } from '../api/models';
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

describe('EmployeePanel', () => {
  let fixture: ComponentFixture<EmployeePanel>;
  let http: HttpTestingController;
  let changes: Employee[];
  let exits: number;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
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

  /** Answers the requests the typeahead makes on its own, e.g. as soon as it renders. */
  function flushSuggestions(): void {
    const none: SkillPage = { items: [], total: 0, page: 1, page_size: 10 };
    http
      .match((r) => r.url === '/api/v1/skills' && r.method === 'GET')
      .filter((r) => !r.cancelled)
      .forEach((r) => r.flush(none));
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
    const select = view().querySelector<HTMLSelectElement>('#new-level')!;
    select.value = level;
    select.dispatchEvent(new Event('change'));
    await settle();
    view().querySelector('form')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  it('shows the employee and reports it as stored', () => {
    expect(view().querySelector('h2')?.textContent).toBe('Anna Schmidt');
    expect(view().querySelector('dl')?.textContent).toContain('E-1001');
    expect(view().querySelector('dl')?.textContent).toContain('—');
    expect(shownSkills()).toEqual(['Kubernetes expert', 'Python beginner']);
    expect(changes).toEqual([anna]);
    expect(button('Save').disabled).toBe(true);
  });

  it('collects edits without sending them', async () => {
    await setLevel('Python', 'advanced');
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Kubernetes"]')!.click();
    await settle();
    await add('Terraform', 'expert');

    expect(shownSkills()).toEqual(['Python advanced', 'Terraform expert']);
    expect(status()).toBe('Unsaved changes');
    expect(button('Save').disabled).toBe(false);
    http.expectNone((r) => r.method !== 'GET');
    expect(changes).toEqual([anna]);
  });

  it('saves all edits in one request', async () => {
    await setLevel('Python', 'advanced');
    await add('  Apache   Kafka ', 'beginner');
    button('Save').click();
    await settle();

    expect(button('Saving…').disabled).toBe(true);
    const save = await request('PUT', '/api/v1/employees/1/skills');
    expect(save.request.body).toEqual({
      skills: [
        { name: 'Kubernetes', level: 'expert' },
        { name: 'Python', level: 'advanced' },
        { name: 'Apache Kafka', level: 'beginner' },
      ],
    });
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

    expect(changes.at(-1)).toEqual(stored);
    expect(status()).toBe('All changes saved');
    expect(button('Save').disabled).toBe(true);
  });

  it('keeps the draft when saving fails, so the user can retry', async () => {
    await setLevel('Python', 'expert');
    button('Save').click();

    (await request('PUT', '/api/v1/employees/1/skills')).flush(
      { title: 'Unprocessable Entity', status: 422, detail: 'Invalid request parameters' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await settle();

    expect(view().textContent).toContain('The changes were not saved.');
    expect(view().textContent).toContain('Invalid request parameters');
    expect(shownSkills()).toEqual(['Kubernetes expert', 'Python expert']);
    expect(button('Save').disabled).toBe(false);
  });

  it('sees no change once an edit is undone by hand', async () => {
    await setLevel('Python', 'expert');
    await setLevel('Python', 'beginner');

    expect(status()).toBe('');
    expect(button('Save').disabled).toBe(true);
  });

  it('changes the level when the added skill is already in the list', async () => {
    await add('KUBERNETES', 'beginner');

    expect(shownSkills()).toEqual(['Kubernetes beginner', 'Python beginner']);
  });

  it('asks to exit without saving anything', async () => {
    await setLevel('Python', 'expert');
    button('Exit').click();

    expect(exits).toBe(1);
    http.expectNone({ method: 'PUT', url: '/api/v1/employees/1/skills' });
  });

  it('suggests catalogue skills that are not in the list yet', async () => {
    const panel = fixture.componentInstance as unknown as {
      suggestions: (q: string) => Observable<string[]>;
    };
    const result = firstValueFrom(panel.suggestions('o'));

    const search = await request('GET', '/api/v1/skills', (params) => params.startsWith('q='));
    expect(search.request.params.toString()).toBe('q=o&page_size=10');
    search.flush({
      items: [
        { id: 3, name: 'Go' },
        { id: 1, name: 'Python' },
      ],
      total: 2,
      page: 1,
      page_size: 10,
    } satisfies SkillPage);

    expect(await result).toEqual(['Go']);
  });
});

describe('EmployeePanel without data', () => {
  it('shows why the employee could not be loaded', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(EmployeePanel);
    fixture.componentRef.setInput('employeeId', 99);
    TestBed.tick();

    http
      .expectOne('/api/v1/employees/99')
      .flush(
        { title: 'Not Found', status: 404, detail: 'Employee 99 does not exist' },
        { status: 404, statusText: 'Not Found' },
      );
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Employee 99 does not exist',
    );
  });
});
