import type { Level, SkillAssignment } from '../api/models';
import { LEVELS } from './level';

/** A skill search criterion: the skill at `level` or higher, or at any level without one. */
export interface Criterion {
  name: string;
  level?: Level;
}

/** Reads the `name:level` format the API's `skill` parameter uses. */
export function parseCriterion(value: string): Criterion {
  const separator = value.lastIndexOf(':');
  const level = value.slice(separator + 1).toLowerCase() as Level;
  if (separator >= 0 && LEVELS.includes(level)) {
    return { name: value.slice(0, separator).trim(), level };
  }
  // An unknown level stays part of the value, so the API rejects it instead of it
  // silently matching nobody.
  return { name: value.trim() };
}

export function formatCriterion({ name, level }: Criterion): string {
  return level ? `${name}:${level}` : name;
}

export function matchesAny(assignment: SkillAssignment, criteria: Criterion[]): boolean {
  return criteria.some(
    ({ name, level }) =>
      name.toLowerCase() === assignment.skill.name.toLowerCase() &&
      (!level || LEVELS.indexOf(assignment.level) >= LEVELS.indexOf(level)),
  );
}
