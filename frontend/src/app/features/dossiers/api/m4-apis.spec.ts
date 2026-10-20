import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NotificationsApi } from '../../notifications/notifications-api.service';
import { AttachmentsApi } from './attachments-api.service';
import { ChecklistApi } from './checklist-api.service';
import { CommentsApi } from './comments-api.service';
import { DocumentsApi } from './documents-api.service';
import { MailTemplatesApi } from './mail-templates-api.service';

describe('M4 API clients', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('talks to the attachment endpoints', () => {
    const api = TestBed.inject(AttachmentsApi);
    const file = new File(['x'], 'plan.pdf', { type: 'application/pdf' });
    api.list('e1', true).subscribe();
    expect(
      http
        .expectOne((r) => r.url === '/api/events/e1/attachments')
        .request.params.get('includeRetired'),
    ).toBe('true');
    api.counts('e1').subscribe();
    http.expectOne('/api/events/e1/dossier-counts');
    api.upload('e1', { file, kind: 'business_plan', visibility: 'org', altText: '' }).subscribe();
    const up = http.expectOne({ method: 'POST', url: '/api/events/e1/attachments' });
    const form = up.request.body as FormData;
    expect(form.get('kind')).toBe('business_plan');
    expect(form.get('visibility')).toBe('org');
    expect(form.has('altText')).toBe(false);
    api.replace('a1', { file, kind: 'other' }).subscribe();
    http.expectOne('/api/attachments/a1/replace');
    api.patch('a1', { visibility: 'team' }).subscribe();
    expect(http.expectOne({ method: 'PATCH', url: '/api/attachments/a1' }).request.body).toEqual({
      visibility: 'team',
    });
    api.retire('a1').subscribe();
    http.expectOne('/api/attachments/a1/retire');
    expect(api.downloadUrl('a1')).toBe('/api/attachments/a1/download');
    expect(api.previewUrl('a1')).toBe('/api/attachments/a1/preview');
    api.quotes('e1').subscribe();
    http.expectOne('/api/events/e1/quotes');
    api.addQuote('e1', { grp: 'g', vendor: 'v', amountCents: 100 }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/events/e1/quotes' });
    api.selectQuote('q1').subscribe();
    http.expectOne('/api/quotes/q1/select');
    api.removeQuote('q1').subscribe();
    http.expectOne({ method: 'DELETE', url: '/api/quotes/q1' });
  });

  it('sends If-Match with the revision for documents and drafts', () => {
    const api = TestBed.inject(DocumentsApi);
    api.list('e1', 'howto').subscribe();
    expect(
      http.expectOne((r) => r.url === '/api/events/e1/documents').request.params.get('kind'),
    ).toBe('howto');
    api.list('e1').subscribe();
    expect(
      http.expectOne((r) => r.url === '/api/events/e1/documents').request.params.has('kind'),
    ).toBe(false);
    api.create('e1', { kind: 'howto', title: 't' }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/events/e1/documents' });
    api.get('d1').subscribe();
    http.expectOne('/api/documents/d1');
    api.put('d1', 3, { bodyMd: 'x' }).subscribe();
    expect(
      http.expectOne({ method: 'PUT', url: '/api/documents/d1' }).request.headers.get('If-Match'),
    ).toBe('"3"');
    api.revisions('d1').subscribe();
    http.expectOne('/api/documents/d1/revisions');
    api.revision('d1', 2).subscribe();
    http.expectOne('/api/documents/d1/revisions/2');
    api.diff('d1', 1, 2).subscribe();
    const diff = http.expectOne((r) => r.url === '/api/documents/d1/diff');
    expect(diff.request.params.get('from')).toBe('1');
    api.getDraft('d1').subscribe();
    http.expectOne({ method: 'GET', url: '/api/documents/d1/draft' });
    api.putDraft('d1', 4, 'body').subscribe();
    const draft = http.expectOne({ method: 'PUT', url: '/api/documents/d1/draft' });
    expect(draft.request.headers.get('If-Match')).toBe('"4"');
    api.deleteDraft('d1').subscribe();
    http.expectOne({ method: 'DELETE', url: '/api/documents/d1/draft' });
  });

  it('talks to the mail template facade', () => {
    const api = TestBed.inject(MailTemplatesApi);
    api.list('e1').subscribe();
    http.expectOne('/api/events/e1/mail-templates');
    api.get('e1', 'm1').subscribe();
    http.expectOne('/api/events/e1/mail-templates/m1');
    api.put('e1', 'new', 0, { subject: 's', bodyMd: 'b' }).subscribe();
    expect(
      http.expectOne('/api/events/e1/mail-templates/new').request.headers.has('If-Match'),
    ).toBe(false);
    api.put('e1', 'm1', 2, { subject: 's', bodyMd: 'b' }).subscribe();
    expect(http.expectOne('/api/events/e1/mail-templates/m1').request.headers.get('If-Match')).toBe(
      '"2"',
    );
    api.preview('e1', 'm1', { subject: 's' }).subscribe();
    http.expectOne('/api/events/e1/mail-templates/m1/render-preview');
    api.placeholders().subscribe();
    http.expectOne('/api/mail-template-placeholders');
  });

  it('talks to checklist and comments', () => {
    const checklist = TestBed.inject(ChecklistApi);
    checklist.get('e1').subscribe();
    http.expectOne('/api/events/e1/checklist');
    checklist.applyTemplate('e1', 'movie').subscribe();
    expect(http.expectOne('/api/events/e1/checklist/apply-template').request.body).toEqual({
      templateSlug: 'movie',
    });
    checklist.applyTemplate('e1').subscribe();
    expect(http.expectOne('/api/events/e1/checklist/apply-template').request.body).toEqual({});
    checklist.add('e1', { text: 't', phase: 'planning' }).subscribe();
    http.expectOne('/api/events/e1/checklist/items');
    checklist.patch('c1', { dueAt: null }).subscribe();
    http.expectOne({ method: 'PATCH', url: '/api/checklist-items/c1' });
    checklist.done('c1', true).subscribe();
    expect(http.expectOne('/api/checklist-items/c1/done').request.body).toEqual({ done: true });
    checklist.remove('c1').subscribe();
    http.expectOne({ method: 'DELETE', url: '/api/checklist-items/c1' });

    const comments = TestBed.inject(CommentsApi);
    comments.list('e1', true).subscribe();
    expect(
      http.expectOne((r) => r.url === '/api/events/e1/comments').request.params.get('open'),
    ).toBe('true');
    comments.list('e1').subscribe();
    expect(
      http.expectOne((r) => r.url === '/api/events/e1/comments').request.params.has('open'),
    ).toBe(false);
    comments.add('e1', { bodyMd: 'x' }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/events/e1/comments' });
    comments.resolve('k1').subscribe();
    http.expectOne('/api/comments/k1/resolve');
    comments.reopen('k1').subscribe();
    http.expectOne('/api/comments/k1/reopen');
  });

  it('talks to the notification endpoints and unwraps lists', () => {
    const api = TestBed.inject(NotificationsApi);
    let items: unknown;
    api.list(true, 10).subscribe((v) => (items = v));
    const req = http.expectOne((r) => r.url === '/api/notifications');
    expect(req.request.params.get('unread')).toBe('true');
    req.flush({ items: [{ id: 'n1' }] });
    expect(items).toEqual({ items: [{ id: 'n1' }] });
    api.list(false, 30, 'abc').subscribe((v) => (items = v));
    const next = http.expectOne((r) => r.url === '/api/notifications');
    expect(next.request.params.get('cursor')).toBe('abc');
    next.flush([{ id: 'n2' }]);
    expect(items).toEqual({ items: [{ id: 'n2' }], nextCursor: null });
    let count = -1;
    api.unreadCount().subscribe((n) => (count = n));
    http.expectOne('/api/notifications/unread-count').flush({ count: 4 });
    expect(count).toBe(4);
    api.markRead('n1').subscribe();
    http.expectOne('/api/notifications/n1/read');
    api.markAllRead().subscribe();
    http.expectOne('/api/notifications/read-all');
    api.prefs().subscribe((v) => (items = v));
    http.expectOne('/api/account/notification-prefs').flush({ items: [{ kind: 'x' }] });
    expect(items).toEqual([{ kind: 'x' }]);
    api.savePrefs([{ kind: 'comment_added', inApp: true, mail: false }]).subscribe();
    http.expectOne({ method: 'PUT', url: '/api/account/notification-prefs' }).flush({ items: [] });
  });
});
