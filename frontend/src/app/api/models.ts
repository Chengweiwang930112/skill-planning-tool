import type { components, operations } from './schema';

type Schemas = components['schemas'];

export type Employee = Schemas['EmployeeRead'];
export type EmployeePage = Schemas['Page_EmployeeRead_'];
export type SkillAssignment = Schemas['SkillAssignmentRead'];
export type Level = SkillAssignment['level'];
export type ProblemDetail = Schemas['ProblemDetail'];

export type EmployeeQuery = NonNullable<
  operations['list_employees_api_v1_employees_get']['parameters']['query']
>;
export type EmployeeSort = NonNullable<EmployeeQuery['sort']>;
