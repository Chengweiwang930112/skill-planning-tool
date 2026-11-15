import { DestroyRef, Directive, ElementRef, inject, output } from '@angular/core';

/** Reports whether the element's content is taller than the element, whenever that changes. */
@Directive({ selector: '[appOverflow]' })
export class Overflow {
  readonly overflowChange = output<boolean>();

  constructor() {
    const element = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    let overflowing = false;
    const check = (): void => {
      const now = element.scrollHeight > element.clientHeight + 1;
      if (now !== overflowing) {
        overflowing = now;
        this.overflowChange.emit(now);
      }
    };
    // A resize covers a narrower window; a mutation, other content at the same size.
    const resizes = new ResizeObserver(check);
    const mutations = new MutationObserver(check);
    resizes.observe(element);
    mutations.observe(element, { childList: true, subtree: true, characterData: true });
    inject(DestroyRef).onDestroy(() => {
      resizes.disconnect();
      mutations.disconnect();
    });
  }
}
