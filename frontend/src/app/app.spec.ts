import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  let host: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    host = fixture.nativeElement as HTMLElement;
  });

  it('renders the application name in the header', () => {
    const name = host.querySelector('si-application-header h1.application-name');

    expect(name?.textContent).toContain('Staff & Skill Planning Tool');
  });

  it('renders the employee card with an empty state', () => {
    const card = host.querySelector('si-card');

    expect(card?.textContent).toContain('Employees');
    expect(card?.querySelector('si-empty-state')?.textContent).toContain('No employees yet');
  });

  it('renders a badge per proficiency level', () => {
    const badges = [...host.querySelectorAll('si-badge')].map((b) => b.textContent?.trim());

    expect(badges).toEqual(['Beginner', 'Intermediate', 'Advanced', 'Expert']);
  });

  it('wires the account dropdown to its trigger and starts closed', () => {
    const trigger = host.querySelector('button[si-header-account-item]');

    expect(trigger?.getAttribute('aria-haspopup')).toBe('dialog');
    expect(trigger?.getAttribute('aria-expanded')).toBe('false');
  });
});
