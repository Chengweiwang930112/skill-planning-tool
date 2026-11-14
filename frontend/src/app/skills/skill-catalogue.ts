import { DecimalPipe } from '@angular/common';
import { HttpClient, httpResource } from '@angular/common/http';
import { Component, computed, inject, input, numberAttribute, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { SiActionDialogService } from '@siemens/element-ng/action-modal';
import { SiEmptyStateComponent } from '@siemens/element-ng/empty-state';
import { SiFileDropzoneComponent } from '@siemens/element-ng/file-uploader';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import { SiSearchBarComponent } from '@siemens/element-ng/search-bar';
import { firstValueFrom } from 'rxjs';
import type { Skill, SkillImportResult, SkillPage, SkillWithUsage } from '../api/models';
import { problemMessage } from '../api/problem';
import { MAX_UPLOAD_BYTES } from '../imports/import-page';

export const PAGE_SIZE = 20;

interface DroppedFile {
  file: File;
  status: string;
}

@Component({
  selector: 'app-skill-catalogue',
  imports: [
    DecimalPipe,
    FormsModule,
    RouterLink,
    SiEmptyStateComponent,
    SiFileDropzoneComponent,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SiPaginationComponent,
    SiSearchBarComponent,
  ],
  templateUrl: './skill-catalogue.html',
  styleUrl: './skill-catalogue.scss',
})
export class SkillCatalogue {
  readonly q = input<string>();
  readonly page = input(1, { transform: (value: unknown) => numberAttribute(value, 1) });

  private readonly http = inject(HttpClient);
  private readonly dialogs = inject(SiActionDialogService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly pageSize = PAGE_SIZE;
  protected readonly maxUploadBytes = MAX_UPLOAD_BYTES;
  protected readonly skills = httpResource<SkillPage>(() => {
    const q = this.q();
    return {
      url: '/api/v1/skills',
      params: { page: this.page(), page_size: PAGE_SIZE, ...(q ? { q } : {}) },
    };
  });
  protected readonly loadError = computed(() => {
    const error = this.skills.error();
    return error ? problemMessage(error) : undefined;
  });

  protected readonly newName = signal('');
  protected readonly adding = signal(false);
  protected readonly added = signal<Skill | undefined>(undefined);
  protected readonly addError = signal<string | undefined>(undefined);

  protected readonly editing = signal<number | undefined>(undefined);
  protected readonly editedName = signal('');
  protected readonly renaming = signal(false);
  protected readonly rowError = signal<{ id: number; message: string } | undefined>(undefined);

  protected readonly importing = signal<string | undefined>(undefined);
  protected readonly imported = signal<SkillImportResult | undefined>(undefined);
  protected readonly importError = signal<string | undefined>(undefined);

  protected async add(): Promise<void> {
    const name = this.newName().trim();
    if (!name) {
      return;
    }
    this.adding.set(true);
    this.added.set(undefined);
    this.addError.set(undefined);
    try {
      this.added.set(await firstValueFrom(this.http.post<Skill>('/api/v1/skills', { name })));
      this.newName.set('');
      this.skills.reload();
    } catch (error) {
      this.addError.set(problemMessage(error));
    } finally {
      this.adding.set(false);
    }
  }

  protected startRename(skill: SkillWithUsage): void {
    this.editing.set(skill.id);
    this.editedName.set(skill.name);
    this.rowError.set(undefined);
  }

  protected cancelRename(): void {
    this.editing.set(undefined);
    this.rowError.set(undefined);
  }

  protected async rename(skill: SkillWithUsage): Promise<void> {
    const name = this.editedName().trim();
    if (!name || name === skill.name) {
      this.cancelRename();
      return;
    }
    this.renaming.set(true);
    try {
      await firstValueFrom(this.http.patch<Skill>(`/api/v1/skills/${skill.id}`, { name }));
      this.cancelRename();
      this.skills.reload();
    } catch (error) {
      this.rowError.set({ id: skill.id, message: problemMessage(error) });
    } finally {
      this.renaming.set(false);
    }
  }

  protected async remove(skill: SkillWithUsage): Promise<void> {
    const answer = await firstValueFrom(
      this.dialogs.showActionDialog({
        type: 'delete-confirm',
        heading: 'Remove skill',
        message: `Remove ${skill.name} from the catalogue?`,
        deleteBtnName: 'Remove',
      }),
    );
    if (answer !== 'delete') {
      return;
    }
    this.rowError.set(undefined);
    try {
      await firstValueFrom(this.http.delete(`/api/v1/skills/${skill.id}`));
      this.skills.reload();
    } catch (error) {
      this.rowError.set({ id: skill.id, message: problemMessage(error) });
    }
  }

  protected async upload(files: DroppedFile[]): Promise<void> {
    const file = files.find((dropped) => dropped.status === 'added')?.file;
    if (!file) {
      return;
    }
    const body = new FormData();
    body.append('file', file, file.name);
    this.importing.set(file.name);
    this.imported.set(undefined);
    this.importError.set(undefined);
    try {
      this.imported.set(
        await firstValueFrom(this.http.post<SkillImportResult>('/api/v1/skills/import', body)),
      );
      this.skills.reload();
    } catch (error) {
      this.importError.set(problemMessage(error));
    } finally {
      this.importing.set(undefined);
    }
  }

  protected rejectFile(error: { errorText: string }): void {
    this.imported.set(undefined);
    this.importError.set(error.errorText);
  }

  protected importSummary(result: SkillImportResult): string {
    const skipped = result.row_errors.length;
    return (
      `${result.rows_created} added, ${result.rows_existing} already in the catalogue` +
      (skipped ? `, ${skipped} ${skipped === 1 ? 'row' : 'rows'} skipped.` : '.')
    );
  }

  protected search(q: string): void {
    this.navigate({ q: q || null, page: null });
  }

  protected goToPage(page: number): void {
    this.navigate({ page: page === 1 ? null : page });
  }

  private navigate(queryParams: Params): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge',
    });
  }
}
