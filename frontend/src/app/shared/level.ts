import type { BadgeType } from '@siemens/element-ng/badge';
import type { Level } from '../api/models';

export const LEVELS: readonly Level[] = ['beginner', 'intermediate', 'advanced', 'expert'];

export const LEVEL_BADGE: Record<Level, BadgeType> = {
  beginner: 'default',
  intermediate: 'info',
  advanced: 'success',
  expert: 'success-emphasis',
};
