import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { firstValueFrom, Observable } from 'rxjs';
import type { SkillPage } from '../api/models';
import { Criterion } from '../shared/criteria';
import { MAX_CRITERIA, SkillCriteria } from './skill-criteria';

describe('SkillCriteria', () => {
  let fixture: ComponentFixture<SkillCriteria>;
  let http: HttpTestingController;
  let searches: Criterion[][];

  async function render(criteria: Criterion[]): Promise<void> {
    fixture.componentRef.setInput('criteria', criteria);
    await settle();
  }

  async function settle(): Promise<void> {
    const none: SkillPage = { items: [], total: 0, page: 1, page_size: 10 };
    http
      .match((r) => r.url === '/api/v1/skills')
      .filter((r) => !r.cancelled)
      .forEach((r) => r.flush(none));
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
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
    const select = view().querySelector<HTMLSelectElement>('#criterion-level')!;
    select.value = level;
    select.dispatchEvent(new Event('change'));
    await settle();
  }

  async function click(label: string): Promise<void> {
    button(label).click();
    await settle();
  }

  it('searches for a typed skill with one click, at advanced or higher by default', async () => {
    await render([]);

    await type('  Apache   Kafka ', 'advanced');
    await click('Search');

    expect(searches).toEqual([[{ name: 'Apache Kafka', level: 'advanced' }]]);
  });

  it('can always search, also with nothing changed or nothing entered', async () => {
    await render([]);
    expect(button('Search').disabled).toBe(false);
    await click('Search');

    await render([{ name: 'Python' }]);
    await click('Search');
    await click('Search');

    expect(searches).toEqual([[], [{ name: 'Python' }], [{ name: 'Python' }]]);
  });

  it('searches with Enter too', async () => {
    await render([]);
    await type('Go', '');

    view().querySelector('form')!.dispatchEvent(new Event('submit'));
    await settle();

    expect(searches).toEqual([[{ name: 'Go' }]]);
  });

  it('collects several skills and searches for them together', async () => {
    await render([]);

    await type('Kubernetes', 'advanced');
    await click('Add skill');
    await type('Python', '');
    await click('Add skill');
    await type('kubernetes', 'expert');
    await click('Add skill');

    expect(shownCriteria()).toEqual(['Kubernetes advanced', 'Python ']);
    expect(searches).toEqual([]);
    await click('Search');
    expect(searches).toEqual([[{ name: 'Kubernetes', level: 'advanced' }, { name: 'Python' }]]);
  });

  it('changes or removes criteria in the draft until the next search', async () => {
    await render([{ name: 'Kubernetes', level: 'advanced' }, { name: 'Python' }, { name: 'Go' }]);
    const levels = view().querySelectorAll<HTMLSelectElement>('li select');

    levels[1].value = 'expert';
    levels[1].dispatchEvent(new Event('change'));
    levels[0].value = '';
    levels[0].dispatchEvent(new Event('change'));
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Go"]')!.click();
    await settle();

    expect(searches).toEqual([]);
    expect(shownCriteria()).toEqual(['Kubernetes ', 'Python expert']);
    expect(view().textContent).toContain('Press Search to update the results.');
    await click('Search');
    expect(searches).toEqual([[{ name: 'Kubernetes' }, { name: 'Python', level: 'expert' }]]);
  });

  it('starts over from the criteria of new results', async () => {
    await render([{ name: 'Python' }]);
    view().querySelector<HTMLButtonElement>('button[aria-label="Remove Python"]')!.click();
    await settle();

    await render([{ name: 'Go', level: 'expert' }]);

    expect(shownCriteria()).toEqual(['Go expert']);
    expect(view().textContent).not.toContain('Press Search');
  });

  it('accepts no more criteria than the API does', async () => {
    await render(Array.from({ length: MAX_CRITERIA }, (_, i) => ({ name: `Skill ${i}` })));

    expect(view().querySelector<HTMLInputElement>('#criterion-skill')!.disabled).toBe(true);
    expect(button('Add skill').disabled).toBe(true);
    expect(view().textContent).toContain('At most 10 skills per search.');
  });

  it('suggests catalogue skills that are not listed yet', async () => {
    await render([{ name: 'Python' }]);
    const component = fixture.componentInstance as unknown as {
      suggestions: (q: string) => Observable<string[]>;
    };
    const result = firstValueFrom(component.suggestions('o'));

    http
      .expectOne((r) => r.url === '/api/v1/skills' && r.params.get('q') === 'o')
      .flush({
        items: [
          { id: 1, name: 'Go' },
          { id: 2, name: 'python' },
        ],
        total: 2,
        page: 1,
        page_size: 10,
      } satisfies SkillPage);

    expect(await result).toEqual(['Go']);
  });
});
