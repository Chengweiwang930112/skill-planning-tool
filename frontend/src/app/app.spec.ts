import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  it('shows the application name and the navigation', async () => {
    // Given
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });

    // When
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    // Then
    expect(host.querySelector('.application-name')?.textContent).toBe('Staff & Skill Planning');
    const links = [...host.querySelectorAll('si-header-navigation a')];
    expect(links.map((link) => [link.textContent?.trim(), link.getAttribute('href')])).toEqual([
      ['Employees', '/employees'],
      ['Skill search', '/search'],
      ['Skills', '/skills'],
      ['Import', '/imports'],
    ]);
  });
});
