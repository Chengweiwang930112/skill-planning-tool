import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'employees' },
  {
    path: 'employees',
    title: 'Employees · Staff & Skill Planning',
    loadComponent: () => import('./employees/employee-list').then((m) => m.EmployeeList),
  },
  {
    path: 'search',
    title: 'Skill search · Staff & Skill Planning',
    loadComponent: () => import('./search/skill-search').then((m) => m.SkillSearch),
  },
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
