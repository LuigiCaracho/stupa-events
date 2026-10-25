/**
 * The pin sheet of the venue table (I23): an `app-map` in pick mode, a button for the address search and the apply
 * button. The search asks the server once per press and only proposes a position; nothing is saved before the editor
 * applies the pin and saves the row. The map loads when the sheet opens, and the number fields of the row stay the
 * keyboard alternative.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  model,
  output,
  signal,
} from '@angular/core';
import { problemOf } from '@core/api/problem';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { MapComponent } from '@shared/ui/map/map.component';
import type { MapPin } from '@shared/ui/map/map.models';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SideSheetComponent } from '@shared/ui/side-sheet/side-sheet.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { AdminVenue } from '../../api/admin.models';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { geocodeError, searchBlock, suggestion } from './venue-geocode';

export interface AppliedPin extends MapPin {
  source: 'pin' | 'nominatim';
}

@Component({
  selector: 'app-venue-pin-sheet',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, MapComponent, NoteComponent, SideSheetComponent],
  templateUrl: './venue-pin-sheet.component.html',
  styleUrl: './venue-pin-sheet.component.scss',
})
export class VenuePinSheetComponent {
  private readonly api = inject(TaxonomyApi);

  readonly open = model(false);
  readonly venue = input<AdminVenue | null>(null);
  readonly start = input<MapPin | null>(null);
  readonly applied = output<AppliedPin>();

  protected readonly pin = signal<MapPin | null>(null);
  protected readonly fromSearch = signal(false);
  protected readonly searching = signal(false);
  protected readonly message = signal<TranslationKey | null>(null);
  protected readonly block = computed(() => searchBlock(this.venue()));
  protected readonly view = computed(() => this.pin() ?? this.start());

  protected setPin(pin: MapPin): void {
    this.pin.set(pin);
    this.fromSearch.set(false);
    this.message.set(null);
  }

  protected search(): void {
    const venue = this.venue();
    if (!venue || this.block() || this.searching()) return;
    this.searching.set(true);
    this.message.set(null);
    this.api.geocodeVenue(venue.id).subscribe({
      next: (answer) => {
        this.searching.set(false);
        const found = suggestion(answer);
        if (!found) return this.message.set('admin.pin.notFound');
        this.pin.set(found);
        this.fromSearch.set(true);
      },
      error: (err: unknown) => {
        this.searching.set(false);
        this.message.set(geocodeError(problemOf(err)));
      },
    });
  }

  protected apply(): void {
    const pin = this.pin();
    if (!pin) return;
    this.applied.emit({ ...pin, source: this.fromSearch() ? 'nominatim' : 'pin' });
    this.open.set(false);
  }

  protected onClosed(): void {
    this.pin.set(null);
    this.fromSearch.set(false);
    this.message.set(null);
  }
}
