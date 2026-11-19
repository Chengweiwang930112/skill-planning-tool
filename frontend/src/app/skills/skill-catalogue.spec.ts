import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SiActionDialogService } from '@siemens/element-ng/action-modal';
import { of } from 'rxjs';
import type { SkillPage, SkillWithUsage } from '../api/models';
import { PAGE_SIZE, SkillCatalogue } from './skill-catalogue';

const GO: SkillWithUsage = { id: 1, name: 'Go', employee_count: 0 };
const PYTHON: SkillWithUsage = { id: 2, name: 'Python', employee_count: 12 };

function page(items: SkillWithUsage[], total = items.length): SkillPage {
  return { items, total, page: 1, page_size: PAGE_SIZE };
}

describe('SkillCatalogue', () => {
  let fixture: ComponentFixture<SkillCatalogue>;
  let http: HttpTestingController;
  let answer: 'delete' | 'cancel';
  let dialogs: unknown[];

  beforeEach(async () => {
    answer = 'delete';
    dialogs = [];
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: SiActionDialogService,
          useValue: {
            showActionDialog: (dialog: unknown) => {
              dialogs.push(dialog);
              return of(answer);
            },
          },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SkillCatalogue);
    (await list()).flush(page([GO, PYTHON]));
    await settle();
  });

  afterEach(() => http.verify());

  const view = () => fixture.nativeElement as HTMLElement;
  const rows = () =>
    [...view().querySelectorAll('tbody tr')].map((tr) =>
      [...tr.querySelectorAll('td')]
        .slice(0, 2)
        .map((td) => td.textContent?.trim())
        .join(' | '),
    );
  const alert = () => view().querySelector('[role=alert]')?.textContent?.trim();
  const button = (label: string) =>
    view().querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!;

  async function list(): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      TestBed.tick();
      const [request] = http.match((r) => r.url === '/api/v1/skills' && r.method === 'GET');
      if (request) {
        return request;
      }
      await new Promise((resolve) => setTimeout(resolve));
    }
    throw new Error('The skills were not requested');
  }

  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  async function enter(input: HTMLInputElement, value: string): Promise<void> {
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await settle();
    input.form!.dispatchEvent(new Event('submit'));
    await settle();
  }

  const conflict = (detail: string) =>
    [
      { title: 'Conflict', status: 409, detail },
      { status: 409, statusText: 'Conflict' },
    ] as const;

  it('lists the skills with how many employees have them', () => {
    // Then
    expect(rows()).toEqual(['Go | 0', 'Python | 12']);
    expect(view().querySelector('tbody a')?.getAttribute('href')).toBe('/employees?skill=Python');
  });

  it('adds a skill and lists it', async () => {
    // When
    await enter(view().querySelector('#new-skill-name')!, ' Rust ');

    // Then
    const create = http.expectOne({ method: 'POST', url: '/api/v1/skills' });
    expect(create.request.body).toEqual({ name: 'Rust' });

    // When
    create.flush({ id: 3, name: 'Rust' });
    await settle();

    // Then
    expect(view().textContent).toContain('Added Rust.');
    (await list()).flush(page([GO, PYTHON, { id: 3, name: 'Rust', employee_count: 0 }]));
    await settle();
    expect(rows()).toHaveLength(3);
  });

  it('explains why a skill was not added', async () => {
    // Given
    await enter(view().querySelector('#new-skill-name')!, 'python');

    // When
    http
      .expectOne({ method: 'POST', url: '/api/v1/skills' })
      .flush(...conflict('The catalogue already has Python (skill 2)'));
    await settle();

    // Then
    expect(view().textContent).toContain('The skill was not added.');
    expect(view().textContent).toContain('The catalogue already has Python (skill 2)');
  });

  it('renames a skill in place', async () => {
    // When
    button('Rename Go').click();
    await settle();
    await enter(view().querySelector('input[aria-label="New name for Go"]')!, 'Golang');

    // Then
    const rename = http.expectOne({ method: 'PATCH', url: '/api/v1/skills/1' });
    expect(rename.request.body).toEqual({ name: 'Golang' });

    // When
    rename.flush({ id: 1, name: 'Golang' });
    await settle();

    // Then
    (await list()).flush(page([{ ...GO, name: 'Golang' }, PYTHON]));
    await settle();
    expect(rows()).toEqual(['Golang | 0', 'Python | 12']);
  });

  it('keeps the new name when renaming fails', async () => {
    // Given
    button('Rename Go').click();
    await settle();
    const input = view().querySelector<HTMLInputElement>('input[aria-label="New name for Go"]')!;
    await enter(input, 'python');

    // When
    http
      .expectOne({ method: 'PATCH', url: '/api/v1/skills/1' })
      .flush(...conflict('The catalogue already has Python (skill 2)'));
    await settle();

    // Then
    expect(alert()).toBe('The catalogue already has Python (skill 2)');
    expect(input.value).toBe('python');
  });

  it('removes a skill nobody has after confirming', async () => {
    // When
    button('Remove Go').click();
    await settle();

    // Then
    expect(dialogs).toEqual([expect.objectContaining({ type: 'delete-confirm' })]);
    http.expectOne({ method: 'DELETE', url: '/api/v1/skills/1' }).flush(null);
    await settle();
    (await list()).flush(page([PYTHON]));
    await settle();
    expect(rows()).toEqual(['Python | 12']);
  });

  it('removes nothing when the removal is cancelled', async () => {
    // Given
    answer = 'cancel';

    // When
    button('Remove Go').click();
    await settle();

    // Then
    http.expectNone({ method: 'DELETE' });
  });

  it('cannot remove a skill that employees have', () => {
    // Then
    expect(button('Remove Python').disabled).toBe(true);
  });

  it('says when no skill matches the search', async () => {
    // When
    fixture.componentRef.setInput('q', 'cobol');
    (await list()).flush(page([]));
    await settle();

    // Then
    expect(view().textContent).toContain('No skills match your search');
  });
});
