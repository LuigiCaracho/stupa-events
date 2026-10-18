/**
 * I23, tab "Organisationen" (`/verwaltung/organisationen`): organizations as an inline-editable table.
 * The `trusted` switch needs `admin.mappings` and asks for confirmation before it turns on, because
 * it lets the approvers of the organization publish their own events.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import {
  ButtonComponent,
  CellDirective,
  type ColumnDef,
  DataTableComponent,
  DialogComponent,
  InputComponent,
  SwitchComponent,
} from '@stupa-makers/ui-kit';
import { rxResource } from '@angular/core/rxjs-interop';
import { KIND_KEYS, optionsOf } from '../../admin-labels';
import { type AdminOrganization, ORGANIZATION_KINDS, type OrganizationKind } from '../../api/admin.models';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { TaxonomyTable } from '../taxonomy-table';

interface OrganizationValue {
  slug: string;
  name: string;
  kind: OrganizationKind;
  short: string;
  categoryId: string;
  instagram: string;
  trusted: boolean;
  active: boolean;
}

const BLANK: OrganizationValue = {
  slug: '',
  name: '',
  kind: 'fachschaft',
  short: '',
  categoryId: '',
  instagram: '',
  trusted: false,
  active: true,
};

const DRAFT: AdminOrganization = {
  id: 'new',
  slug: '',
  name: '',
  kind: 'fachschaft',
  short: '',
  parentId: null,
  colorToken: null,
  categoryId: null,
  instagram: [],
  trusted: false,
  legacyWpIds: [],
  active: true,
  createdAt: '',
  updatedAt: '',
};

const splitAccounts = (text: string): string[] =>
  text
    .split(',')
    .map((a) => a.trim())
    .filter(Boolean);

@Component({
  selector: 'app-organizations',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CellDirective,
    DataTableComponent,
    DialogComponent,
    InputComponent,
    NoteComponent,
    SelectFieldComponent,
    StatusTextComponent,
    SwitchComponent,
  ],
  templateUrl: './organizations.component.html',
  styleUrl: './organizations.component.scss',
})
export class OrganizationsComponent extends TaxonomyTable<AdminOrganization, OrganizationValue> {
  private readonly api = inject(TaxonomyApi);
  private readonly auth = inject(AuthService);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    slug: '',
    name: '',
    kind: 'fachschaft' as OrganizationKind,
    short: '',
    categoryId: '',
    instagram: '',
    trusted: false,
    active: true,
  });

  protected readonly canTrust = computed(() => this.auth.can('admin.mappings'));
  protected readonly confirmTrust = signal(false);
  protected readonly categories = rxResource({ stream: () => this.api.categories() });

  protected readonly columns: ColumnDef[] = [
    { key: 'name', label: this.i18n.translate('admin.col.name'), width: '16rem' },
    { key: 'slug', label: this.i18n.translate('admin.col.slug'), width: '11rem' },
    { key: 'kind', label: this.i18n.translate('admin.col.kind'), width: '10rem' },
    { key: 'short', label: this.i18n.translate('admin.col.short'), width: '8rem' },
    { key: 'categoryId', label: this.i18n.translate('admin.col.category'), width: '14rem' },
    { key: 'instagram', label: this.i18n.translate('admin.col.instagram'), width: '14rem' },
    { key: 'trusted', label: this.i18n.translate('admin.col.trusted'), width: '9rem' },
    { key: 'active', label: this.i18n.translate('admin.col.active'), width: '7rem' },
    { key: 'actions', label: this.i18n.translate('admin.col.actions'), sticky: 'end', card: 'actions' },
  ];

  protected readonly kindOptions = optionsOf(this.i18n, ORGANIZATION_KINDS, KIND_KEYS);
  protected readonly kindKeys = KIND_KEYS;

  protected readonly categoryOptions = computed<SelectFieldOption[]>(() =>
    (this.categories.hasValue() ? this.categories.value() : []).map((c) => ({ value: c.id, label: c.name })),
  );
  protected readonly categoryName = computed(
    () => new Map((this.categories.hasValue() ? this.categories.value() : []).map((c) => [c.id, c.name] as const)),
  );

  protected readonly rows = computed(() => (this.isNew() ? [DRAFT, ...this.loaded()] : this.loaded()));

  protected override startNew(): void {
    super.startNew();
    this.syncTrustedAccess();
  }

  protected override startEdit(row: AdminOrganization): void {
    super.startEdit(row);
    this.syncTrustedAccess();
  }

  private syncTrustedAccess(): void {
    if (this.canTrust()) this.form.controls.trusted.enable();
    else this.form.controls.trusted.disable();
  }

  protected onTrustedChange(on: boolean): void {
    if (on) this.confirmTrust.set(true);
  }

  protected acceptTrust(): void {
    this.form.controls.trusted.setValue(true);
    this.confirmTrust.set(false);
  }

  protected declineTrust(): void {
    this.form.controls.trusted.setValue(false);
    this.confirmTrust.set(false);
  }

  protected fetch() {
    return this.api.organizations();
  }

  protected blank(): OrganizationValue {
    return BLANK;
  }

  protected toValue(row: AdminOrganization): OrganizationValue {
    return {
      slug: row.slug,
      name: row.name,
      kind: row.kind,
      short: row.short,
      categoryId: row.categoryId ?? '',
      instagram: row.instagram.join(', '),
      trusted: row.trusted,
      active: row.active,
    };
  }

  protected write(id: string | null, v: OrganizationValue) {
    const body = {
      name: v.name.trim(),
      kind: v.kind,
      short: v.short.trim(),
      categoryId: v.categoryId || null,
      instagram: splitAccounts(v.instagram),
      active: v.active,
      ...(this.canTrust() && { trusted: v.trusted }),
    };
    return id === null ? this.api.createOrganization({ ...body, slug: v.slug }) : this.api.updateOrganization(id, body);
  }
}
