import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import type { SkillPage } from '../api/models';
import { Criterion } from '../shared/criteria';
import { MAX_CRITERIA, SkillCriteria } from './skill-criteria';

const CATALOGUE = ['Apache Kafka', 'Go', 'Kubernetes', 'Python'];

describe('SkillCriteria', () => {
  let fixture: ComponentFixture<SkillCriteria>;
  let http: HttpTestingController;
  let searches: Criterion[][];

  async function render(criteria: Criterion[]): Promise<void> {
    fixture.componentRef.setInput('criteria', criteria);
    await settle();
  }

  async function settle(): Promise<void> {
    for (const request of http.match((r) => r.url === '/api/v1/skills')) {
      if (request.cancelled) {
        continue;
      }
      const q = (request.request.params.get('q') ?? '').toLowerCase();
      const names = CATALOGUE.filter((name) => name.toLowerCase().includes(q));
      request.flush({
        items: names.map((name, id) => ({ id, name, employee_count: 0 })),
        total: names.length,
        page: 1,
        page_size: 10,
      } satisfies SkillPage);
    }
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SkillCriteria);
    searches = [];
    fixture.componentInstance.criteriaChange.subscribe((criteria) => searches.push(criteria));
  });

  afterEach(async () => {
    await settle();
    http.verify();
  });

  const view = () => fixture.nativeElement as HTMLElement;
  const shownCriteria = () =>
    [...view().querySelectorAll('li')].map(
      (li) => `${li.querySelector('span')?.textContent} ${li.querySelector('select')?.value}`,
    );

  function button(label: string): HTMLButtonElement {
    return [...view().querySelectorAll<HTMLButtonElement>('form button')].find(
      (b) => b.textContent?.trim() === label,
    )!;
  }

  async function type(name: string, level: string): Promise<void> {
    const input = view().querySelector<HTMLInputElement>('#criterion-skill')!;
    input.value = name;
    input.dispatchEvent(new Event('input'));
    await settle();
    await settle();
    const select = view().querySelector<HTMLSelectElement>('#criterion-level')!;
    select.value = level;
    select.dispatchEvent(new Event('change'));
    await settle();
  }

  async function click(label: string): Promise<void> {
    button(label).click();
    await settle();
  }

  it('searches for a typed catalogue skill with one click, at advanced by default', async () => {
    // Given
    await render([]);

    // When
    await type('apache kafka', 'advanced');
    await click('Search');

    // Then
    expect(searches).toEqual([[{ name: 'Apache Kafka', level: 'advanced' }]]);
  });

  it('can always search, also with nothing changed or nothing entered', async () => {
    // Given
    await render([]);
    expect(button('Search').disabled).toBe(false);

    // When
    await click('Search');

    await render([{ name: 'Python' }]);
    await click('Search');
    await click('Search');

    // Then
    expect(searches).toEqual([[], [{ name: 'Python' }], [{ name: 'Python' }]]);
  });

  it('searches with Enter too', async () => {
    // Given
    await render([]);
    await type('Go', '');

    // When
    view().querySelector('form')!.dispatchEvent(new Event('submit'));
    await settle();

    // Then
    expect(searches).toEqual([[{ name: 'Go' }]]);
  });

  it('collects several skills and searches for them together', async () => {
    // Given
    await render([]);

    // When
    await type('Kubernetes', 'advanced');
    await click('Add skill');
    await type('Python', '');
    await click('Add skill');
    await type('kubernetes', 'expert');
    await click('Add skill');

    // Then
    expect(shownCriteria()).toEqual(['Kubernetes advanced', 'Python ']);
    expect(searches).toEqual([]);

    // When
    await click('Search');

    // Then
    expect(searches).toEqual([[{ name: 'Kubernetes', level: 'advanced' }, { name: 'Python' }]]);
  });

  it('changes or removes criteria in the draft until the next search', async () => {
    // Given
    await render([{ name: 'Kubernetes', level: 'advanced' }, { name: 'Python' }, { name: 'Go' }]);
    const levels = view().querySelectorAll<HTMLSelectElement>('li select');

    // When
    levels[1].value = 'expert';
    levels[1].dispatchEvent(new Event('change'));
    levels[0].value = '';
    levels[0].dispatchEvent(new Event('change'));
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Go"]')!.click();
    await settle();

    // Then
    expect(searches).toEqual([]);
    expect(shownCriteria()).toEqual(['Kubernetes ', 'Python expert']);
    expect(view().textContent).toContain('Press Search to update the results.');

    // When
    await click('Search');

    // Then
    expect(searches).toEqual([[{ name: 'Kubernetes' }, { name: 'Python', level: 'expert' }]]);
  });

  it('starts over from the criteria of new results', async () => {
    // Given
    await render([{ name: 'Python' }]);
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Python"]')!.click();
    await settle();

    // When
    await render([{ name: 'Go', level: 'expert' }]);

    // Then
    expect(shownCriteria()).toEqual(['Go expert']);
    expect(view().textContent).not.toContain('Press Search');
  });

  it('accepts no more criteria than the API does', async () => {
    // When
    await render(Array.from({ length: MAX_CRITERIA }, (_, i) => ({ name: `Skill ${i}` })));

    // Then
    expect(view().querySelector<HTMLInputElement>('#criterion-skill')!.disabled).toBe(true);
    expect(button('Add skill').disabled).toBe(true);
    expect(view().textContent).toContain('At most 10 skills per search.');
  });

  it('never searches for a skill that is not in the catalogue', async () => {
    // Given
    await render([{ name: 'Python' }]);

    // When
    await type('Cobol', '');
    await click('Search');
    await click('Add skill');

    // Then
    expect(searches).toEqual([]);
    expect(shownCriteria()).toEqual(['Python ']);
    expect(view().querySelector('[role=alert]')?.textContent).toContain(
      '“Cobol” is not in the skill catalogue.',
    );
    expect(view().querySelector('[role=alert] a')?.getAttribute('href')).toBe('/skills');
  });

  it('asks to choose a suggestion for partly typed names', async () => {
    // Given
    await render([]);

    // When
    await type('kube', '');
    await click('Search');

    // Then
    expect(searches).toEqual([]);
    expect(view().querySelector('[role=alert]')?.textContent).toContain(
      'Choose a skill from the suggestions.',
    );
  });
});
