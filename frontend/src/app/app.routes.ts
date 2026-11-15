import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'employees' },
  {
    path: 'employees',
    title: 'Find people · Staff & Skill Planning',
    loadComponent: () => import('./search/skill-search').then((m) => m.SkillSearch),
  },
  // The skill search used to be a page of its own; old links keep their criteria.
  { path: 'search', redirectTo: 'employees' },
  {
    path: 'skills',
    title: 'Skills · Staff & Skill Planning',
    loadComponent: () => import('./skills/skill-catalogue').then((m) => m.SkillCatalogue),
  },
  {
    path: 'imports',
    title: 'Import · Staff & Skill Planning',
    loadComponent: () => import('./imports/import-page').then((m) => m.ImportPage),
  },
  {
    path: 'imports/:id',
    title: 'Import report · Staff & Skill Planning',
    loadComponent: () => import('./imports/import-detail').then((m) => m.ImportDetail),
  },
  { path: '**', redirectTo: 'employees' },
];
