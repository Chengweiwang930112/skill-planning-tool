import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, input, output, signal } from '@angular/core';
import {
  SelectItem,
  SelectOption,
  SelectOptionSource,
  SiSelectComponent,
  SiSelectLazyOptionsDirective,
  SiSelectMultiValueDirective,
} from '@siemens/element-ng/select';
import { map, Observable, of } from 'rxjs';
import type { NamePage } from '../api/models';

export interface EmployeeFilterValues {
  department: string[];
  location: string[];
}

/** Offers the names the API has, so that only those can be chosen. */
class NameOptions implements SelectOptionSource<string> {
  constructor(
    private readonly http: HttpClient,
    private readonly url: string,
  ) {}

  getAllOptions(): Observable<SelectItem<string>[]> {
    return this.find({ page_size: 100 });
  }

  getOptionsForSearch(search: string): Observable<SelectItem<string>[]> {
    return this.find({ q: search, page_size: 20 });
  }

  getOptionsForValues(values: string[]): Observable<SelectOption<string>[]> {
    return of(values.map(option));
  }

  private find(params: Record<string, string | number>): Observable<SelectItem<string>[]> {
    return this.http
      .get<NamePage>(this.url, { params })
      .pipe(map((page) => page.items.map((item) => option(item.name))));
  }
}

function option(name: string): SelectOption<string> {
  return { type: 'option', value: name, label: name };
}

/** A button that opens the department and location filters below it, in place rather
 * than as a popover: the dropdowns' own overlays would cover Apply there, and a click
 * beside them would close it. The filters apply with Apply. */
@Component({
  selector: 'app-employee-filters',
  imports: [SiSelectComponent, SiSelectLazyOptionsDirective, SiSelectMultiValueDirective],
  templateUrl: './employee-filters.html',
  styleUrl: './employee-filters.scss',
})
export class EmployeeFilters {
  /** The filters of the current results. */
  readonly values = input.required<EmployeeFilterValues>();
  readonly valuesChange = output<EmployeeFilterValues>();

  private readonly http = inject(HttpClient);

  protected readonly departments = new NameOptions(this.http, '/api/v1/departments');
  protected readonly locations = new NameOptions(this.http, '/api/v1/locations');
  protected readonly department = signal<string[]>([]);
  protected readonly location = signal<string[]>([]);
  protected readonly open = signal(false);
  protected readonly count = computed(
    () => this.values().department.length + this.values().location.length,
  );

  /** Every opening starts from the filters in effect, so that unapplied edits are dropped. */
  protected toggle(): void {
    if (!this.open()) {
      this.department.set(this.values().department);
      this.location.set(this.values().location);
    }
    this.open.update((open) => !open);
  }

  protected clear(): void {
    this.department.set([]);
    this.location.set([]);
  }

  protected apply(): void {
    this.valuesChange.emit({ department: this.department(), location: this.location() });
    this.open.set(false);
  }
}
