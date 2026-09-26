/**
 * Picoripi Companion - Term Editor & Review View
 */

let activeOccFilter = 'all';

async function openTermEditor(filteredIndex) {
  if (filteredIndex < 0 || filteredIndex >= state.filteredEntries.length) return;

  state.currentTermIndex = filteredIndex;
  const basicEntry = state.filteredEntries[filteredIndex];

  switchView('editor');
  renderEditorSkeleton(basicEntry);

  try {
    const detail = await api.getTermDetail(state.currentProject, basicEntry.original);
    state.currentEntry = detail.entry;
    state.currentOccurrences = detail.occurrences || [];
    renderTermDetail(detail.entry, detail.occurrences);
  } catch (err) {
    showToast('Failed to load term details: ' + err.message, true);
  }
}

function renderEditorSkeleton(entry) {
  document.getElementById('originalText').textContent = entry.original;
  document.getElementById('translationInput').value = entry.translation || '';
  document.getElementById('entryCategoryBadge').textContent = entry.section || 'General';

  const counterEl = document.getElementById('termCounter');
  counterEl.textContent = `${state.currentTermIndex + 1} / ${state.filteredEntries.length}`;

  document.getElementById('prevTermBtn').disabled = state.currentTermIndex <= 0;
  document.getElementById('nextTermBtn').disabled = state.currentTermIndex >= state.filteredEntries.length - 1;

  document.getElementById('variantsList').innerHTML = '<div class="loading-state">Loading variants...</div>';
  document.getElementById('descriptionText').textContent = 'Loading description...';
  document.getElementById('aiNotesText').textContent = '';
  document.getElementById('userNotesInput').value = entry.user_notes || '';
  document.getElementById('occurrencesList').innerHTML = '<div class="loading-state">Loading occurrences...</div>';
}

function renderTermDetail(entry, occurrences) {
  document.getElementById('originalText').textContent = entry.original;
  const transInput = document.getElementById('translationInput');
  transInput.value = entry.translation || '';
  document.getElementById('entryCategoryBadge').textContent = entry.section || 'General';

  // Status badge
  const statusBadge = document.getElementById('entryStatusBadge');
  const status = (entry.status || '').toLowerCase();
  if (status === 'confirmed') {
    statusBadge.className = 'badge badge-success';
    statusBadge.textContent = 'Confirmed';
  } else if (['seeded', 'fragments', 'synthesized', 'translated'].includes(status) || (entry.translation_variants && entry.translation_variants.length > 1)) {
    statusBadge.className = 'badge badge-warning';
    statusBadge.textContent = 'Needs review';
  } else {
    statusBadge.className = 'badge';
    statusBadge.textContent = entry.status || 'Normal';
  }

  // Wiki button
  const wikiBtn = document.getElementById('wikiLinkBtn');
  wikiBtn.onclick = () => {
    const url = `https://zelda.fandom.com/wiki/Special:Search?search=${encodeURIComponent(entry.original)}`;
    window.open(url, '_blank');
  };

  // Proposed variants
  renderVariants(entry);

  // Description lore with real-time {{TERM}} rendering
  renderLoreDescription(entry, transInput.value);

  // Notes
  document.getElementById('aiNotesText').textContent = entry.notes || '(No AI notes)';
  document.getElementById('userNotesInput').value = entry.user_notes || '';

  // Occurrences
  renderOccurrences(entry, occurrences);
}

function renderVariants(entry) {
  const container = document.getElementById('variantsList');
  const countBadge = document.getElementById('variantCountBadge');
  const variants = entry.translation_variants || [];

  countBadge.textContent = variants.length;
  container.innerHTML = '';

  if (variants.length === 0) {
    container.innerHTML = '<div class="loading-state" style="padding: 6px 0; color: var(--text-dim);">No proposed variants recorded.</div>';
    return;
  }

  variants.forEach((v) => {
    const card = document.createElement('div');
    const isReference = v.rationale && (v.rationale.includes('RU') || v.rationale.toLowerCase().includes('reference'));
    const isSelected = entry.translation && entry.translation.trim().toLowerCase() === v.translation.trim().toLowerCase();

    card.className = `variant-card ${isReference ? 'reference' : ''} ${isSelected ? 'selected' : ''}`;
    card.innerHTML = `
      <div class="variant-card-title">
        <span>${escapeHtml(v.translation)}</span>
        ${isReference ? '<span class="badge" style="background: rgba(56,189,248,0.2); color:#38bdf8;">RU Ref</span>' : ''}
        ${isSelected ? '<span style="color: var(--accent-confirm); font-size: 0.85rem;">✓ Active</span>' : ''}
      </div>
      ${v.rationale ? `<div class="variant-rationale">${escapeHtml(v.rationale)}</div>` : ''}
    `;

    card.addEventListener('click', () => {
      const transInput = document.getElementById('translationInput');
      transInput.value = v.translation;
      // Mark as selected visually
      container.querySelectorAll('.variant-card').forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
      // Update lore description in real-time
      renderLoreDescription(entry, v.translation);
    });

    container.appendChild(card);
  });
}

function renderLoreDescription(entry, activeTranslation) {
  const descEl = document.getElementById('descriptionText');
  let rawText = '';

  if (entry.fragments && entry.fragments.length > 0) {
    rawText = entry.fragments.map((f) => f.text).join('\n\n');
  } else if (entry.notes) {
    rawText = entry.notes;
  }

  if (!rawText) {
    descEl.textContent = 'No lore description available.';
    return;
  }

  const termReplacement = (activeTranslation || '').trim() || entry.original;
  // Substitute {{TERM}} or {TERM}
  let rendered = rawText
    .replace(/\{\{TERM\}\}/g, `<mark>${escapeHtml(termReplacement)}</mark>`)
    .replace(/\{TERM\}/g, `<mark>${escapeHtml(termReplacement)}</mark>`);

  descEl.innerHTML = rendered.replace(/\n/g, '<br>');
}

function renderOccurrences(entry, occurrences) {
  const container = document.getElementById('occurrencesList');
  const countBadge = document.getElementById('occCountBadge');
  countBadge.textContent = occurrences.length;

  container.innerHTML = '';
  if (!occurrences || occurrences.length === 0) {
    container.innerHTML = '<div class="loading-state">No occurrences indexed.</div>';
    return;
  }

  const filtered = occurrences.filter((occ) => {
    if (activeOccFilter === 'spoken') return occ.kind === 'spoken';
    if (activeOccFilter === 'mentions') return occ.kind === 'mention';
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="loading-state">No occurrences match the selected filter.</div>';
    return;
  }

  filtered.forEach((occ) => {
    const card = document.createElement('div');
    card.className = 'occ-card';

    // Highlight original term in EN line
    const regex = new RegExp(`(${escapeRegex(entry.original)})`, 'gi');
    const highlightedEn = escapeHtml(occ.line_text || '').replace(regex, '<mark>$1</mark>');

    // Highlight in RU reference line if present
    let ruBlock = '';
    if (occ.ref_text) {
      ruBlock = `<div class="occ-line-ru">RU: ${escapeHtml(occ.ref_text)}</div>`;
    }

    card.innerHTML = `
      <div class="occ-speaker">${escapeHtml(occ.speaker || (occ.kind === 'spoken' ? entry.original : 'Speaker'))} [${occ.kind || 'mention'}]</div>
      <div class="occ-line-en">EN: ${highlightedEn}</div>
      ${ruBlock}
    `;

    container.appendChild(card);
  });
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Saving and Confirming
async function saveActiveTerm(advance = false) {
  if (!state.currentEntry) return;

  const translation = document.getElementById('translationInput').value.trim();
  const userNotes = document.getElementById('userNotesInput').value.trim();
  const newStatus = advance ? 'confirmed' : state.currentEntry.status || '';

  const payload = {
    original: state.currentEntry.original,
    translation: translation,
    status: newStatus,
    user_notes: userNotes,
  };

  try {
    const res = await api.updateTerm(state.currentProject, payload);
    state.currentEntry = res.entry;

    // Update in filteredEntries list as well
    if (state.filteredEntries[state.currentTermIndex]) {
      Object.assign(state.filteredEntries[state.currentTermIndex], res.entry);
    }

    if (advance) {
      showToast(`✓ Confirmed: ${state.currentEntry.original}`);
      // Advance to next term
      navigateToNextTerm();
    } else {
      showToast(`Saved ${state.currentEntry.original}`);
      // Refresh current view details
      renderTermDetail(state.currentEntry, state.currentOccurrences);
    }
  } catch (err) {
    showToast('Failed to save term: ' + err.message, true);
  }
}

function navigateToNextTerm() {
  if (state.currentTermIndex < state.filteredEntries.length - 1) {
    openTermEditor(state.currentTermIndex + 1);
  } else {
    // Reached the end of filtered list
    showToast('🎉 All filtered terms reviewed!');
    switchView('list');
    refreshGlossaryList();
  }
}

function navigateToPrevTerm() {
  if (state.currentTermIndex > 0) {
    openTermEditor(state.currentTermIndex - 1);
  }
}

// Event Listeners for Editor
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('backToListBtn').addEventListener('click', () => {
    switchView('list');
    refreshGlossaryList();
  });

  document.getElementById('prevTermBtn').addEventListener('click', navigateToPrevTerm);
  document.getElementById('nextTermBtn').addEventListener('click', navigateToNextTerm);

  // Copy original button
  document.getElementById('copyOrigBtn').addEventListener('click', async () => {
    const orig = document.getElementById('originalText').textContent;
    try {
      await navigator.clipboard.writeText(orig);
      showToast('Copied to clipboard');
    } catch {
      showToast('Copy failed');
    }
  });

  // Real-time {{TERM}} update as user types translation
  document.getElementById('translationInput').addEventListener('input', (e) => {
    if (state.currentEntry) {
      renderLoreDescription(state.currentEntry, e.target.value);
    }
  });

  // Action Buttons
  document.getElementById('confirmNextBtn').addEventListener('click', () => saveActiveTerm(true));
  document.getElementById('saveTermBtn').addEventListener('click', () => saveActiveTerm(false));

  // Accordion Toggles
  ['desc', 'notes', 'occ'].forEach((id) => {
    const header = document.getElementById(`${id}Header`);
    if (header) {
      header.addEventListener('click', () => {
        header.parentElement.classList.toggle('open');
      });
    }
  });

  // Occurrences Filters
  const occChips = {
    all: document.getElementById('occFilterAll'),
    spoken: document.getElementById('occFilterSpoken'),
    mentions: document.getElementById('occFilterMentions'),
  };

  Object.entries(occChips).forEach(([key, btn]) => {
    if (btn) {
      btn.addEventListener('click', () => {
        activeOccFilter = key;
        Object.values(occChips).forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        if (state.currentEntry) {
          renderOccurrences(state.currentEntry, state.currentOccurrences);
        }
      });
    }
  });
});
