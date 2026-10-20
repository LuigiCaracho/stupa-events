/**
 * Comment threads of a dossier. Pattern from the workflow tool's chat block, cut down to what a review question
 * needs: root comments with an anchor chip, replies, resolve and reopen, one reply box per thread. The page owns the
 * requests; this block only emits.
 */
import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { CommentThread } from '../../../features/dossiers/model/comment.models';
import { MarkdownViewComponent } from '../../markdown/markdown-view.component';
import { TextareaComponent } from '../textarea/textarea.component';
import { StatusTextComponent } from '../status-text/status-text.component';

export interface ChatReply {
  parentId: string;
  bodyMd: string;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    LocalizedDatePipe,
    ButtonComponent,
    MarkdownViewComponent,
    StatusTextComponent,
    TextareaComponent,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent {
  readonly threads = input.required<readonly CommentThread[]>();
  readonly anchorLabel = input.required<(thread: CommentThread) => string>();
  readonly canWrite = input(false);
  readonly canResolve = input<(thread: CommentThread) => boolean>(() => false);
  readonly busy = input(false);

  readonly reply = output<ChatReply>();
  readonly resolve = output<string>();
  readonly reopen = output<string>();
  readonly jump = output<CommentThread>();

  protected readonly replyFor = signal<string | null>(null);
  protected draft = '';

  protected openReply(id: string): void {
    this.draft = '';
    this.replyFor.set(id);
  }

  protected send(thread: CommentThread): void {
    const text = this.draft.trim();
    if (!text) return;
    this.reply.emit({ parentId: thread.id, bodyMd: text });
    this.replyFor.set(null);
  }
}
