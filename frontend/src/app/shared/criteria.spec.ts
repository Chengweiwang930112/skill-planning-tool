import type { SkillAssignment } from '../api/models';
import { formatCriterion, matchesAny, parseCriterion } from './criteria';

describe('criteria', () => {
  it('reads and writes the API format', () => {
    // When / Then
    expect(parseCriterion('Kubernetes:Advanced')).toEqual({
      name: 'Kubernetes',
      level: 'advanced',
    });
    expect(parseCriterion(' Python ')).toEqual({ name: 'Python' });
    expect(formatCriterion({ name: 'Kubernetes', level: 'advanced' })).toBe('Kubernetes:advanced');
    expect(formatCriterion({ name: 'Python' })).toBe('Python');
  });

  it('keeps an unknown level as part of the value for the API to reject', () => {
    // When
    const criterion = parseCriterion('kubernetes:advnced');

    // Then
    expect(criterion).toEqual({ name: 'kubernetes:advnced' });
    expect(formatCriterion(criterion)).toBe('kubernetes:advnced');
  });

  it('matches a skill at the level or higher, ignoring case', () => {
    // Given
    const k8s = (level: SkillAssignment['level']): SkillAssignment => ({
      skill: { id: 1, name: 'Kubernetes' },
      level,
    });

    // When / Then
    expect(matchesAny(k8s('expert'), [{ name: 'kubernetes', level: 'advanced' }])).toBe(true);
    expect(matchesAny(k8s('advanced'), [{ name: 'kubernetes', level: 'advanced' }])).toBe(true);
    expect(matchesAny(k8s('intermediate'), [{ name: 'kubernetes', level: 'advanced' }])).toBe(
      false,
    );
    expect(matchesAny(k8s('beginner'), [{ name: 'Kubernetes' }])).toBe(true);
    expect(matchesAny(k8s('expert'), [{ name: 'Go' }])).toBe(false);
  });
});
