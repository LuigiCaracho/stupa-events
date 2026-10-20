/** Helpers of the mail tab (contract 6.4): the `mailto:` link with its length limit and the sentence for a refused template. */
import type { ProblemReason } from '@core/api/models';
import type { I18nService } from '@core/i18n/i18n.service';

/** Mail clients cut a `mailto:` URL somewhere above this length; the page then asks to copy instead. */
export const MAILTO_LIMIT = 1800;

export type MailtoResult = { href: string } | { tooLong: true };

export function mailtoFor(subject: string, body: string): MailtoResult {
  const href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return href.length > MAILTO_LIMIT ? { tooLong: true } : { href };
}

interface TemplateReason extends ProblemReason {
  allowed?: string[];
  line?: number;
}

/** One sentence per finding of a 422 `template_invalid`; an unknown placeholder lists what is allowed. */
export function templateReasonText(i18n: I18nService, reason: ProblemReason): string {
  const r = reason as TemplateReason;
  if (r.code === 'unknown_placeholder') {
    return i18n.translate('mail.unknownPlaceholder', {
      field: r.field ?? '',
      allowed: (r.allowed ?? []).map((p) => `{{ ${p} }}`).join(', '),
    });
  }
  if (r.code === 'statement_not_allowed') return i18n.translate('mail.statementNotAllowed');
  if (r.code === 'syntax_error') return i18n.translate('mail.syntaxError', { line: r.line ?? 0 });
  return i18n.translate('problem.templateInvalid');
}
