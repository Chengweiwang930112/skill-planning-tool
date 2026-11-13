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
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import { SiSearchBarComponent } from '@siemens/element-ng/search-bar';
import type { Employee, EmployeePage } from '../api/models';
import { EmployeeList, PAGE_SIZE } from './employee-list';

const anna: Employee = {
  id: 1,
  employee_number: 'E-1001',
  first_name: 'Anna',
  last_name: 'Schmidt',
  email: 'anna.schmidt@example.com',
  department: 'Digital Industries',
  job_title: 'Senior Software Engineer',
  location: 'Munich',
  hire_date: '2019-04-01',
  skills: [
    { skill: { id: 2, name: 'Kubernetes' }, level: 'expert' },
    { skill: { id: 1, name: 'Python' }, level: 'beginner' },
  ],
};

function page(items: Employee[], total = items.length, current = 1): EmployeePage {
  return { items, total, page: current, page_size: PAGE_SIZE };
}

describe('EmployeeList', () => {
  let harness: RouterTestingHarness;
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter(
          [{ path: 'employees', component: EmployeeList }],
          withComponentInputBinding(),
        ),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });

  afterEach(() => http.verify());

  async function open(url: string): Promise<TestRequest> {
    await harness.navigateByUrl(url);
    return nextRequest();
  }

  /** Waits for the reactive request without waiting for stability, which needs its response. */
  async function nextRequest(): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      TestBed.tick();
      const [request] = http.match((r) => r.url === '/api/v1/employees');
      if (request) {
        return request;
      }
      await new Promise((resolve) => setTimeout(resolve));
    }
    throw new Error('No request to /api/v1/employees was made');
  }

  async function respond(request: TestRequest, body: EmployeePage): Promise<HTMLElement> {
    request.flush(body);
    await harness.fixture.whenStable();
    return harness.routeNativeElement as HTMLElement;
  }

  function currentUrl(): string {
    return TestBed.inject(Router).url;
  }

  it('requests the first page sorted by last name and renders the employees', async () => {
    const request = await open('/employees');

    expect(request.request.params.toString()).toBe('page=1&page_size=20&sort=last_name');
    const view = await respond(request, page([anna]));

    const [name, ...cells] = [...view.querySelectorAll('tbody td')].map((cell) =>
      cell.textContent?.trim(),
    );
    expect(name).toContain('Schmidt, Anna');
    expect(name).toContain('anna.schmidt@example.com');
    expect(cells.slice(0, 4)).toEqual([
      'E-1001',
      'Digital Industries',
      'Senior Software Engineer',
      'Munich',
    ]);
    const badges = [...view.querySelectorAll('si-badge')].map((b) => b.textContent?.trim());
    expect(badges).toEqual(['Kubernetes · expert', 'Python · beginner']);
    expect(view.textContent).toContain('1 employee');
  });

  it('passes the search, sorting and page from the URL to the API', async () => {
    const request = await open('/employees?q=anna&sort=-department&page=2');

    expect(request.request.params.toString()).toBe('page=2&page_size=20&sort=-department&q=anna');
    request.flush(page([anna], 21, 2));
  });

  it('sorts by a column and reverses the order on a second click', async () => {
    const view = await respond(await open('/employees'), page([anna]));
    const department = () =>
      [...view.querySelectorAll('th')].find((th) => th.textContent?.includes('Department'))!;
    expect(department().getAttribute('aria-sort')).toBe('none');

    department().querySelector('button')!.click();
    await respond(await nextRequest(), page([anna]));

    expect(currentUrl()).toBe('/employees?sort=department');
    expect(department().getAttribute('aria-sort')).toBe('ascending');

    department().querySelector('button')!.click();
    await respond(await nextRequest(), page([anna]));

    expect(currentUrl()).toBe('/employees?sort=-department');
    expect(department().getAttribute('aria-sort')).toBe('descending');
  });

  it('starts again at the first page when the search changes', async () => {
    await respond(await open('/employees?page=2'), page([anna], 21, 2));

    searchBar().searchChange.emit('schmidt');
    await respond(await nextRequest(), page([anna]));

    expect(currentUrl()).toBe('/employees?q=schmidt');
  });

  it('pages through the results only when there is more than one page', async () => {
    let view = await respond(await open('/employees'), page([anna]));
    expect(view.querySelector('si-pagination')).toBeNull();

    view = await respond(await open('/employees?sort=location'), page([anna], 45));
    paginator().currentPage.set(3);
    await respond(await nextRequest(), page([anna], 45, 3));

    expect(currentUrl()).toBe('/employees?sort=location&page=3');
    expect(view.querySelector('si-pagination')).not.toBeNull();
  });

  it('distinguishes an empty directory from a search without matches', async () => {
    const empty = await respond(await open('/employees'), page([]));
    expect(empty.textContent).toContain('No employees yet');
    expect(empty.querySelector('a[href="/imports"]')?.textContent).toBe('Import employees');

    const noMatch = await respond(await open('/employees?q=nobody'), page([]));
    expect(noMatch.textContent).toContain('No employees match your search');
    expect(noMatch.querySelector('a[href="/imports"]')).toBeNull();
  });

  it('shows the problem detail when loading fails and retries on request', async () => {
    const request = await open('/employees?sort=salary');
    request.flush(
      { title: 'Unprocessable Entity', status: 422, detail: 'Invalid request parameters' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await harness.fixture.whenStable();
    const view = harness.routeNativeElement as HTMLElement;
    expect(view.textContent).toContain('Invalid request parameters');

    view.querySelector<HTMLButtonElement>('button.btn-secondary')!.click();
    await respond(await nextRequest(), page([anna]));

    expect(view.textContent).toContain('Schmidt, Anna');
  });

  function searchBar(): SiSearchBarComponent {
    return harness.fixture.debugElement.query(By.directive(SiSearchBarComponent)).componentInstance;
  }

  function paginator(): SiPaginationComponent {
    return harness.fixture.debugElement.query(By.directive(SiPaginationComponent))
      .componentInstance;
  }
});
