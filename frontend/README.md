# STUPA Events Frontend

Angular 20 SPA (standalone, OnPush, signals, strict TS) on the `@stupa-makers/ui-kit` design system.
The app frame, auth, i18n (DE), theme and PWA update flow are copied from STUPA-Workflow@93c33d6
(see `../PROVENANCE.frontend.json`); pages live in `src/app/features/**` and `src/app/pages/**`.

## Commands

| Goal | Command |
|---|---|
| Install | `npm ci` (after `git submodule update --init`) |
| Dev server (proxy `/api` to `localhost:8000`) | `npm start` |
| Unit tests | `npm test` |
| Lint / types | `npm run lint` / `npm run typecheck` |
| Production build | `npm run build` |

## Layout

- `src/app/core/`: `auth` (OIDC session via `/api/auth/me`, guards, CSRF interceptor), `i18n`
  (DE only until stage B), `theme`, `cache`, `loading`, `pwa` (update prompt), `api` (shell endpoints, Problem+JSON).
- `src/app/layout/`: `ShellComponent` with the frames `rail`, `public`, `bare`, `pending`; nav rail, bottom bar, public header.
- `src/app/shared/ui/`: blocks copied from the workflow tool. New blocks (guard list, poster upload) land here.
- `src/app/feature-routes.ts`: Aufgaben and Dossiers routes. They show a placeholder until a feature replaces
  `loadComponent` with `loadChildren: () => import('./features/<area>/<area>.routes')`.
- `src/app/core/i18n/translations.events.de.ts`: German strings of the feature pages.

## Rules

- No external requests: fonts come from the kit (`/assets/fonts`), no CDN.
- UI strings German, Du-form, gendern mit Doppelpunkt or neutral. Keys `<area>.<name>`.
- Never a native `<select>` (`no-native-select.contract.spec.ts`), never `user-scalable=no`.
- The logos in `src/assets/logos` are the STUPA CD marks of the workflow tool; replace them when the Events branding exists.
