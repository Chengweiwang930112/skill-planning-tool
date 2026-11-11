import { TestBed } from '@angular/core/testing';
import { ButtonShowcase } from './button-showcase';

describe('ButtonShowcase', () => {
  it('disables every button when the switch is toggled', async () => {
    const fixture = TestBed.createComponent(ButtonShowcase);
    await fixture.whenStable();
    const host = fixture.nativeElement as HTMLElement;

    const buttons = [...host.querySelectorAll('button')];
    expect(buttons.length).toBeGreaterThan(0);
    expect(buttons.some((button) => button.disabled)).toBe(false);

    host.querySelector<HTMLInputElement>('#backdrop-switch')?.click();
    await fixture.whenStable();

    expect(buttons.every((button) => button.disabled)).toBe(true);
  });
});
