/**
 * Picoripi Companion - Core Application & State Management
 */

const state = {
  token: localStorage.getItem('picoripi_token') || '',
  currentProject: localStorage.getItem('picoripi_project') || '',
  projects: [],
  glossaryData: null,
  activeCategory: 'All',
  needsReviewOnly: false,
  searchQuery: '',
  filteredEntries: [],
  currentTermIndex: -1,
  currentEntry: null,
  currentOccurrences: [],
};

// API Client
const api = {
  async request(endpoint, options = {}) {
    const headers = options.headers || {};
    if (state.token) {
      headers['Authorization'] = `Bearer ${state.token}`;
    }
    headers['Content-Type'] = 'application/json';

    try {
      const res = await fetch(endpoint, { ...options, headers });
      if (res.status === 401) {
        showToast('Session expired or invalid token', true);
        logout();
        throw new Error('Unauthorized');
      }
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const detail = errorData.detail;
        const error = new Error((detail && detail.message) || (typeof detail === 'string' && detail) || `HTTP Error ${res.status}`);
        error.status = res.status;
        error.detail = detail;
        throw error;
      }
      return await res.json();
    } catch (err) {
      console.error('API Error:', err);
      throw err;
    }
  },

  login(token) {
    return this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  },

  getProjects() {
    return this.request('/api/projects');
  },

  getGlossary(project, category = null, needsReview = null, search = null) {
    const params = new URLSearchParams();
    if (project) params.set('project', project);
    if (category && category !== 'All') params.set('category', category);
    if (needsReview) params.set('needs_review', 'true');
    if (search) params.set('search', search);
    return this.request(`/api/glossary?${params.toString()}`);
  },

  getTermDetail(project, term) {
    const params = new URLSearchParams({ project, term });
    return this.request(`/api/glossary/entry?${params.toString()}`);
  },

  updateTerm(project, updateData) {
    const params = new URLSearchParams({ project });
    return this.request(`/api/glossary/entry?${params.toString()}`, {
      method: 'PUT',
      body: JSON.stringify(updateData),
    });
  },
};

// Toast Notifications
function showToast(message, isError = false) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.style.background = isError ? '#ef4444' : '#334155';
  toast.classList.remove('hidden');
  toast.style.opacity = '1';

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.classList.add('hidden'), 200);
  }, 2500);
}

// UI Navigation
function switchView(viewName) {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appHeader').classList.add('hidden');
  document.getElementById('listView').classList.add('hidden');
  document.getElementById('editorView').classList.add('hidden');
  document.getElementById('stringsView').classList.add('hidden');
  document.getElementById('stringEditorView').classList.add('hidden');
  document.getElementById('modeBtn').textContent = viewName.startsWith('string') ? 'Glossary' : 'Strings';

  if (viewName === 'strings' || viewName === 'string-editor') {
    document.getElementById('appHeader').classList.remove('hidden');
    document.getElementById(viewName === 'strings' ? 'stringsView' : 'stringEditorView').classList.remove('hidden');
  } else if (viewName === 'login') {
    document.getElementById('loginScreen').classList.remove('hidden');
  } else if (viewName === 'list') {
    document.getElementById('appHeader').classList.remove('hidden');
    document.getElementById('listView').classList.remove('hidden');
  } else if (viewName === 'editor') {
    document.getElementById('appHeader').classList.remove('hidden');
    document.getElementById('editorView').classList.remove('hidden');
  }
}

// Authentication Flow
async function handleLogin(token) {
  try {
    const res = await api.login(token);
    state.token = token;
    localStorage.setItem('picoripi_token', token);
    showToast('Connected to Picoripi Companion');
    await loadInitialData();
  } catch (err) {
    document.getElementById('loginError').textContent = err.message || 'Invalid token';
  }
}

function logout() {
  state.token = '';
  localStorage.removeItem('picoripi_token');
  switchView('login');
}

// Load Initial Data
async function loadInitialData() {
  try {
    const projects = await api.getProjects();
    state.projects = projects;

    const select = document.getElementById('projectSelect');
    select.innerHTML = '';

    if (!projects || projects.length === 0) {
      select.innerHTML = '<option value="">(No projects pushed)</option>';
      switchView('list');
      document.getElementById('termsList').innerHTML =
        '<div class="loading-state">No projects found. Push a project from Picoripi Desktop!</div>';
      return;
    }

    projects.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.name;
      if (p.name === state.currentProject) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    if (!state.currentProject || !projects.some((p) => p.name === state.currentProject)) {
      state.currentProject = projects[0].name;
      localStorage.setItem('picoripi_project', state.currentProject);
    }

    switchView('list');
    await refreshGlossaryList();
  } catch (err) {
    showToast('Failed to load projects: ' + err.message, true);
  }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  // Login Form
  document.getElementById('loginForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const token = document.getElementById('tokenInput').value.trim();
    if (token) handleLogin(token);
  });

  // Logout & Refresh
  document.getElementById('logoutBtn').addEventListener('click', logout);
  document.getElementById('refreshBtn').addEventListener('click', () => {
    if (stringsMode()) refreshStrings(true);
    else refreshGlossaryList(true);
  });
  document.getElementById('modeBtn').addEventListener('click', () => {
    if (stringsMode()) {
      switchView('list');
      refreshGlossaryList();
    } else {
      switchView('strings');
      refreshStrings();
    }
  });

  // Project selector
  document.getElementById('projectSelect').addEventListener('change', (e) => {
    state.currentProject = e.target.value;
    localStorage.setItem('picoripi_project', state.currentProject);
    if (stringsMode()) {
      stringsState.block = null;
      refreshStrings();
    } else {
      refreshGlossaryList();
    }
  });

  // Check existing session
  if (state.token) {
    loadInitialData();
  } else {
    switchView('login');
  }
});
