/**
 * I24 (`/verwaltung/zuordnungen`): maps IdP groups to a role and, for organization roles, an
 * organization. Groups and members come from Authentik; this page only maps. Rows edit inline
 * (the group is fixed after creation), delete asks first, and every row expands into a preview
 * of the people it reaches.
 *
 * Pattern from STUPA-Workflow@93c33d6 frontend/src/app/pages/admin/group-mappings/group-mappings.component.ts (rewritten, no code copied).
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import {
  ButtonComponent,
  CellDirective,
  type ColumnDef,
  DataTableComponent,
  DialogComponent,
  InputComponent,
  RowDetailDirective,
  ToastService,
} from '@stupa-makers/ui-kit';
import { problemMessage } from '../../dossiers/api/problem-message';
import { ROLE_KEYS } from '../admin-labels';
import { adminErrors } from '../admin-errors';
import {
  GLOBAL_ROLES,
  type GroupMapping,
  type MappingRole,
  ORGANIZATION_ROLES,
} from '../api/admin.models';
import { MappingsApi } from '../api/mappings-api.service';
import { NEW_ROW, TaxonomyTable } from '../taxonomy/taxonomy-table';
import { PrincipalPreviewComponent } from './principal-preview.component';

interface MappingValue {
  oidcGroup: string;
  role: MappingRole | '';
  organizationId: string;
}

const BLANK: MappingValue = { oidcGroup: '', role: '', organizationId: '' };
const ALL_ROLES: readonly MappingRole[] = [...GLOBAL_ROLES, ...ORGANIZATION_ROLES];
const isOrgRole = (role: MappingRole | ''): boolean => role !== '' && ORGANIZATION_ROLES.includes(role);

const DRAFT: GroupMapping = {
  id: NEW_ROW,
  oidcGroup: '',
  role: 'viewer',
  organization: null,
  principalCount: 0,
  createdAt: '',
  updatedAt: '',
};

@Component({
  selector: 'app-mappings',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CellDirective,
    DataTableComponent,
    DialogComponent,
    EmptyStateComponent,
    InputComponent,
    NoteComponent,
    PrincipalPreviewComponent,
    RowDetailDirective,
    SelectFieldComponent,
  ],
  templateUrl: './mappings.component.html',
  styleUrl: './mappings.component.scss',
})
export class MappingsComponent extends TaxonomyTable<GroupMapping, MappingValue> {
  private readonly api = inject(MappingsApi);
  private readonly toastService = inject(ToastService);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    oidcGroup: '',
    role: '' as MappingRole | '',
    organizationId: '',
  });

  protected readonly orgs = rxResource({ stream: () => this.api.organizations() });
  protected readonly expanded = signal<string | null>(null);
  protected readonly deleting = signal<GroupMapping | null>(null);
  protected readonly working = signal(false);
  protected readonly roleKeys = ROLE_KEYS;
  protected readonly isExpanded = (row: unknown): boolean => this.expanded() === (row as GroupMapping).id;

  protected readonly columns: ColumnDef[] = [
    { key: 'oidcGroup', label: this.i18n.translate('admin.col.group'), width: '18rem', card: 'title' },
    { key: 'role', label: this.i18n.translate('admin.col.role'), width: '14rem' },
    { key: 'organizationId', label: this.i18n.translate('admin.col.organization'), width: '16rem' },
    { key: 'principalCount', label: this.i18n.translate('admin.col.people'), width: '7rem' },
    { key: 'actions', label: this.i18n.translate('admin.col.actions'), sticky: 'end', card: 'actions' },
  ];

  protected readonly roleOptions: SelectFieldOption[] = ALL_ROLES.map((role) => ({
    value: role,
    label: this.i18n.translate(ROLE_KEYS[role]),
  }));
  protected readonly orgOptions = computed<SelectFieldOption[]>(() =>
    (this.orgs.hasValue() ? this.orgs.value() : []).map((o) => ({ value: o.id, label: o.name })),
  );
  protected readonly rows = computed(() => (this.isNew() ? [DRAFT, ...this.loaded()] : this.loaded()));

  protected globalRole(): boolean {
    const role = this.form.controls.role.value;
    return role !== '' && !isOrgRole(role);
  }

  protected toggle(row: GroupMapping): void {
    this.expanded.update((open) => (open === row.id ? null : row.id));
  }

  protected defaults(): void {
    if (this.working()) return;
    this.working.set(true);
    this.api.createDefaults().subscribe({
      next: (created) => {
        this.working.set(false);
        this.toastService.success(this.i18n.translate('admin.defaultsCreated', { n: created.length }));
        this.list.reload();
      },
      error: (err: unknown) => {
        this.working.set(false);
        this.toastService.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }

  protected confirmDelete(): void {
    const row = this.deleting();
    if (!row || this.working()) return;
    this.working.set(true);
    this.api.remove(row.id).subscribe({
      next: () => {
        this.working.set(false);
        this.deleting.set(null);
        this.list.reload();
      },
      error: (err: unknown) => {
        this.working.set(false);
        this.deleting.set(null);
        const { fields, message } = adminErrors(this.i18n, problemOf(err));
        this.toastService.error(message ?? Object.values(fields).join(' '));
      },
    });
  }

  protected fetch() {
    return this.api.list();
  }

  protected blank(): MappingValue {
    return BLANK;
  }

  protected toValue(row: GroupMapping): MappingValue {
    return { oidcGroup: row.oidcGroup, role: row.role, organizationId: row.organization?.id ?? '' };
  }

  protected override validate(v: MappingValue): Record<string, string> {
    const errors: Record<string, string> = {};
    if (this.isNew() && !v.oidcGroup.trim()) errors['oidcGroup'] = this.i18n.translate('admin.err.groupRequired');
    if (!v.role) errors['role'] = this.i18n.translate('admin.err.roleRequired');
    else if (isOrgRole(v.role) && !v.organizationId) {
      errors['organizationId'] = this.i18n.translate('admin.err.organizationRequired');
    }
    return errors;
  }

  protected write(id: string | null, v: MappingValue) {
    const role = v.role as MappingRole;
    const organizationId = isOrgRole(role) ? v.organizationId : null;
    return id === null
      ? this.api.create({ oidcGroup: v.oidcGroup.trim(), role, organizationId })
      : this.api.update(id, { role, organizationId });
  }
}
