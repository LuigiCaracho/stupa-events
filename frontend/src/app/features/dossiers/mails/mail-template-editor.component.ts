/**
 * Detail of one mail template (I11): subject, body in the editor shell, the placeholder list (a click inserts
 * `{{ path }}`), a live preview from `render-preview` (debounced), and the buttons "Text kopieren" and "Als Mail
 * öffnen". The server never sends from the dossier; copy and `mailto:` are built here. A refused template shows the
 * findings as a note with the allowed placeholders.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { LOCATION } from '@core/browser/location.token';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent, InputComponent, ToastService } from '@stupa-makers/ui-kit';
import { Subject, catchError, debounceTime, of, switchMap } from 'rxjs';
import { DocumentsApi } from '../api/documents-api.service';
import { MailTemplatesApi } from '../api/mail-templates-api.service';
import { problemMessage } from '../api/problem-message';
import { DocumentDraft } from '../editor/document-draft';
import { DossierMarkdownEditorComponent } from '../editor/dossier-markdown-editor.component';
import type { MailTemplateOut, PlaceholderOut, RenderedMail } from '../model/document.models';
import { mailtoFor, templateReasonText } from './mail-preview';

const PREVIEW_DEBOUNCE_MS = 400;

@Component({
  selector: 'app-mail-template-editor',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    DossierMarkdownEditorComponent,
    InputComponent,
    NoteComponent,
  ],
  templateUrl: './mail-template-editor.component.html',
  styleUrl: './mail-template-editor.component.scss',
})
export class MailTemplateEditorComponent {
  private readonly api = inject(MailTemplatesApi);
  private readonly documents = inject(DocumentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);
  private readonly location = inject(LOCATION);

  readonly eventId = input.required<string>();
  /** The stored template, or null for a new one. */
  readonly template = input<MailTemplateOut | null>(null);
  readonly placeholders = input<readonly PlaceholderOut[]>([]);
  readonly canEdit = input(false);

  readonly saved = output<MailTemplateOut>();

  protected readonly subject = signal('');
  protected readonly title = signal('');
  protected readonly body = signal('');
  protected readonly preview = signal<RenderedMail | null>(null);
  protected readonly errors = signal<string[]>([]);
  protected readonly tooLong = signal(false);
  protected readonly busy = signal(false);
  protected readonly shell = viewChild(DossierMarkdownEditorComponent);

  private readonly preview$ = new Subject<{ subject: string; bodyMd: string }>();
  protected readonly draft = new DocumentDraft(
    this.documents,
    () => {
      const t = this.template();
      return t ? { documentId: t.id, baseRev: t.rev } : null;
    },
    () => `mail:${this.template()?.id ?? this.eventId()}`,
    inject(DestroyRef),
  );
  protected readonly docKey = computed(() => `mail:${this.template()?.id ?? 'new'}`);

  constructor() {
    effect(() => {
      const t = this.template();
      untracked(() => {
        this.title.set(t?.title ?? '');
        this.subject.set(t?.subject ?? '');
        this.body.set(t?.bodyMd ?? '');
        this.preview.set(null);
        this.errors.set([]);
        this.draft.settle();
      });
    });
    this.preview$
      .pipe(
        debounceTime(PREVIEW_DEBOUNCE_MS),
        switchMap((draft) =>
          this.api.preview(this.eventId(), this.template()?.id ?? 'new', draft).pipe(
            catchError((err: unknown) => {
              this.showErrors(err);
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((rendered) => {
        if (!rendered) return;
        this.errors.set([]);
        this.preview.set(rendered);
      });
    effect(() => {
      const draft = { subject: this.subject(), bodyMd: this.body() };
      untracked(() => this.preview$.next(draft));
    });
  }

  protected setBody(value: string): void {
    this.body.set(value);
    if (this.template()) this.draft.change(value);
  }

  protected insert(path: string): void {
    this.shell()?.insertText(`{{ ${path} }}`);
  }

  protected save(): void {
    this.busy.set(true);
    const t = this.template();
    this.api
      .put(this.eventId(), t?.id ?? 'new', t?.rev ?? 0, {
        title: this.title() || this.subject(),
        subject: this.subject(),
        bodyMd: this.body(),
      })
      .subscribe({
        next: (saved) => {
          this.busy.set(false);
          this.draft.settle();
          this.toast.success(this.i18n.translate('mail.saved'));
          this.saved.emit(saved);
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.showErrors(err);
        },
      });
  }

  protected async copy(): Promise<void> {
    const p = this.preview();
    if (!p) return;
    const text = `${p.subject}\n\n${p.body}`;
    try {
      await navigator.clipboard.writeText(text);
      this.toast.success(this.i18n.translate('mail.copied'));
    } catch {
      this.toast.show(this.i18n.translate('mail.copyFallback'), 'warning', 8000);
    }
  }

  protected openMail(): void {
    const p = this.preview();
    if (!p) return;
    const result = mailtoFor(p.subject, p.body);
    this.tooLong.set('tooLong' in result);
    if ('href' in result) this.location.assign(result.href);
  }

  private showErrors(err: unknown): void {
    const problem = problemOf(err);
    const reasons = problem.reasons ?? [];
    if (problem.code === 'template_invalid' && reasons.length > 0) {
      this.errors.set(reasons.map((r) => templateReasonText(this.i18n, r)));
    } else {
      this.errors.set([problemMessage(this.i18n, problem)]);
    }
  }
}
