// Wine Collection Manager - Frontend Application

const API_BASE = '/api';

// State
let wines = [];
let currentFilters = {};
let editingWineId = null;

// DOM Elements
const elements = {
    statsBar: document.getElementById('stats-bar'),
    totalBottles: document.getElementById('total-bottles'),
    readyToDrink: document.getElementById('ready-to-drink'),
    needsCellaring: document.getElementById('needs-cellaring'),
    wineGrid: document.getElementById('wine-grid'),
    searchInput: document.getElementById('search-input'),
    styleFilter: document.getElementById('style-filter'),
    countryFilter: document.getElementById('country-filter'),
    drinkingNowFilter: document.getElementById('drinking-now-filter'),
    sortSelect: document.getElementById('sort-select'),
    addWineBtn: document.getElementById('add-wine-btn'),
    wineModal: document.getElementById('wine-modal'),
    viewModal: document.getElementById('view-modal'),
    modalTitle: document.getElementById('modal-title'),
    closeModal: document.getElementById('close-modal'),
    closeViewModal: document.getElementById('close-view-modal'),
    cancelBtn: document.getElementById('cancel-btn'),
    wineForm: document.getElementById('wine-form'),
    imageInput: document.getElementById('image-input'),
    uploadArea: document.getElementById('upload-area'),
    previewImage: document.getElementById('preview-image'),
    uploadSection: document.getElementById('upload-section'),
    analyzingIndicator: document.getElementById('analyzing'),
    viewBody: document.getElementById('view-body'),
    viewTitle: document.getElementById('view-title')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadWines();
    loadStats();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    // Search and filters
    elements.searchInput.addEventListener('input', debounce(applyFilters, 300));
    elements.styleFilter.addEventListener('change', applyFilters);
    elements.countryFilter.addEventListener('change', applyFilters);
    elements.drinkingNowFilter.addEventListener('change', applyFilters);
    elements.sortSelect.addEventListener('change', applyFilters);

    // Modal controls
    elements.addWineBtn.addEventListener('click', openAddModal);
    elements.closeModal.addEventListener('click', closeModal);
    elements.closeViewModal.addEventListener('click', closeViewModal);
    elements.cancelBtn.addEventListener('click', closeModal);
    elements.wineModal.addEventListener('click', (e) => {
        if (e.target === elements.wineModal) closeModal();
    });
    elements.viewModal.addEventListener('click', (e) => {
        if (e.target === elements.viewModal) closeViewModal();
    });

    // Form submission
    elements.wineForm.addEventListener('submit', handleFormSubmit);

    // Image upload
    elements.imageInput.addEventListener('change', handleImageUpload);
}

// API Functions
async function loadWines() {
    try {
        const params = new URLSearchParams();
        if (currentFilters.search) params.set('search', currentFilters.search);
        if (currentFilters.style) params.set('style', currentFilters.style);
        if (currentFilters.country) params.set('country', currentFilters.country);
        if (currentFilters.drinkingNow) params.set('drinking_now', 'true');
        if (currentFilters.sortBy) params.set('sort_by', currentFilters.sortBy);
        if (currentFilters.sortOrder) params.set('sort_order', currentFilters.sortOrder);

        const response = await fetch(`${API_BASE}/wines?${params}`);
        wines = await response.json();
        renderWines();
        updateCountryFilter();
    } catch (error) {
        console.error('Error loading wines:', error);
        showError('Failed to load wines');
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const stats = await response.json();
        elements.totalBottles.textContent = stats.total_bottles || 0;
        elements.readyToDrink.textContent = stats.ready_to_drink || 0;
        elements.needsCellaring.textContent = stats.needs_cellaring || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function createWine(data) {
    const response = await fetch(`${API_BASE}/wines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('Failed to create wine');
    return response.json();
}

async function updateWine(id, data) {
    const response = await fetch(`${API_BASE}/wines/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('Failed to update wine');
    return response.json();
}

async function deleteWine(id) {
    const response = await fetch(`${API_BASE}/wines/${id}`, {
        method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to delete wine');
    return response.json();
}

async function analyzeImage(file) {
    const formData = new FormData();
    formData.append('image', file);

    const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData
    });
    if (!response.ok) throw new Error('Failed to analyze image');
    return response.json();
}

async function updateQuantity(id, delta) {
    const wine = wines.find(w => w.id === id);
    if (!wine) return;

    const newQuantity = Math.max(0, (wine.quantity || 0) + delta);
    await updateWine(id, { quantity: newQuantity });
    loadWines();
    loadStats();
}

// Rendering Functions
function renderWines() {
    if (wines.length === 0) {
        elements.wineGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">🍷</div>
                <h3>No wines in your collection</h3>
                <p>Click "Add Wine" to start building your collection</p>
            </div>
        `;
        return;
    }

    elements.wineGrid.innerHTML = wines.map(wine => renderWineCard(wine)).join('');

    // Add click handlers for cards
    elements.wineGrid.querySelectorAll('.wine-card').forEach(card => {
        const wineId = parseInt(card.dataset.id);
        card.addEventListener('click', (e) => {
            // Don't open modal if clicking quantity buttons
            if (e.target.closest('.quantity-btn')) return;
            openViewModal(wineId);
        });
    });

    // Add quantity button handlers
    elements.wineGrid.querySelectorAll('.quantity-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const wineId = parseInt(btn.dataset.id);
            const delta = parseInt(btn.dataset.delta);
            updateQuantity(wineId, delta);
        });
    });
}

function renderWineCard(wine) {
    const styleClass = wine.style ? `style-${wine.style.toLowerCase().replace('é', 'e')}` : '';
    const imageHtml = wine.image_path
        ? `<img src="/static/${wine.image_path}" alt="${escapeHtml(wine.name)}" class="wine-card-image">`
        : `<div class="wine-card-placeholder">🍷</div>`;

    return `
        <div class="wine-card" data-id="${wine.id}">
            ${imageHtml}
            <div class="wine-card-body">
                <div class="wine-card-name">${escapeHtml(wine.name)}</div>
                <div class="wine-card-producer">${escapeHtml(wine.producer || '')}</div>
                <div class="wine-card-meta">
                    ${wine.vintage ? `<span class="wine-tag">${wine.vintage}</span>` : ''}
                    ${wine.style ? `<span class="wine-tag ${styleClass}">${wine.style}</span>` : ''}
                    ${wine.country ? `<span class="wine-tag">${escapeHtml(wine.country)}</span>` : ''}
                </div>
            </div>
            <div class="wine-card-footer">
                <div class="wine-quantity">
                    <button class="quantity-btn" data-id="${wine.id}" data-delta="-1">−</button>
                    <span>${wine.quantity || 0} bottles</span>
                    <button class="quantity-btn" data-id="${wine.id}" data-delta="1">+</button>
                </div>
                ${wine.score ? `<span class="wine-score">${wine.score} pts</span>` : ''}
            </div>
        </div>
    `;
}

function renderWineDetails(wine) {
    const imageHtml = wine.image_path
        ? `<img src="/static/${wine.image_path}" alt="${escapeHtml(wine.name)}" class="view-wine-image">`
        : '';

    const styleClass = wine.style ? `style-${wine.style.toLowerCase().replace('é', 'e')}` : '';

    const grapes = Array.isArray(wine.grape_varieties) ? wine.grape_varieties : [];
    const tastingNotes = wine.tasting_notes || {};

    let notesHtml = '';
    if (Object.keys(tastingNotes).length > 0) {
        const notesParts = [];
        if (tastingNotes.aromas?.length) notesParts.push(`<strong>Aromas:</strong> ${tastingNotes.aromas.join(', ')}`);
        if (tastingNotes.flavors?.length) notesParts.push(`<strong>Flavors:</strong> ${tastingNotes.flavors.join(', ')}`);
        if (tastingNotes.body) notesParts.push(`<strong>Body:</strong> ${tastingNotes.body}`);
        if (tastingNotes.tannins) notesParts.push(`<strong>Tannins:</strong> ${tastingNotes.tannins}`);
        if (tastingNotes.acidity) notesParts.push(`<strong>Acidity:</strong> ${tastingNotes.acidity}`);
        if (tastingNotes.finish) notesParts.push(`<strong>Finish:</strong> ${tastingNotes.finish}`);
        if (notesParts.length > 0) {
            notesHtml = `
                <div class="view-wine-notes">
                    <strong>Tasting Notes</strong><br>
                    ${notesParts.join('<br>')}
                </div>
            `;
        }
    }

    return `
        ${imageHtml}
        <div class="view-wine-header">
            <div class="view-wine-name">${escapeHtml(wine.name)}</div>
            <div class="view-wine-producer">${escapeHtml(wine.producer || 'Unknown Producer')}</div>
        </div>
        <div class="view-wine-tags">
            ${wine.vintage ? `<span class="wine-tag">${wine.vintage}</span>` : ''}
            ${wine.style ? `<span class="wine-tag ${styleClass}">${wine.style}</span>` : ''}
            ${wine.country ? `<span class="wine-tag">${escapeHtml(wine.country)}</span>` : ''}
            ${wine.region ? `<span class="wine-tag">${escapeHtml(wine.region)}</span>` : ''}
        </div>
        <div class="view-wine-details">
            ${wine.appellation ? `<div class="view-detail"><div class="view-detail-label">Appellation</div>${escapeHtml(wine.appellation)}</div>` : ''}
            ${grapes.length ? `<div class="view-detail"><div class="view-detail-label">Grapes</div>${escapeHtml(grapes.join(', '))}</div>` : ''}
            ${wine.alcohol_percentage ? `<div class="view-detail"><div class="view-detail-label">Alcohol</div>${wine.alcohol_percentage}%</div>` : ''}
            ${wine.quantity !== undefined ? `<div class="view-detail"><div class="view-detail-label">Quantity</div>${wine.quantity} bottles</div>` : ''}
            ${wine.drinking_window_start && wine.drinking_window_end ? `<div class="view-detail"><div class="view-detail-label">Drinking Window</div>${wine.drinking_window_start} - ${wine.drinking_window_end}</div>` : ''}
            ${wine.score ? `<div class="view-detail"><div class="view-detail-label">Score</div>${wine.score} points</div>` : ''}
        </div>
        ${wine.description ? `<div class="view-wine-description">${escapeHtml(wine.description)}</div>` : ''}
        ${notesHtml}
        <div class="view-wine-actions">
            <button class="btn btn-primary" onclick="editWine(${wine.id})">Edit</button>
            <button class="btn btn-danger" onclick="confirmDeleteWine(${wine.id})">Delete</button>
        </div>
    `;
}

// Modal Functions
function openAddModal() {
    editingWineId = null;
    elements.modalTitle.textContent = 'Add Wine';
    elements.wineForm.reset();
    document.getElementById('wine-id').value = '';
    document.getElementById('image-path').value = '';
    elements.previewImage.classList.add('hidden');
    elements.previewImage.src = '';
    document.querySelector('.upload-prompt').classList.remove('hidden');
    elements.uploadSection.classList.remove('hidden');
    elements.wineModal.classList.add('active');
}

function openEditModal(wine) {
    editingWineId = wine.id;
    elements.modalTitle.textContent = 'Edit Wine';

    // Fill form
    document.getElementById('wine-id').value = wine.id;
    document.getElementById('image-path').value = wine.image_path || '';
    document.getElementById('wine-name').value = wine.name || '';
    document.getElementById('wine-producer').value = wine.producer || '';
    document.getElementById('wine-vintage').value = wine.vintage || '';
    document.getElementById('wine-style').value = wine.style || '';
    document.getElementById('wine-quantity').value = wine.quantity || 1;
    document.getElementById('wine-country').value = wine.country || '';
    document.getElementById('wine-region').value = wine.region || '';
    document.getElementById('wine-appellation').value = wine.appellation || '';
    document.getElementById('wine-grapes').value = Array.isArray(wine.grape_varieties) ? wine.grape_varieties.join(', ') : '';
    document.getElementById('wine-alcohol').value = wine.alcohol_percentage || '';
    document.getElementById('wine-drink-start').value = wine.drinking_window_start || '';
    document.getElementById('wine-drink-end').value = wine.drinking_window_end || '';
    document.getElementById('wine-score').value = wine.score || '';
    document.getElementById('wine-description').value = wine.description || '';

    // Format tasting notes
    const notes = wine.tasting_notes || {};
    const notesText = formatTastingNotesForEdit(notes);
    document.getElementById('wine-tasting-notes').value = notesText;

    // Show preview image if exists
    if (wine.image_path) {
        elements.previewImage.src = `/static/${wine.image_path}`;
        elements.previewImage.classList.remove('hidden');
        document.querySelector('.upload-prompt').classList.add('hidden');
    } else {
        elements.previewImage.classList.add('hidden');
        document.querySelector('.upload-prompt').classList.remove('hidden');
    }

    elements.uploadSection.classList.remove('hidden');
    elements.wineModal.classList.add('active');
}

function closeModal() {
    elements.wineModal.classList.remove('active');
    editingWineId = null;
}

function openViewModal(wineId) {
    const wine = wines.find(w => w.id === wineId);
    if (!wine) return;

    elements.viewTitle.textContent = wine.name;
    elements.viewBody.innerHTML = renderWineDetails(wine);
    elements.viewModal.classList.add('active');
}

function closeViewModal() {
    elements.viewModal.classList.remove('active');
}

// Form Handling
async function handleFormSubmit(e) {
    e.preventDefault();

    const grapeInput = document.getElementById('wine-grapes').value;
    const grapeVarieties = grapeInput
        ? grapeInput.split(',').map(g => g.trim()).filter(g => g)
        : [];

    const data = {
        name: document.getElementById('wine-name').value,
        producer: document.getElementById('wine-producer').value || null,
        vintage: parseInt(document.getElementById('wine-vintage').value) || null,
        style: document.getElementById('wine-style').value || null,
        quantity: parseInt(document.getElementById('wine-quantity').value) || 1,
        country: document.getElementById('wine-country').value || null,
        region: document.getElementById('wine-region').value || null,
        appellation: document.getElementById('wine-appellation').value || null,
        grape_varieties: grapeVarieties,
        alcohol_percentage: parseFloat(document.getElementById('wine-alcohol').value) || null,
        drinking_window_start: parseInt(document.getElementById('wine-drink-start').value) || null,
        drinking_window_end: parseInt(document.getElementById('wine-drink-end').value) || null,
        score: parseInt(document.getElementById('wine-score').value) || null,
        description: document.getElementById('wine-description').value || null,
        tasting_notes: parseTastingNotes(document.getElementById('wine-tasting-notes').value),
        image_path: document.getElementById('image-path').value || null
    };

    try {
        if (editingWineId) {
            await updateWine(editingWineId, data);
        } else {
            await createWine(data);
        }
        closeModal();
        loadWines();
        loadStats();
    } catch (error) {
        console.error('Error saving wine:', error);
        showError('Failed to save wine');
    }
}

async function handleImageUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        elements.previewImage.src = e.target.result;
        elements.previewImage.classList.remove('hidden');
        document.querySelector('.upload-prompt').classList.add('hidden');
    };
    reader.readAsDataURL(file);

    // Analyze with AI
    elements.analyzingIndicator.classList.remove('hidden');
    try {
        const result = await analyzeImage(file);

        if (result.error) {
            console.error('Analysis error:', result.error);
            showError(result.error);
            elements.analyzingIndicator.classList.add('hidden');
            return;
        }

        // Fill form with results
        if (result.name) document.getElementById('wine-name').value = result.name;
        if (result.producer) document.getElementById('wine-producer').value = result.producer;
        if (result.vintage) document.getElementById('wine-vintage').value = result.vintage;
        if (result.style) document.getElementById('wine-style').value = result.style;
        if (result.country) document.getElementById('wine-country').value = result.country;
        if (result.region) document.getElementById('wine-region').value = result.region;
        if (result.appellation) document.getElementById('wine-appellation').value = result.appellation;
        if (result.grape_varieties?.length) {
            document.getElementById('wine-grapes').value = result.grape_varieties.join(', ');
        }
        if (result.alcohol_percentage) document.getElementById('wine-alcohol').value = result.alcohol_percentage;
        if (result.drinking_window_start) document.getElementById('wine-drink-start').value = result.drinking_window_start;
        if (result.drinking_window_end) document.getElementById('wine-drink-end').value = result.drinking_window_end;
        if (result.score) document.getElementById('wine-score').value = result.score;
        if (result.description) document.getElementById('wine-description').value = result.description;
        if (result.tasting_notes) {
            document.getElementById('wine-tasting-notes').value = formatTastingNotesForEdit(result.tasting_notes);
        }
        if (result.image_path) document.getElementById('image-path').value = result.image_path;

    } catch (error) {
        console.error('Error analyzing image:', error);
        showError('Failed to analyze image. You can still fill in the details manually.');
    } finally {
        elements.analyzingIndicator.classList.add('hidden');
    }
}

// Filter Functions
function applyFilters() {
    const [sortBy, sortOrder] = elements.sortSelect.value.split('-');

    currentFilters = {
        search: elements.searchInput.value.trim(),
        style: elements.styleFilter.value,
        country: elements.countryFilter.value,
        drinkingNow: elements.drinkingNowFilter.checked,
        sortBy,
        sortOrder
    };

    loadWines();
}

function updateCountryFilter() {
    const countries = [...new Set(wines.map(w => w.country).filter(Boolean))].sort();
    const currentValue = elements.countryFilter.value;

    elements.countryFilter.innerHTML = '<option value="">All Countries</option>';
    countries.forEach(country => {
        const option = document.createElement('option');
        option.value = country;
        option.textContent = country;
        if (country === currentValue) option.selected = true;
        elements.countryFilter.appendChild(option);
    });
}

// Global functions for inline handlers
window.editWine = function(id) {
    closeViewModal();
    const wine = wines.find(w => w.id === id);
    if (wine) openEditModal(wine);
};

window.confirmDeleteWine = async function(id) {
    if (!confirm('Are you sure you want to delete this wine?')) return;

    try {
        await deleteWine(id);
        closeViewModal();
        loadWines();
        loadStats();
    } catch (error) {
        console.error('Error deleting wine:', error);
        showError('Failed to delete wine');
    }
};

// Utility Functions
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showError(message) {
    // Simple alert for now - could be replaced with a toast notification
    alert(message);
}

function formatTastingNotesForEdit(notes) {
    if (!notes || typeof notes !== 'object') return '';

    const parts = [];
    if (notes.aromas?.length) parts.push(`Aromas: ${notes.aromas.join(', ')}`);
    if (notes.flavors?.length) parts.push(`Flavors: ${notes.flavors.join(', ')}`);
    if (notes.body) parts.push(`Body: ${notes.body}`);
    if (notes.tannins) parts.push(`Tannins: ${notes.tannins}`);
    if (notes.acidity) parts.push(`Acidity: ${notes.acidity}`);
    if (notes.finish) parts.push(`Finish: ${notes.finish}`);
    return parts.join('\n');
}

function parseTastingNotes(text) {
    if (!text || !text.trim()) return {};

    const notes = {};
    const lines = text.split('\n');

    for (const line of lines) {
        const [key, ...valueParts] = line.split(':');
        if (!key || valueParts.length === 0) continue;

        const value = valueParts.join(':').trim();
        const keyLower = key.trim().toLowerCase();

        if (keyLower === 'aromas' || keyLower === 'flavors') {
            notes[keyLower] = value.split(',').map(v => v.trim()).filter(v => v);
        } else if (['body', 'tannins', 'acidity', 'finish'].includes(keyLower)) {
            notes[keyLower] = value;
        }
    }

    return notes;
}
