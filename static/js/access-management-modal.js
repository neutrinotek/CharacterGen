class AccessManagementModal {
    constructor() {
        this.modal = null;
        this.currentUserId = null;
        this.currentTab = 'checkpoints';
        this.modelData = null;
        this.characterData = null;
        this.createModal();
        this.addEventListeners();
    }

    createModal() {
        const modalHTML = `
            <div id="accessManagementModal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-50">
                <div class="bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 min-h-[50vh] border-2 border-blue-500" style="max-height: 90vh;">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-white">Access Management</h2>
                        <button id="closeModalBtn" class="text-gray-400 hover:text-white text-xl">×</button>
                    </div>

                    <div class="mb-4">
                        <div class="flex border-b border-gray-700">
                            <button class="tab-button px-4 py-2 text-white border-b-2 border-blue-500" data-tab="checkpoints">
                                Checkpoints
                            </button>
                            <button class="tab-button px-4 py-2 text-gray-400 hover:text-white" data-tab="loras">
                                LoRAs
                            </button>
                            <button class="tab-button px-4 py-2 text-gray-400 hover:text-white" data-tab="characters">
                                Characters
                            </button>
                        </div>
                    </div>

                    <div id="checkpointsTab" class="tab-content bg-gray-900 p-4 rounded" style="min-height: 300px;">
                        <div class="mb-4">
                            <label class="inline-flex items-center text-white">
                                <input type="checkbox" id="selectAllCheckpoints" class="mr-2">
                                <span class="select-none">Select All Checkpoints</span>
                            </label>
                        </div>
                        <div id="checkpointsList" class="space-y-2 max-h-[50vh] overflow-y-auto">
                        </div>
                    </div>

                    <div id="lorasTab" class="tab-content hidden bg-gray-900 p-4 rounded" style="min-height: 300px;">
                        <div class="mb-4">
                            <label class="inline-flex items-center text-white">
                                <input type="checkbox" id="selectAllLoras" class="mr-2">
                                <span class="select-none">Select All LoRAs</span>
                            </label>
                        </div>
                        <div id="lorasList" class="space-y-2 max-h-[50vh] overflow-y-auto">
                        </div>
                    </div>

                    <div id="charactersTab" class="tab-content hidden bg-gray-900 p-4 rounded" style="min-height: 300px;">
                        <div class="mb-4">
                            <div class="grid grid-cols-3 gap-4 text-white font-bold">
                                <div>Character</div>
                                <div class="text-center">Generate</div>
                                <div class="text-center">Browse</div>
                            </div>
                        </div>
                        <div id="charactersList" class="space-y-2 max-h-[50vh] overflow-y-auto">
                        </div>
                    </div>

                    <div class="flex justify-end mt-4 space-x-2">
                        <button id="cancelModalBtn" class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">
                            Cancel
                        </button>
                        <button id="saveChangesBtn" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('accessManagementModal');
    }

    addEventListeners() {
        document.getElementById('closeModalBtn').addEventListener('click', () => this.hide());
        document.getElementById('cancelModalBtn').addEventListener('click', () => this.hide());
        document.getElementById('saveChangesBtn').addEventListener('click', () => this.saveChanges());

        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        document.getElementById('selectAllCheckpoints').addEventListener('change', (e) =>
            this.handleSelectAll('checkpoints', e.target.checked));

        document.getElementById('selectAllLoras').addEventListener('change', (e) =>
            this.handleSelectAll('loras', e.target.checked));
    }

    async show(userId) {
        this.currentUserId = userId;
        this.modal.classList.remove('hidden');
        this.modal.classList.add('flex');
        await this.loadPermissions();
    }

    hide() {
        this.modal.classList.add('hidden');
        this.modal.classList.remove('flex');
        this.currentUserId = null;
        this.modelData = null;
        this.characterData = null;
    }

    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab buttons
        document.querySelectorAll('.tab-button').forEach(button => {
            const isActive = button.dataset.tab === tabName;
            button.classList.toggle('text-white', isActive);
            button.classList.toggle('border-b-2', isActive);
            button.classList.toggle('border-blue-500', isActive);
            button.classList.toggle('text-gray-400', !isActive);
        });

        // Update content visibility
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        document.getElementById(`${tabName}Tab`).classList.remove('hidden');

        // Render appropriate content
        if (tabName === 'checkpoints' || tabName === 'loras') {
            this.renderModels(tabName);
        } else if (tabName === 'characters') {
            this.renderCharacters();
        }
    }

    async loadPermissions() {
        try {
            // Load both model and character permissions
            const [modelResponse, charResponse] = await Promise.all([
                fetch(`/admin/api/user/${this.currentUserId}/models`, {
                    credentials: 'include'
                }),
                fetch(`/admin/api/user/${this.currentUserId}/characters`, {
                    credentials: 'include'
                })
            ]);

            if (!modelResponse.ok || !charResponse.ok) {
                throw new Error('Failed to load permissions');
            }

            this.modelData = await modelResponse.json();
            this.characterData = await charResponse.json();

            // Initial render
            this.switchTab('checkpoints');
        } catch (error) {
            console.error('Error loading permissions:', error);
            alert('Error loading permissions: ' + error.message);
        }
    }

    renderModels(type) {
        if (!this.modelData) return;

        const listElement = document.getElementById(`${type}List`);
        const models = this.modelData[type] || [];

        listElement.innerHTML = '';
        models.forEach(model => {
            listElement.innerHTML += `
                <div class="flex items-center gap-2 p-2 text-white border-b border-gray-700">
                    <input type="checkbox"
                           class="${type === 'checkpoints' ? 'checkpoint-checkbox' : 'lora-checkbox'}"
                           data-model="${model.name}"
                           ${model.enabled ? 'checked' : ''}
                           style="width: 16px; height: 16px;">
                    <span class="text-sm flex-1">${model.name}</span>
                </div>
            `;
        });

        this.updateSelectAllState(type);
    }

    renderCharacters() {
        if (!this.characterData) return;

        const listElement = document.getElementById('charactersList');
        listElement.innerHTML = '';

        this.characterData.forEach(char => {
            listElement.innerHTML += `
                <div class="grid grid-cols-3 gap-4 items-center p-2 text-white border-b border-gray-700">
                    <div class="text-sm">${char.name}</div>
                    <div class="flex justify-center">
                        <input type="checkbox"
                               class="character-generate"
                               data-character="${char.name}"
                               ${char.can_generate ? 'checked' : ''}>
                    </div>
                    <div class="flex justify-center">
                        <input type="checkbox"
                               class="character-browse"
                               data-character="${char.name}"
                               ${char.can_browse ? 'checked' : ''}>
                    </div>
                </div>
            `;
        });
    }

    handleSelectAll(type, checked) {
        const selector = type === 'checkpoints' ? '.checkpoint-checkbox' : '.lora-checkbox';
        document.querySelectorAll(selector).forEach(checkbox => {
            checkbox.checked = checked;
        });
    }

    updateSelectAllState(type) {
        const selector = type === 'checkpoints' ? '.checkpoint-checkbox' : '.lora-checkbox';
        const selectAllCheckbox = document.getElementById(`selectAll${type.charAt(0).toUpperCase() + type.slice(1)}`);
        const checkboxes = document.querySelectorAll(selector);

        if (checkboxes.length > 0) {
            selectAllCheckbox.checked = Array.from(checkboxes).every(cb => cb.checked);
        }
    }

    async saveChanges() {
        try {
            const modelPermissions = {
                checkpoints: Array.from(document.querySelectorAll('.checkpoint-checkbox'))
                    .map(cb => ({
                        name: cb.dataset.model,
                        enabled: cb.checked
                    })),
                loras: Array.from(document.querySelectorAll('.lora-checkbox'))
                    .map(cb => ({
                        name: cb.dataset.model,
                        enabled: cb.checked
                    }))
            };

            const characterPermissions = Array.from(document.querySelectorAll('#charactersList > div'))
                .map(row => ({
                    name: row.querySelector('[data-character]').dataset.character,
                    can_generate: row.querySelector('.character-generate').checked,
                    can_browse: row.querySelector('.character-browse').checked
                }));

            // Save both model and character permissions
            await Promise.all([
                fetch(`/admin/api/user/${this.currentUserId}/models`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(modelPermissions),
                    credentials: 'include'
                }),
                fetch(`/admin/api/user/${this.currentUserId}/characters`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(characterPermissions),
                    credentials: 'include'
                })
            ]);

            this.hide();
            window.location.reload();
        } catch (error) {
            console.error('Error saving permissions:', error);
            alert('Error saving changes: ' + error.message);
        }
    }
}

// Initialize the modal
document.addEventListener('DOMContentLoaded', function() {
    const modal = new AccessManagementModal();

    // Add click handlers to access management buttons
    document.querySelectorAll('[data-action="access_management"]').forEach(button => {
        button.addEventListener('click', function(e) {
            const userId = this.dataset.userid;
            modal.show(userId);
        });
    });
});