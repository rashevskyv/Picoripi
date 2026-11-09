/**
 * Picoripi Companion - translation rows: block list, row list and the row editor.
 *
 * A save sends the text this page showed as `base`. When the PC pushed another text meanwhile, the server
 * answers 409 and the page shows both texts; the phone text stays in the field until the user chooses.
 */

const stringsState = {
  blocks: [],
  block: null,       // block number, or '' for every block
  only: '',          // '', 'untranslated' or 'changed'
  search: '',
  rows: [],
  index: -1,
  base: '',          // the server text the open row was loaded with
};

let stringSearchTimer = null;

function stringsMode() {
  return !document.getElementById('stringsView').classList.contains('hidden') ||
    !document.getElementById('stringEditorView').classList.contains('hidden');
}

function stringsQuery(params) {
  return new URLSearchParams({ project: state.currentProject, ...params }).toString();
}

async function refreshStrings(notify = false) {
  if (!state.currentProject) return;
  const listEl = document.getElementById('stringsList');
  try {
    const data = await api.request(`/api/strings/blocks?${stringsQuery({})}`);
    stringsState.blocks = data.blocks || [];
    if (!stringsState.blocks.length) {
      listEl.innerHTML = '<div class="loading-state">No rows yet. In Picoripi, run Tools → Sync Translation with Companion.</div>';
      document.getElementById('blockSelect').innerHTML = '';
      document.getElementById('stringsStats').textContent = '';
      return;
    }
    if (stringsState.block === null || (stringsState.block !== '' &&
        !stringsState.blocks.some((b) => b.block === stringsState.block))) {
      stringsState.block = stringsState.blocks[0].block;
    }
    renderBlockSelect();
    await refreshStringRows();
    if (notify) showToast(`Loaded ${stringsState.rows.length} rows`);
  } catch (err) {
    listEl.innerHTML = `<div class="loading-state error-msg">Failed to load rows: ${escapeHtml(err.message)}</div>`;
  }
}

function renderBlockSelect() {
  const select = document.getElementById('blockSelect');
  select.innerHTML = '';
  const all = document.createElement('option');
  all.value = '';
  all.textContent = 'All blocks';
  select.appendChild(all);
  let total = 0, untranslated = 0, changed = 0;
  stringsState.blocks.forEach((b) => {
    total += b.total; untranslated += b.untranslated; changed += b.changed;
    const opt = document.createElement('option');
    opt.value = String(b.block);
    const marks = b.changed ? ` ✎${b.changed}` : '';
    opt.textContent = `${b.name} (${b.total - b.untranslated}/${b.total})${marks}`;
    select.appendChild(opt);
  });
  select.value = String(stringsState.block);
  document.getElementById('stringsStats').textContent =
    `Translated: ${total - untranslated} / ${total} · changed on phone: ${changed}`;
}

async function refreshStringRows() {
  const params = { only: stringsState.only, search: stringsState.search };
  if (stringsState.block !== '') params.block = String(stringsState.block);
  const data = await api.request(`/api/strings?${stringsQuery(params)}`);
  stringsState.rows = data.rows || [];
  renderStringRows(data.total || 0);
}

function renderStringRows(total) {
  const container = document.getElementById('stringsList');
  container.innerHTML = '';
  if (!stringsState.rows.length) {
    container.innerHTML = '<div class="loading-state">No rows match your filter or search.</div>';
    return;
  }
  stringsState.rows.forEach((row, idx) => {
    const changed = row.translation !== row.base;
    const untranslated = row.translation === row.original;
    const card = document.createElement('div');
    card.className = `term-card string-card ${changed ? 'unconfirmed' : ''} ${untranslated ? '' : 'confirmed'}`;
    card.innerHTML = `
      <div class="card-top">
        <span class="badge badge-count">${row.string + 1}</span>
        ${changed ? '<span class="badge badge-warning">✎ phone</span>' : ''}
      </div>
      <div class="string-text string-orig">${escapeHtml(row.original)}</div>
      <div class="string-text term-trans ${untranslated ? 'empty' : ''}">${untranslated ? '(not translated)' : escapeHtml(row.translation)}</div>
    `;
    card.addEventListener('click', () => openStringEditor(idx));
    container.appendChild(card);
  });
  if (total > stringsState.rows.length) {
    const more = document.createElement('div');
    more.className = 'loading-state';
    more.textContent = `Showing ${stringsState.rows.length} of ${total}. Pick a block or search to narrow it.`;
    container.appendChild(more);
  }
}

function openStringEditor(idx) {
  if (idx < 0 || idx >= stringsState.rows.length) return;
  stringsState.index = idx;
  const row = stringsState.rows[idx];
  stringsState.base = row.translation;
  const block = stringsState.blocks.find((b) => b.block === row.block);
  document.getElementById('stringBlockBadge').textContent = `${block ? block.name : '#' + row.block} · ${row.string + 1}`;
  document.getElementById('stringChangedBadge').classList.toggle('hidden', row.translation === row.base);
  document.getElementById('stringOriginal').textContent = row.original;
  document.getElementById('stringTranslationInput').value = row.translation;
  document.getElementById('stringConflict').classList.add('hidden');
  document.getElementById('stringCounter').textContent = `${idx + 1} / ${stringsState.rows.length}`;
  switchView('string-editor');
}

async function saveString(goNext) {
  const row = stringsState.rows[stringsState.index];
  if (!row) return;
  const text = document.getElementById('stringTranslationInput').value;
  if (text === stringsState.base) {
    if (goNext) openStringEditor(stringsState.index + 1);
    return;
  }
  try {
    const res = await api.request(`/api/strings/entry?${stringsQuery({})}`, {
      method: 'PUT',
      body: JSON.stringify({ key: row.key, translation: text, base: stringsState.base }),
    });
    stringsState.rows[stringsState.index] = res.row;
    stringsState.base = res.row.translation;
    document.getElementById('stringConflict').classList.add('hidden');
    document.getElementById('stringChangedBadge').classList.toggle('hidden', res.row.translation === res.row.base);
    showToast('Saved');
    if (goNext && stringsState.index + 1 < stringsState.rows.length) openStringEditor(stringsState.index + 1);
  } catch (err) {
    if (err.status === 409 && err.detail && err.detail.row) {
      showStringConflict(err.detail.row);
    } else {
      showToast('Save failed: ' + err.message, true);
    }
  }
}

function showStringConflict(serverRow) {
  // Nothing is lost: the phone text stays in the field, the PC text is shown under it.
  stringsState.rows[stringsState.index] = serverRow;
  stringsState.base = serverRow.translation;
  document.getElementById('stringConflictPc').textContent = serverRow.translation;
  document.getElementById('stringConflict').classList.remove('hidden');
  showToast('The text changed on the PC. Choose one.', true);
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('blockSelect').addEventListener('change', (e) => {
    stringsState.block = e.target.value === '' ? '' : Number(e.target.value);
    refreshStringRows();
  });
  document.getElementById('stringSearchInput').addEventListener('input', (e) => {
    clearTimeout(stringSearchTimer);
    stringSearchTimer = setTimeout(() => {
      stringsState.search = e.target.value.trim();
      refreshStringRows();
    }, 250);
  });
  document.querySelectorAll('#stringFilterPills .pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#stringFilterPills .pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      stringsState.only = pill.dataset.only;
      refreshStringRows();
    });
  });
  document.getElementById('backToStringsBtn').addEventListener('click', () => {
    switchView('strings');
    refreshStrings();
  });
  document.getElementById('prevStringBtn').addEventListener('click', () => openStringEditor(stringsState.index - 1));
  document.getElementById('nextStringBtn').addEventListener('click', () => openStringEditor(stringsState.index + 1));
  document.getElementById('saveStringBtn').addEventListener('click', () => saveString(false));
  document.getElementById('saveNextStringBtn').addEventListener('click', () => saveString(true));
  document.getElementById('keepMineBtn').addEventListener('click', () => saveString(false));
  document.getElementById('takePcBtn').addEventListener('click', () => {
    document.getElementById('stringTranslationInput').value = stringsState.base;
    document.getElementById('stringConflict').classList.add('hidden');
  });
  document.getElementById('copyStringOrigBtn').addEventListener('click', () => {
    const text = document.getElementById('stringOriginal').textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(() => showToast('Copied'));
  });
});
