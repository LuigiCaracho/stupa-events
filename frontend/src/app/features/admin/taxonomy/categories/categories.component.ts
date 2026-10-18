/**
 * I23, tab "Kategorien" (`/verwaltung/kategorien`): the category tree as an inline-editable
 * table. Slugs are fixed after creation, categories are never deleted, only deactivated.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import {
  ButtonComponent,
  CellDirective,
  type ColumnDef,
  DataTableComponent,
  InputComponent,
  SwitchComponent,
} from '@stupa-makers/ui-kit';
import { COLOR_KEYS, KIND_KEYS, PROFILE_KEYS, optionsOf } from '../../admin-labels';
import {
  type AdminCategory,
  CATEGORY_KINDS,
  COLOR_TOKENS,
  type CategoryKind,
  type ColorToken,
  REQUIRED_PROFILES,
  type RequiredProfile,
} from '../../api/admin.models';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { NEW_ROW, TaxonomyTable } from '../taxonomy-table';
import { categoryRows, descendantIds } from './category-tree';

interface CategoryValue {
  slug: string;
  name: string;
  kind: CategoryKind;
  parentId: string;
  short: string;
  colorToken: ColorToken | '';
  requiredProfile: RequiredProfile;
  active: boolean;
}

@Component({
  selector: 'app-categories',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CellDirective,
    DataTableComponent,
    InputComponent,
    NoteComponent,
    SelectFieldComponent,
    StatusTextComponent,
    SwitchComponent,
  ],
  templateUrl: './categories.component.html',
  styleUrl: './categories.component.scss',
})
export class CategoriesComponent extends TaxonomyTable<AdminCategory, CategoryValue> {
  private readonly api = inject(TaxonomyApi);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    slug: '',
    name: '',
    kind: 'format' as CategoryKind,
    parentId: '',
    short: '',
    colorToken: '' as ColorToken | '',
    requiredProfile: 'generic' as RequiredProfile,
    active: true,
  });

  protected readonly columns: ColumnDef[] = [
    { key: 'name', label: this.i18n.translate('admin.col.name'), width: '16rem' },
    { key: 'slug', label: this.i18n.translate('admin.col.slug'), width: '11rem' },
    { key: 'kind', label: this.i18n.translate('admin.col.kind'), width: '10rem' },
    { key: 'parentId', label: this.i18n.translate('admin.col.parent'), width: '14rem' },
    { key: 'short', label: this.i18n.translate('admin.col.short'), width: '8rem' },
    { key: 'colorToken', label: this.i18n.translate('admin.col.color'), width: '10rem' },
    { key: 'requiredProfile', label: this.i18n.translate('admin.col.profile'), width: '10rem' },
    { key: 'active', label: this.i18n.translate('admin.col.active'), width: '7rem' },
    { key: 'actions', label: this.i18n.translate('admin.col.actions'), sticky: 'end', card: 'actions' },
  ];

  protected readonly kindOptions = optionsOf(this.i18n, CATEGORY_KINDS, KIND_KEYS);
  protected readonly colorOptions = optionsOf(this.i18n, COLOR_TOKENS, COLOR_KEYS);
  protected readonly profileOptions = optionsOf(this.i18n, REQUIRED_PROFILES, PROFILE_KEYS);
  protected readonly kindKeys = KIND_KEYS;
  protected readonly colorKeys = COLOR_KEYS;
  protected readonly profileKeys = PROFILE_KEYS;

  protected readonly rows = computed(() => {
    const tree = categoryRows(this.loaded());
    return this.isNew() ? [{ ...DRAFT, depth: 0 }, ...tree] : tree;
  });

  protected readonly parentOptions = computed<SelectFieldOption[]>(() => {
    const own = this.editingId();
    const excluded = own && own !== NEW_ROW ? descendantIds(this.loaded(), own) : new Set<string>();
    return categoryRows(this.loaded())
      .filter((c) => !excluded.has(c.id))
      .map((c) => ({ value: c.id, label: `${' '.repeat(c.depth)}${c.name}` }));
  });

  protected readonly parentName = computed(
    () => new Map(this.loaded().map((c) => [c.id, c.name] as const)),
  );

  protected fetch() {
    return this.api.categories();
  }

  protected blank(): CategoryValue {
    return BLANK;
  }

  protected toValue(row: AdminCategory): CategoryValue {
    return {
      slug: row.slug,
      name: row.name,
      kind: row.kind,
      parentId: row.parentId ?? '',
      short: row.short ?? '',
      colorToken: row.colorToken ?? '',
      requiredProfile: row.requiredProfile,
      active: row.active,
    };
  }

  protected write(id: string | null, v: CategoryValue) {
    const body = {
      name: v.name.trim(),
      kind: v.kind,
      parentId: v.parentId || null,
      short: v.short.trim() || null,
      colorToken: v.colorToken || null,
      requiredProfile: v.requiredProfile,
      active: v.active,
    };
    return id === null
      ? this.api.createCategory({ ...body, slug: v.slug })
      : this.api.updateCategory(id, body);
  }
}

const BLANK: CategoryValue = {
  slug: '',
  name: '',
  kind: 'format',
  parentId: '',
  short: '',
  colorToken: '',
  requiredProfile: 'generic',
  active: true,
};

const DRAFT: AdminCategory = {
  id: NEW_ROW,
  slug: '',
  name: '',
  kind: 'format',
  parentId: null,
  short: null,
  colorToken: null,
  requiredProfile: 'generic',
  legacyWpId: null,
  sort: 0,
  active: true,
  createdAt: '',
  updatedAt: '',
};
