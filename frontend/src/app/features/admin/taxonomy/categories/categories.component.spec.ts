import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../../testing/a11y';
import { makeCategory } from '../../../../../testing/admin-fixtures';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { CategoriesComponent } from './categories.component';

const TREE = [
  makeCategory({ id: 'fs', slug: 'fachschaft', name: 'Fachschaften', kind: 'fachschaft' }),
  makeCategory({
    id: 'fsi',
    slug: 'fsi',
    name: 'Informatik',
    kind: 'fachschaft',
    parentId: 'fs',
    colorToken: 'petrol',
  }),
  makeCategory({ id: 'kino', slug: 'kino', name: 'Kino', kind: 'format', active: false }),
];

function fakeTaxonomy(overrides: Record<string, unknown> = {}) {
  return {
    categories: jest.fn(() => of(TREE)),
    createCategory: jest.fn(() => of(makeCategory())),
    updateCategory: jest.fn(() => of(makeCategory())),
    ...overrides,
  };
}

async function setup(api = fakeTaxonomy()) {
  const view = await render(CategoriesComponent, {
    providers: [{ provide: TaxonomyApi, useValue: api }],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api, success: jest.spyOn(toast, 'success'), error: jest.spyOn(toast, 'error') };
}

describe('CategoriesComponent', () => {
  it('shows the tree parent first, with the colour as text and inactive categories marked', async () => {
    await setup();
    const names = (await screen.findAllByRole('cell')).map((c) => c.textContent?.trim());
    expect(names.indexOf('Fachschaften')).toBeLessThan(names.indexOf('Informatik'));
    expect(screen.getByText('Petrol')).toBeInTheDocument();
    expect(screen.getByText('inaktiv')).toBeInTheDocument();
    expect(
      screen.getByText('Kategorien werden nicht gelöscht, nur deaktiviert.'),
    ).toBeInTheDocument();
  });

  it('creates a category with an editable slug and a null parent', async () => {
    const { api, success } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Name/ }), ' Party ');
    await userEvent.type(screen.getByRole('textbox', { name: /Slug/ }), 'party');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.createCategory).toHaveBeenCalledWith({
      slug: 'party',
      name: 'Party',
      kind: 'format',
      parentId: null,
      short: null,
      colorToken: null,
      requiredProfile: 'generic',
      active: true,
    });
    expect(success).toHaveBeenCalledWith('Gespeichert.');
    expect(api.categories).toHaveBeenCalledTimes(2);
  });

  it('refuses an invalid slug before it posts', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Name/ }), 'Party');
    await userEvent.type(screen.getByRole('textbox', { name: /Slug/ }), 'Not Valid');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.createCategory).not.toHaveBeenCalled();
    expect(screen.getByText(/Slug: Kleinbuchstaben/)).toBeInTheDocument();
  });

  it('shows "Slug schon vergeben." at the slug field on a 409', async () => {
    const conflict = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'slug_taken' },
    });
    const { api, error } = await setup(
      fakeTaxonomy({ createCategory: jest.fn(() => throwError(() => conflict)) }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Name/ }), 'Kino 2');
    await userEvent.type(screen.getByRole('textbox', { name: /Slug/ }), 'kino');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.createCategory).toHaveBeenCalled();
    expect(screen.getByText('Slug schon vergeben.')).toBeInTheDocument();
    expect(error).not.toHaveBeenCalled();
  });

  it('edits a row on click, keeps the slug read-only and patches without it', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Informatik'));
    expect(screen.queryByRole('textbox', { name: /Slug/ })).not.toBeInTheDocument();
    const name = screen.getByRole('textbox', { name: /Name/ });
    await userEvent.clear(name);
    await userEvent.type(name, 'Informatik 2');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateCategory).toHaveBeenCalledWith('fsi', {
      name: 'Informatik 2',
      kind: 'fachschaft',
      parentId: 'fs',
      short: null,
      colorToken: 'petrol',
      requiredProfile: 'generic',
      active: true,
    });
  });

  it('cancels an edit without writing', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Kino'));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(api.updateCategory).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Speichern' })).not.toBeInTheDocument();
  });

  it('shows an error note when the load fails', async () => {
    await setup(
      fakeTaxonomy({
        categories: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Daten konnten nicht geladen werden.',
    );
  });

  it('ignores a second edit while a row is open', async () => {
    await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.click(screen.getByText('Kino'));
    await userEvent.click(screen.getByRole('button', { name: 'Hinzufügen' }));
    expect(screen.getAllByRole('textbox', { name: /Name/ })).toHaveLength(1);
    expect(screen.getByRole('textbox', { name: /Slug/ })).toBeInTheDocument();
  });

  it('ignores a repeated start of the same kind', async () => {
    const { fixture } = await setup();
    const table = fixture.componentInstance as unknown as {
      startNew(): void;
      startEdit(row: unknown): void;
      editingId(): string | null;
    };
    table.startNew();
    table.startNew();
    table.startEdit(TREE[0]);
    expect(table.editingId()).toBe('new');
  });

  it('refuses a blank name and toasts a failure without a field', async () => {
    const down = new HttpErrorResponse({ status: 500, error: { status: 500, code: 'internal' } });
    const { api, error } = await setup(
      fakeTaxonomy({ updateCategory: jest.fn(() => throwError(() => down)) }),
    );
    await userEvent.click(await screen.findByText('Informatik'));
    const name = screen.getByRole('textbox', { name: /Name/ });
    await userEvent.clear(name);
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateCategory).not.toHaveBeenCalled();
    await userEvent.type(name, 'Neu');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(error).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const view = await setup();
    await screen.findByText('Informatik');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
