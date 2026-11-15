import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, Router, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import type { Employee, EmployeePage, SkillPage } from '../api/models';
import { SkillCriteria } from './skill-criteria';
import { SkillSearch } from './skill-search';

const anna: Employee = {
  id: 1,
  employee_number: 'E-1001',
  first_name: 'Anna',
  last_name: 'Schmidt',
  email: 'anna.schmidt@example.com',
  department: null,
  job_title: null,
  location: null,
  hire_date: null,
  skills: [
    { skill: { id: 1, name: 'Python' }, level: 'expert' },
    { skill: { id: 2, name: 'Kubernetes' }, level: 'advanced' },
    { skill: { id: 3, name: 'Go' }, level: 'beginner' },
  ],
};

describe('SkillSearch', () => {
  let harness: RouterTestingHarness;
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'search', component: SkillSearch }], withComponentInputBinding()),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });

  afterEach(async () => {
    await settle();
    http.verify();
  });

  const view = () => harness.routeNativeElement as HTMLElement;

  async function settle(): Promise<void> {
    const none: SkillPage = { items: [], total: 0, page: 1, page_size: 10 };
    http
      .match((r) => r.url === '/api/v1/skills')
      .filter((r) => !r.cancelled)
      .forEach((r) => r.flush(none));
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  async function employeesRequest(): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      await settle();
      const [request] = http.match((r) => r.url === '/api/v1/employees');
      if (request) {
        return request;
      }
    }
    throw new Error('The employees were not requested');
  }

  function results(items: Employee[]): EmployeePage {
    return { items, total: items.length, page: 1, page_size: 20 };
  }

  it('lists everybody before a skill is added', async () => {
    // When
    await harness.navigateByUrl('/search');
    const request = await employeesRequest();

    // Then
    expect(request.request.params.has('skill')).toBe(false);

    // When
    request.flush(results([anna]));
    await settle();

    // Then
    expect(view().querySelector('h1')?.textContent).toBe('Find people by skill');
    expect(view().textContent).toContain('Schmidt, Anna');
  });

  it('searches with the criteria in the URL and highlights the matched skills', async () => {
    // When
    await harness.navigateByUrl('/search?skill=kubernetes:advanced&skill=python');
    const request = await employeesRequest();

    // Then
    expect(request.request.params.getAll('skill')).toEqual(['kubernetes:advanced', 'python']);

    // When
    request.flush(results([anna]));
    await settle();

    // Then
    expect(view().querySelector('h2')?.textContent).toBe('Employees');
    const badges = [...view().querySelectorAll('tbody si-badge')].map((badge) => [
      badge.textContent?.trim(),
      badge.classList.contains('faded'),
    ]);
    expect(badges).toEqual([
      ['Python · expert', false],
      ['Kubernetes · advanced', false],
      ['Go · beginner', true],
    ]);
  });

  it('puts changed criteria into the URL and starts again at the first page', async () => {
    // Given
    await harness.navigateByUrl('/search?skill=python&q=anna&page=3');
    (await employeesRequest()).flush(results([anna]));
    await settle();

    // When
    const criteria: SkillCriteria = harness.fixture.debugElement.query(
      By.directive(SkillCriteria),
    ).componentInstance;
    criteria.criteriaChange.emit([{ name: 'Python' }, { name: 'Go', level: 'expert' }]);
    const request = await employeesRequest();

    // Then
    expect(TestBed.inject(Router).url).toBe('/search?skill=Python&skill=Go:expert&q=anna');
    expect(request.request.params.get('page')).toBe('1');
    request.flush(results([]));
    await settle();
    expect(view().textContent).toContain('Try a lower minimum level or fewer skills.');
  });

  function criteriaEditor(): SkillCriteria {
    return harness.fixture.debugElement.query(By.directive(SkillCriteria)).componentInstance;
  }

  it('lists everybody when searching without criteria', async () => {
    // Given
    await harness.navigateByUrl('/search');
    await settle();

    // When
    criteriaEditor().criteriaChange.emit([]);
    const request = await employeesRequest();

    // Then
    expect(request.request.params.has('skill')).toBe(false);
    request.flush(results([anna]));
    await settle();
    expect(view().querySelector('tbody')?.textContent).toContain('Schmidt, Anna');
  });

  it('sends a request for every search, also when it repeats the current one', async () => {
    // Given
    await harness.navigateByUrl('/search?skill=python');
    (await employeesRequest()).flush(results([anna]));
    await settle();

    // When
    criteriaEditor().criteriaChange.emit([{ name: 'python' }]);
    (await employeesRequest()).flush(results([anna]));
    await settle();
    criteriaEditor().criteriaChange.emit([{ name: 'python' }]);
    const third = await employeesRequest();

    // Then
    expect(TestBed.inject(Router).url).toBe('/search?skill=python');
    expect(third.request.params.getAll('skill')).toEqual(['python']);
    third.flush(results([anna]));
  });

  it('starts again at the first page when an unchanged search is repeated', async () => {
    // Given
    await harness.navigateByUrl('/search?skill=python&page=3');
    (await employeesRequest()).flush(results([anna]));
    await settle();

    // When
    criteriaEditor().criteriaChange.emit([{ name: 'python' }]);
    const request = await employeesRequest();

    // Then
    expect(TestBed.inject(Router).url).toBe('/search?skill=python');
    expect(request.request.params.get('page')).toBe('1');
    request.flush(results([anna]));
  });

  it('lists everybody when the last criterion is removed and searched', async () => {
    // Given
    await harness.navigateByUrl('/search?skill=python');
    (await employeesRequest()).flush(results([anna]));
    await settle();

    // When
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove python"]')!.click();
    await settle();

    // Then
    expect(TestBed.inject(Router).url).toBe('/search?skill=python');

    // When
    view().querySelector<HTMLButtonElement>('app-skill-criteria button[type=submit]')!.click();
    const request = await employeesRequest();

    // Then
    expect(TestBed.inject(Router).url).toBe('/search');
    expect(request.request.params.has('skill')).toBe(false);
    request.flush(results([anna]));
    await settle();
    expect(view().querySelector('tbody')?.textContent).toContain('Schmidt, Anna');
  });
});
