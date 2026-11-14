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
import { SiSidePanelComponent } from '@siemens/element-ng/side-panel';
import type { Employee, EmployeePage, SkillPage } from '../api/models';
import { EmployeeList, PAGE_SIZE } from './employee-list';
import { EmployeePanel } from './employee-panel';

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

  afterEach(() => {
    flushSuggestions();
    http.verify();
  });

  /** Answers the requests the panel's typeahead makes on its own. */
  function flushSuggestions(): void {
    const none: SkillPage = { items: [], total: 0, page: 1, page_size: 10 };
    http
      .match((r) => r.url === '/api/v1/skills')
      .filter((r) => !r.cancelled)
      .forEach((r) => r.flush(none));
  }

  async function settle(): Promise<void> {
    flushSuggestions();
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

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

  async function panelRequest(id: number): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      TestBed.tick();
      const [request] = http.match(`/api/v1/employees/${id}`);
      if (request) {
        return request;
      }
      await new Promise((resolve) => setTimeout(resolve));
    }
    throw new Error(`Employee ${id} was not requested`);
  }

  function sidePanel(): SiSidePanelComponent {
    return harness.fixture.debugElement.query(By.directive(SiSidePanelComponent)).componentInstance;
  }

  it('opens an employee in the side panel from the name', async () => {
    const view = await respond(await open('/employees?q=schmidt'), page([anna]));
    expect(sidePanel().collapsed()).toBe(true);

    view.querySelector<HTMLAnchorElement>('tbody a')!.click();
    (await panelRequest(1)).flush(anna);
    await settle();

    expect(currentUrl()).toBe('/employees?q=schmidt&employee=1');
    expect(sidePanel().collapsed()).toBe(false);
    expect(view.querySelector('app-employee-panel h2')?.textContent).toBe('Anna Schmidt');
  });

  it('opens an employee from anywhere in the row and highlights the row', async () => {
    const view = await respond(await open('/employees'), page([anna]));
    const row = view.querySelector('tbody tr')!;

    row.querySelectorAll('td')[2].click();
    (await panelRequest(1)).flush(anna);
    await settle();

    expect(currentUrl()).toBe('/employees?employee=1');
    expect(row.classList).toContain('table-active');
  });

  it('does not open the panel when the click ends a text selection', async () => {
    const view = await respond(await open('/employees'), page([anna]));
    const selection = vi
      .spyOn(window, 'getSelection')
      .mockReturnValue({ toString: () => 'anna' } as Selection);

    view.querySelectorAll<HTMLElement>('tbody td')[1].click();
    await settle();
    selection.mockRestore();

    expect(currentUrl()).toBe('/employees');
  });

  it('still shows the list when the panel loads first', async () => {
    await harness.navigateByUrl('/employees?employee=1');
    const list = await nextRequest();
    (await panelRequest(1)).flush(anna);
    await settle();

    const view = await respond(list, page([anna]));

    expect(view.querySelector('tbody')?.textContent).toContain('Schmidt, Anna');
  });

  it('shows edits made in the panel in the list', async () => {
    const list = await open('/employees?employee=1');
    (await panelRequest(1)).flush(anna);
    list.flush(page([anna]));
    await settle();
    const view = harness.routeNativeElement as HTMLElement;

    const panel: EmployeePanel = harness.fixture.debugElement.query(
      By.directive(EmployeePanel),
    ).componentInstance;
    panel.changed.emit({ ...anna, skills: [{ skill: { id: 9, name: 'Go' }, level: 'advanced' }] });
    panel.changed.emit({ ...anna, id: 42 });
    await settle();

    const badges = [...view.querySelectorAll('tbody si-badge')].map((b) => b.textContent?.trim());
    expect(badges).toEqual(['Go · advanced']);
  });

  it('closes the panel by removing the employee from the URL', async () => {
    const list = await open('/employees?employee=1&page=2');
    (await panelRequest(1)).flush(anna);
    list.flush(page([anna], 30, 2));
    await settle();

    sidePanel().closed.emit();
    await settle();

    expect(currentUrl()).toBe('/employees?page=2');
  });

  it('closes the panel when the panel asks to exit', async () => {
    const list = await open('/employees?employee=1');
    (await panelRequest(1)).flush(anna);
    list.flush(page([anna]));
    await settle();

    const panel: EmployeePanel = harness.fixture.debugElement.query(
      By.directive(EmployeePanel),
    ).componentInstance;
    panel.exit.emit();
    await settle();

    expect(currentUrl()).toBe('/employees');
  });

  function searchBar(): SiSearchBarComponent {
    return harness.fixture.debugElement.query(By.directive(SiSearchBarComponent)).componentInstance;
  }

  function paginator(): SiPaginationComponent {
    return harness.fixture.debugElement.query(By.directive(SiPaginationComponent))
      .componentInstance;
  }
});
