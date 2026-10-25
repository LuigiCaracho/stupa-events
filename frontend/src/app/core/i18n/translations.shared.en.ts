/** English strings of the shared blocks and the status mapping: the same keys as `translations.shared.de.ts`. */
import type { sharedDe } from './translations.shared.de';

export const sharedEn = {
  'event.state.draft': 'Draft',
  'event.state.published': 'Published',
  'event.state.archived': 'Archived',
  'action.close': 'Close',
  'action.cancel': 'Cancel',
  'action.retry': 'Try again',
  'shell.breadcrumb': 'Breadcrumb',
  'ui.filterSelect.empty': 'No choices available',
  'ui.listDetail.back': 'Back to the list',
  'ui.rowMenu.trigger': 'More actions',
  'ui.rowMenu.empty': 'No actions available',
  'ui.search.clear': 'Clear search',
} as const satisfies Record<keyof typeof sharedDe, string>;
