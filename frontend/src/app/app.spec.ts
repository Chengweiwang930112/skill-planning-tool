import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  it('links the application name to the home page and keeps data management under Manage', async () => {
    // Given
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    // When
    host.querySelector<HTMLButtonElement>('si-header-actions button')!.click();
    await fixture.whenStable();

    // Then
    const brand = host.querySelector('a.application-name');
    expect([brand?.textContent?.trim(), brand?.getAttribute('href')]).toEqual([
      'Staff & Skill Planning',
      '/employees',
    ]);
    const items = [...document.querySelectorAll('si-header-dropdown a')];
    expect(items.map((item) => [item.textContent?.trim(), item.getAttribute('href')])).toEqual([
      ['Skill catalogue', '/skills'],
      ['Import employees', '/imports'],
    ]);
  });
});
