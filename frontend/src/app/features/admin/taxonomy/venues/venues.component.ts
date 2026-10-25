/**
 * I23, tab "Orte" (`/verwaltung/orte`): venues as an inline-editable table. Many existing venues
 * have no address. Coordinates are two number fields plus a pin sheet with a map and a one-press address
 * search; venues are only deactivated.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { MapPin } from '@shared/ui/map/map.models';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent } from '@shared/ui/select/select.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import {
  ButtonComponent,
  CellDirective,
  type ColumnDef,
  DataTableComponent,
  InputComponent,
  SwitchComponent,
} from '@stupa-makers/ui-kit';
import { PRECISION_KEYS, optionsOf } from '../../admin-labels';
import {
  type AdminVenue,
  PUBLIC_PRECISIONS,
  type PublicPrecision,
  type VenueWrite,
} from '../../api/admin.models';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { TaxonomyTable } from '../taxonomy-table';
import { toNumber } from './venue-geocode';
import { type AppliedPin, VenuePinSheetComponent } from './venue-pin-sheet.component';

interface VenueValue {
  slug: string;
  name: string;
  address: string;
  postcode: string;
  city: string;
  buildingNo: string;
  roomKey: string;
  lat: string;
  lon: string;
  publicPrecision: PublicPrecision;
  isPrivate: boolean;
  active: boolean;
}

const BLANK: VenueValue = {
  slug: '',
  name: '',
  address: '',
  postcode: '',
  city: '',
  buildingNo: '',
  roomKey: '',
  lat: '',
  lon: '',
  publicPrecision: 'building',
  isPrivate: false,
  active: true,
};

const DRAFT: AdminVenue = {
  id: 'new',
  slug: '',
  name: '',
  address: null,
  postcode: null,
  city: null,
  buildingNo: null,
  roomKey: null,
  campusBuildingNo: null,
  lat: null,
  lon: null,
  publicPrecision: 'building',
  geocodeSource: null,
  geocodedAt: null,
  isPrivate: false,
  legacyWpId: null,
  notes: null,
  active: true,
  createdAt: '',
  updatedAt: '',
};

const blankToNull = (text: string): string | null => text.trim() || null;

@Component({
  selector: 'app-venues',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
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
    VenuePinSheetComponent,
  ],
  templateUrl: './venues.component.html',
  styleUrl: './venues.component.scss',
})
export class VenuesComponent extends TaxonomyTable<AdminVenue, VenueValue> {
  private readonly api = inject(TaxonomyApi);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    slug: '',
    name: '',
    address: '',
    postcode: '',
    city: '',
    buildingNo: '',
    roomKey: '',
    lat: '',
    lon: '',
    publicPrecision: 'building' as PublicPrecision,
    isPrivate: false,
    active: true,
  });

  protected readonly columns: ColumnDef[] = [
    { key: 'name', label: this.i18n.translate('admin.col.name'), width: '16rem' },
    { key: 'slug', label: this.i18n.translate('admin.col.slug'), width: '11rem' },
    { key: 'address', label: this.i18n.translate('admin.col.address'), width: '14rem' },
    { key: 'postcode', label: this.i18n.translate('admin.col.postcode'), width: '6rem' },
    { key: 'city', label: this.i18n.translate('admin.col.city'), width: '10rem' },
    { key: 'buildingNo', label: this.i18n.translate('admin.col.building'), width: '8rem' },
    { key: 'roomKey', label: this.i18n.translate('admin.col.room'), width: '8rem' },
    { key: 'publicPrecision', label: this.i18n.translate('admin.col.precision'), width: '10rem' },
    { key: 'isPrivate', label: this.i18n.translate('admin.col.private'), width: '7rem' },
    { key: 'coordinates', label: this.i18n.translate('admin.col.coordinates'), width: '14rem' },
    { key: 'active', label: this.i18n.translate('admin.col.active'), width: '7rem' },
    {
      key: 'actions',
      label: this.i18n.translate('admin.col.actions'),
      sticky: 'end',
      card: 'actions',
    },
  ];

  protected readonly precisionOptions = optionsOf(this.i18n, PUBLIC_PRECISIONS, PRECISION_KEYS);
  protected readonly precisionKeys = PRECISION_KEYS;

  protected readonly sheetOpen = signal(false);
  private readonly applied = signal<AppliedPin | null>(null);
  protected readonly editedVenue = computed(
    () => this.loaded().find((row) => row.id === this.editingId()) ?? (this.isNew() ? DRAFT : null),
  );

  protected rows() {
    return this.isNew() ? [DRAFT, ...this.loaded()] : this.loaded();
  }

  protected fetch() {
    return this.api.venues();
  }

  protected blank(): VenueValue {
    return BLANK;
  }

  protected toValue(row: AdminVenue): VenueValue {
    return {
      slug: row.slug,
      name: row.name,
      address: row.address ?? '',
      postcode: row.postcode ?? '',
      city: row.city ?? '',
      buildingNo: row.buildingNo ?? '',
      roomKey: row.roomKey ?? '',
      lat: row.lat === null ? '' : String(row.lat),
      lon: row.lon === null ? '' : String(row.lon),
      publicPrecision: row.publicPrecision,
      isPrivate: row.isPrivate,
      active: row.active,
    };
  }

  protected override startEdit(row: AdminVenue): void {
    this.applied.set(null);
    super.startEdit(row);
  }

  protected override startNew(): void {
    this.applied.set(null);
    super.startNew();
  }

  protected startPin(): MapPin | null {
    const lat = toNumber(this.form.controls.lat.value);
    const lon = toNumber(this.form.controls.lon.value);
    return lat === null || lon === null ? null : { lat, lon };
  }

  protected openSheet(): void {
    this.sheetOpen.set(true);
  }

  protected takePin(pin: AppliedPin): void {
    this.applied.set(pin);
    this.form.patchValue({ lat: pin.lat.toFixed(6), lon: pin.lon.toFixed(6) });
    this.form.markAsDirty();
  }

  protected override validate(v: VenueValue): Record<string, string> {
    const errors = super.validate(v);
    const lat = toNumber(v.lat);
    const lon = toNumber(v.lon);
    const bad = this.i18n.translate('admin.err.coordinatesIncomplete');
    const outOfRange =
      (lat !== null && Math.abs(lat) > 90) || (lon !== null && Math.abs(lon) > 180);
    if (String(v.lat).trim() !== '' && lat === null) errors['lat'] = bad;
    if (String(v.lon).trim() !== '' && lon === null) errors['lon'] = bad;
    if ((lat === null) !== (lon === null) || outOfRange) errors['lat'] = errors['lat'] ?? bad;
    return errors;
  }

  private coordinates(id: string | null, v: VenueValue): Partial<VenueWrite> {
    const lat = toNumber(v.lat);
    const lon = toNumber(v.lon);
    const row = this.loaded().find((r) => r.id === id);
    if (toNumber(row?.lat) === lat && toNumber(row?.lon) === lon) return {};
    const source = this.applied();
    const searched = source?.source === 'nominatim' && source.lat === lat && source.lon === lon;
    return {
      lat,
      lon,
      ...(searched && lat !== null ? { geocodeSource: 'nominatim' as const } : {}),
    };
  }

  protected write(id: string | null, v: VenueValue) {
    const body = {
      ...this.coordinates(id, v),
      name: v.name.trim(),
      address: blankToNull(v.address),
      postcode: blankToNull(v.postcode),
      city: blankToNull(v.city),
      buildingNo: blankToNull(v.buildingNo),
      roomKey: blankToNull(v.roomKey),
      publicPrecision: v.publicPrecision,
      isPrivate: v.isPrivate,
      active: v.active,
    };
    return id === null
      ? this.api.createVenue({ ...body, slug: v.slug })
      : this.api.updateVenue(id, body);
  }
}
