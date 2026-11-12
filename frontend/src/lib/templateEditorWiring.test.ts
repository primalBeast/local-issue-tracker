import { describe, expect, it } from 'vitest';
import appSource from '../App.svelte?raw';
import editorSource from './TemplateEditor.svelte?raw';
import canvasSource from './TemplateLayoutCanvas.svelte?raw';
import detailsSource from './FieldDetailsPanel.svelte?raw';
import listSource from './TemplateList.svelte?raw';
import previewSource from './TemplatePreview.svelte?raw';
import discardSource from './ConfirmDiscard.svelte?raw';
import columnsSource from './listColumns.ts?raw';
import fieldsSource from './templateFields.ts?raw';
import { defaultColumnOrder } from './listColumns';

describe('templates editor wiring', () => {
  it('is a modal dialog with title, ✕, backdrop, and trapped focus', () => {
    expect(editorSource).toContain('role="dialog"');
    expect(editorSource).toContain('aria-modal="true"');
    expect(editorSource).toContain('aria-labelledby="template-editor-title"');
    expect(editorSource).toContain('template-editor-backdrop');
    expect(editorSource).toContain('aria-label="Close"');
    expect(editorSource).toContain('✕');
    expect(editorSource).toContain('handleFocusTrap');
    expect(editorSource).toContain('restoreFocus');
    expect(editorSource).toContain('unsaved-dot');
  });

  it('puts Close on the left and Save as copy… then Save on the right, Save until dirty', () => {
    const footerAt = editorSource.indexOf('template-editor-footer');
    expect(footerAt).toBeGreaterThanOrEqual(0);
    const footer = editorSource.slice(footerAt, footerAt + 500);
    expect(footer.indexOf('>Close<')).toBeGreaterThanOrEqual(0);
    expect(footer.indexOf('Save as copy…')).toBeGreaterThan(footer.indexOf('>Close<'));
    expect(footer.indexOf('>Save<')).toBeGreaterThan(footer.indexOf('Save as copy…'));
    expect(editorSource).toContain('disabled={!saveOk}');
    expect(editorSource).toContain('saveEnabled');
  });

  it('keeps the layout beside details and the example on a wide window', () => {
    expect(editorSource).toContain('template-editor-canvas');
    expect(editorSource).toContain("selectFrom('canvas'");
    expect(editorSource).toContain("selectFrom('preview'");
    expect(editorSource).toContain('scrollCounterpartIntoView');
    expect(previewSource).toContain('role="button"');
    expect(previewSource).toContain('tabindex="0"');
    expect(previewSource).toContain('Select field');
    expect(previewSource).toContain('onHitKey');
    expect(previewSource).not.toContain('svelte-ignore a11y_no_static_element_interactions');
  });

  it('splits the list, canvas, and one details panel, and drops the ▾ expanders', () => {
    expect(editorSource).toContain('<TemplateList');
    expect(editorSource).toContain('<TemplateLayoutCanvas');
    expect(editorSource).toContain('<FieldDetailsPanel');
    expect(editorSource).not.toContain('expandedFields');
    expect(editorSource).not.toContain('▾');
    expect(canvasSource).not.toContain('▾');
    expect(detailsSource).not.toContain('▾');
    expect(listSource).toContain('PROJECT_FIELDS_LABEL');
    expect(listSource).toContain('BUILTIN_LABEL');
    expect(previewSource).toContain('data-field-id');
    expect(previewSource).toContain('onselect');
  });

  it('removes the All Items checkbox from the editor and keeps show_in_list for columns and save', () => {
    expect(editorSource).not.toContain('All Items');
    expect(detailsSource).not.toContain('All Items');
    expect(canvasSource).not.toContain('All Items');
    expect(editorSource).not.toContain('show_in_list');
    expect(detailsSource).not.toContain('show_in_list');
    expect(fieldsSource).toContain('show_in_list: false');
    expect(columnsSource).toContain('show_in_list');
    expect(
      defaultColumnOrder(
        [
          { id: 'ticket_key', order: 10, show_in_list: true },
          { id: 'notes', order: 60, show_in_list: false },
        ],
        true
      )
    ).toEqual(['ticket_key', '_waiting', '_updated']);
  });

  it('App leaves Esc and backdrop to the editor close guard', () => {
    const escAt = appSource.indexOf("if (templateEditorOpen)");
    expect(escAt).toBeGreaterThanOrEqual(0);
    expect(appSource).toContain('templateEditorOpen = true');
    const escRegion = appSource.slice(escAt, escAt + 80);
    expect(escRegion).not.toContain('templateEditorOpen = false');
    expect(discardSource).toContain('DISCARD_PROMPT');
    expect(discardSource).toContain('KEEP_LABEL');
    expect(editorSource).toContain('askClose');
    expect(editorSource).toContain('onBackdrop');
  });

  it('keeps TemplateEditor under the old 702-line size', () => {
    const lines = editorSource.split('\n').length;
    expect(lines).toBeLessThan(702);
  });
});
