/**
 * Picoripi Companion - Glossary List View
 */

let searchDebounceTimer = null;

async function refreshGlossaryList(notify = false) {
  if (!state.currentProject) return;

  const listEl = document.getElementById('termsList');
  if (notify) {
    listEl.innerHTML = '<div class="loading-state">Refreshing glossary...</div>';
  }

  try {
    const data = await api.getGlossary(
      state.currentProject,
      state.activeCategory,
      state.needsReviewOnly,
      state.searchQuery
    );

    state.glossaryData = data;
    state.filteredEntries = data.entries || [];

    renderCategoryPills(data.categories, data.category_counts, data.total);
    renderStats(data);
    renderTermsList(state.filteredEntries);

    if (notify) {
      showToast(`Loaded ${data.entries.length} terms`);
    }
  } catch (err) {
    listEl.innerHTML = `<div class="loading-state error-msg">Failed to load terms: ${err.message}</div>`;
  }
}

function renderCategoryPills(categories, categoryCounts, totalCount) {
  const container = document.getElementById('categoryPills');
  container.innerHTML = '';

  // "All" pill
  const allPill = document.createElement('div');
  allPill.className = `pill ${state.activeCategory === 'All' ? 'active' : ''}`;
  allPill.textContent = `All (${totalCount})`;
  allPill.addEventListener('click', () => {
    state.activeCategory = 'All';
    refreshGlossaryList();
  });
  container.appendChild(allPill);

  // Individual categories
  (categories || []).forEach((cat) => {
    const count = categoryCounts[cat] || 0;
    const pill = document.createElement('div');
    pill.className = `pill ${state.activeCategory === cat ? 'active' : ''}`;
    pill.textContent = `${cat} (${count})`;
    pill.addEventListener('click', () => {
      state.activeCategory = cat;
      refreshGlossaryList();
    });
    container.appendChild(pill);
  });
}

function renderStats(data) {
  const needsReviewBtn = document.getElementById('needsReviewToggle');
  const needsReviewCountEl = document.getElementById('needsReviewCount');
  needsReviewCountEl.textContent = data.needs_review_count || 0;

  if (state.needsReviewOnly) {
    needsReviewBtn.classList.add('active');
  } else {
    needsReviewBtn.classList.remove('active');
  }

  const confirmed = data.confirmed_count || 0;
  const total = data.total || 0;
  const percent = total > 0 ? Math.round((confirmed / total) * 100) : 0;

  document.getElementById('statsConfirmed').textContent = confirmed;
  document.getElementById('statsTotal').textContent = total;
  document.getElementById('statsPercent').textContent = `${percent}%`;
}

function renderTermsList(entries) {
  const container = document.getElementById('termsList');
  container.innerHTML = '';

  if (!entries || entries.length === 0) {
    container.innerHTML = '<div class="loading-state">No terms match your filter or search.</div>';
    return;
  }

  entries.forEach((entry, idx) => {
    const card = document.createElement('div');
    const status = (entry.status || '').toLowerCase();
    const isConfirmed = status === 'confirmed';
    const isUnconfirmed =
      ['seeded', 'fragments', 'synthesized', 'translated'].includes(status) ||
      (entry.translation_variants && entry.translation_variants.length > 1);

    card.className = `term-card ${isConfirmed ? 'confirmed' : ''} ${isUnconfirmed ? 'unconfirmed' : ''}`;

    const variantCount = entry.translation_variants ? entry.translation_variants.length : 0;

    card.innerHTML = `
      <div class="card-top">
        <span class="term-orig">${escapeHtml(entry.original)}</span>
        <div class="card-badges">
          <span class="badge badge-category">${escapeHtml(entry.section || 'General')}</span>
          ${isConfirmed ? '<span class="badge badge-success">✓</span>' : ''}
          ${isUnconfirmed ? '<span class="badge badge-warning">●</span>' : ''}
          ${variantCount > 1 ? `<span class="badge badge-count">⚡ ${variantCount}</span>` : ''}
        </div>
      </div>
      <div class="term-trans ${entry.translation ? '' : 'empty'}">
        ${entry.translation ? escapeHtml(entry.translation) : '(No translation yet)'}
      </div>
    `;

    card.addEventListener('click', () => {
      openTermEditor(idx);
    });

    container.appendChild(card);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Search and filter listeners
window.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('searchInput');
  const clearBtn = document.getElementById('searchClearBtn');
  const needsReviewToggle = document.getElementById('needsReviewToggle');

  searchInput.addEventListener('input', (e) => {
    const val = e.target.value;
    clearBtn.classList.toggle('hidden', !val);

    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      state.searchQuery = val.trim();
      refreshGlossaryList();
    }, 180);
  });

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.classList.add('hidden');
    state.searchQuery = '';
    refreshGlossaryList();
  });

  needsReviewToggle.addEventListener('click', () => {
    state.needsReviewOnly = !state.needsReviewOnly;
    refreshGlossaryList();
  });
});
