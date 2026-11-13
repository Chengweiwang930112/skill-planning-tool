import type { BadgeType } from '@siemens/element-ng/badge';
import type { StatusType } from '@siemens/element-ng/common';
import type { ImportStatus } from '../api/models';

export const IMPORT_STATUS: Record<
  ImportStatus,
  { label: string; badge: BadgeType; severity: StatusType }
> = {
  succeeded: { label: 'Succeeded', badge: 'success', severity: 'success' },
  partially_succeeded: { label: 'Partially succeeded', badge: 'warning', severity: 'warning' },
  failed: { label: 'Failed', badge: 'danger', severity: 'danger' },
};
