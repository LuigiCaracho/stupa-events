/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/ui/index.ts (rewritten) */
/**
 * The shared building blocks of the app (`@shared/ui`). Rewritten from the workflow tool: only the blocks that the
 * M1 pages use. The ui-kit (`@stupa-makers/ui-kit`) holds the generic controls. These
 * blocks are specific to this app; they use its i18n and its status model.
 *
 * Exception: code in the initial bundle (the shell, the layout) imports a block by its
 * path, for example `@shared/ui/empty-state/empty-state.component`. When the initial
 * bundle imports this barrel, every block that a lazy page uses goes into it too.
 *
 * New blocks (`app-poster-upload`, ...) have their own directory here and join this barrel
 * when they exist.
 */
export { DateBlockComponent } from './date-block/date-block.component';
export { EmptyStateComponent } from './empty-state/empty-state.component';
export { FieldGroupComponent, FieldRowComponent } from './field-group/field-group.component';
export { FileDropZoneComponent, acceptsFile } from './file-drop-zone/file-drop-zone.component';
export { ImageThumbComponent, inlineUrl, isThumbImage } from './image-thumb/image-thumb.component';
export {
  LIST_DETAIL_SPLIT_MIN,
  ListDetailLayoutComponent,
  NAV_RAIL_WIDTH,
} from './list-detail/list-detail-layout.component';
export { ListItemComponent } from './list-item/list-item.component';
export { NoteComponent } from './note/note.component';
export type { NoteKind } from './note/note.component';
export { PageHeaderComponent } from './page-header/page-header.component';
export { SelectFieldComponent } from './select/select.component';
export type { SelectFieldOption } from './select/select.component';
export { SheetBarComponent, SheetBarKickerDirective } from './sheet-bar/sheet-bar.component';
export { SideSheetComponent } from './side-sheet/side-sheet.component';
export type { SheetSide } from './side-sheet/side-sheet.component';
export { SkeletonComponent } from './skeleton/skeleton.component';
export type { SkeletonVariant } from './skeleton/skeleton.component';
export { StickyBarComponent } from './sticky-bar/sticky-bar.component';
export { StatusTextComponent } from './status-text/status-text.component';
export * from '../status-kind.util';
export { PosterUploadComponent } from './poster-upload/poster-upload.component';
export type { PosterRights, PosterSubmission } from './poster-upload/poster-upload.component';
