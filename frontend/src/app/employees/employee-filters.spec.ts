import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import type { NamePage } from '../api/models';
import { EmployeeFilters, EmployeeFilterValues } from './employee-filters';

describe('EmployeeFilters', () => {
  let fixture: ComponentFixture<EmployeeFilters>;
  let http: HttpTestingController;
  let applied: EmployeeFilterValues[];

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(EmployeeFilters);
    fixture.componentRef.setInput('values', { department: ['Mobility'], location: [] });
    applied = [];
    fixture.componentInstance.valuesChange.subscribe((values) => applied.push(values));
    await settle();
  });

  afterEach(() => http.verify());

  const host = () => fixture.nativeElement as HTMLElement;
  const panel = () => host().querySelector('.filters-panel');
  const selects = () =>
    [...host().querySelectorAll('.filters-panel si-select')].map((s) =>
      s.textContent?.replace(/\s+/g, ' ').trim(),
    );

  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  async function toggle(): Promise<void> {
    host().querySelector('button')!.click();
    await settle();
  }

  async function click(label: string): Promise<void> {
    const button = [...host().querySelectorAll<HTMLButtonElement>('.filters-panel button')].find(
      (b) => b.textContent?.trim() === label,
    );
    button!.click();
    await settle();
  }

  // The select asks for its options 100ms after it opens.
  async function request(url: string): Promise<TestRequest> {
    for (const deadline = Date.now() + 1000; Date.now() < deadline;) {
      const [match] = http.match((r) => r.url === url);
      if (match) {
        return match;
      }
      await new Promise((resolve) => setTimeout(resolve, 20));
      TestBed.tick();
    }
    throw new Error(`No request to ${url}`);
  }

  function names(...items: string[]): NamePage {
    return {
      items: items.map((name, id) => ({ id, name })),
      total: items.length,
      page: 1,
      page_size: 100,
    };
  }

  it('counts the filters in effect on its button', async () => {
    // When
    fixture.componentRef.setInput('values', {
      department: ['Mobility'],
      location: ['Munich', 'Zug'],
    });
    await settle();

    // Then
    expect(host().querySelector('button')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'Filters 3',
    );
  });

  it('opens with the filters in effect and applies what was chosen', async () => {
    // When
    await toggle();

    // Then
    expect(selects()[0]).toContain('Mobility');

    // When
    await click('Clear');
    await click('Apply');

    // Then
    expect(applied).toEqual([{ department: [], location: [] }]);
    expect(panel()).toBeNull();
  });

  it('drops what was not applied when the panel opens again', async () => {
    // Given
    await toggle();
    await click('Clear');

    // When
    await toggle();
    await toggle();

    // Then
    expect(selects()[0]).toContain('Mobility');
    expect(applied).toEqual([]);
  });

  it('offers only the departments the API has', async () => {
    // Given
    await toggle();

    // When
    host().querySelector<HTMLElement>('.filters-panel si-select [role=combobox]')!.click();
    const all = await request('/api/v1/departments');

    // Then
    expect(all.request.params.toString()).toBe('page_size=100');

    // When
    all.flush(names('Healthineers', 'Mobility'));
    await settle();
    const healthineers = [...document.querySelectorAll<HTMLElement>('[role=option]')].find(
      (option) => option.textContent?.trim() === 'Healthineers',
    );
    healthineers!.click();
    await settle();
    await click('Apply');

    // Then
    expect(applied).toEqual([{ department: ['Mobility', 'Healthineers'], location: [] }]);
  });

  it('stays open on clicks beside it, so that what was chosen can still be applied', async () => {
    // Given
    await toggle();
    await click('Clear');

    // When
    document.body.click();
    await settle();

    // Then
    expect(panel()).not.toBeNull();
    expect(host().querySelector('button')?.getAttribute('aria-expanded')).toBe('true');
  });
});
