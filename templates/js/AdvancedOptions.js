import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

const AdvancedOptions = ({ onOptionsChange }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [lastUsedSeed, setLastUsedSeed] = useState(-1);
    const [availableModels, setAvailableModels] = useState({
        checkpoints: ['default'],  // Initialize with 'default' option
        loras: []
    });
    const [loadingError, setLoadingError] = useState(null);
    const [options, setOptions] = useState(() => {
        const savedOptions = localStorage.getItem('advancedOptions');
        return savedOptions ? JSON.parse(savedOptions) : {
            checkpointModel: 'default',
            width: 1024,
            height: 1024,
            guidance: 3,
            seed: -1,
            useLastSeed: false,
            loras: [{ name: '', strength: 1.0 }]
        };
    });

    // Fetch last used seed
    const fetchLastSeed = useCallback(async () => {
        try {
            const response = await fetch('/api/last-seed', {
                credentials: 'include'
            });
            if (!response.ok) throw new Error('Failed to fetch last seed');
            const data = await response.json();
            setLastUsedSeed(data.seed);
        } catch (error) {
            console.error('Error fetching last seed:', error);
        }
    }, []);

    // Fetch available models
    const fetchModels = useCallback(async () => {
        try {
            const response = await fetch('/api/available-models', {
                credentials: 'include'
            });
            if (!response.ok) throw new Error('Failed to fetch models');
            const data = await response.json();

            setAvailableModels({
                checkpoints: ['default', ...(data.checkpoints || [])],  // Ensure 'default' is first
                loras: data.loras || []
            });
        } catch (error) {
            console.error('Error fetching models:', error);
            setLoadingError('Failed to fetch available models');
        }
    }, []);

    // Load defaults from workflow
    const loadWorkflowDefaults = useCallback(async () => {
        const characterSelect = document.getElementById('character-select');
        if (!characterSelect) return;

        try {
            const response = await fetch(`/api/get-default-workflow?character=${characterSelect.value}`, {
                credentials: 'include'
            });
            if (!response.ok) throw new Error('Failed to fetch workflow');
            const workflow = await response.json();

            let defaultOptions = {
                checkpointModel: 'default',
                width: 1024,
                height: 1024,
                guidance: 3,
                seed: -1,
                useLastSeed: false,
                loras: []
            };

            // Extract settings from workflow
            for (const node of Object.values(workflow)) {
                if (node.inputs) {
                    if (node.inputs.width) defaultOptions.width = node.inputs.width;
                    if (node.inputs.height) defaultOptions.height = node.inputs.height;
                    if (node.inputs.guidance) defaultOptions.guidance = node.inputs.guidance;
                    if (node.inputs.seed !== undefined) defaultOptions.seed = node.inputs.seed;
                }

                // Extract LoRAs
                if (node.class_type === "Power Lora Loader (rgthree)") {
                    for (const [key, value] of Object.entries(node.inputs)) {
                        if (key.startsWith('lora_') && value && value.lora) {
                            defaultOptions.loras.push({
                                name: value.lora,
                                strength: value.strength || 1.0
                            });
                        }
                    }
                }
            }

            // Ensure at least one empty LoRA slot
            if (defaultOptions.loras.length === 0) {
                defaultOptions.loras.push({ name: '', strength: 1.0 });
            }

            setOptions(defaultOptions);
            localStorage.setItem('advancedOptions', JSON.stringify(defaultOptions));
            if (onOptionsChange) onOptionsChange(defaultOptions);

        } catch (error) {
            console.error('Error loading workflow defaults:', error);
            setLoadingError('Failed to load workflow defaults');
        }
    }, [onOptionsChange]);

    // Initial setup
    useEffect(() => {
        fetchModels();
        fetchLastSeed();
        loadWorkflowDefaults();

        const intervalId = setInterval(fetchLastSeed, 5000);
        return () => clearInterval(intervalId);
    }, [fetchLastSeed, fetchModels, loadWorkflowDefaults]);

    // Character change handler
    useEffect(() => {
        const characterSelect = document.getElementById('character-select');
        if (!characterSelect) return;

        const handleChange = () => loadWorkflowDefaults();
        characterSelect.addEventListener('change', handleChange);

        return () => characterSelect.removeEventListener('change', handleChange);
    }, [loadWorkflowDefaults]);

    // Save options when they change
    useEffect(() => {
        localStorage.setItem('advancedOptions', JSON.stringify(options));
        if (onOptionsChange) onOptionsChange(options);
    }, [options, onOptionsChange]);

    // Handler functions
    const handleLoraChange = (index, field, value) => {
        const newLoras = [...options.loras];
        newLoras[index] = { ...newLoras[index], [field]: value };
        setOptions(prev => ({ ...prev, loras: newLoras }));
    };

    const addLora = () => {
        if (options.loras.length < 5) {
            setOptions(prev => ({
                ...prev,
                loras: [...prev.loras, { name: '', strength: 1.0 }]
            }));
        }
    };

    const removeLora = (index) => {
        if (index > 0) {
            setOptions(prev => ({
                ...prev,
                loras: prev.loras.filter((_, i) => i !== index)
            }));
        }
    };

    // UI rendering
    if (loadingError) {
        return (
            <div className="w-full p-4 bg-red-500 text-white rounded-lg mb-4">
                Error: {loadingError}
            </div>
        );
    }

    if (!isExpanded) {
        return (
            <button
                className="w-full p-2 bg-gray-800 text-white rounded-lg mb-4 hover:bg-gray-700"
                onClick={() => setIsExpanded(true)}
            >
                Show Advanced Options
            </button>
        );
    }

    return (
        <div className="w-full bg-gray-800 rounded-lg p-4 mb-4">
            <div className="flex justify-between items-center mb-4">
                <button
                    onClick={() => setIsExpanded(false)}
                    className="text-white hover:bg-gray-700 px-3 py-1 rounded"
                >
                    Hide Advanced Options
                </button>
                <button
                    onClick={loadWorkflowDefaults}
                    className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700"
                >
                    Reset to Defaults
                </button>
            </div>

            <div className="space-y-4">
                <div className="space-y-2">
                    <label className="block text-white">Checkpoint Model:</label>
                    <select
                        value={options.checkpointModel}
                        onChange={(e) => setOptions(prev => ({ ...prev, checkpointModel: e.target.value }))}
                        className="w-full p-2 bg-gray-700 text-white rounded"
                    >
                        {availableModels.checkpoints.map(model => (
                            <option key={model} value={model}>
                                {model === 'default' ? 'Default Model' : model}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="space-y-2">
                    <label className="block text-white">Width:</label>
                    <input
                        type="number"
                        value={options.width}
                        onChange={(e) => setOptions(prev => ({ ...prev, width: parseInt(e.target.value) }))}
                        className="w-full p-2 bg-gray-700 text-white rounded"
                        min="512"
                        max="2048"
                        step="64"
                    />
                </div>

                <div className="space-y-2">
                    <label className="block text-white">Height:</label>
                    <input
                        type="number"
                        value={options.height}
                        onChange={(e) => setOptions(prev => ({ ...prev, height: parseInt(e.target.value) }))}
                        className="w-full p-2 bg-gray-700 text-white rounded"
                        min="512"
                        max="2048"
                        step="64"
                    />
                </div>

                <div className="space-y-2">
                    <label className="block text-white">Guidance Scale:</label>
                    <input
                        type="number"
                        value={options.guidance}
                        onChange={(e) => setOptions(prev => ({ ...prev, guidance: parseFloat(e.target.value) }))}
                        className="w-full p-2 bg-gray-700 text-white rounded"
                        min="1"
                        max="20"
                        step="0.1"
                    />
                </div>

                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={options.useLastSeed}
                            onChange={(e) => setOptions(prev => ({
                                ...prev,
                                useLastSeed: e.target.checked,
                                seed: e.target.checked ? -1 : prev.seed
                            }))}
                            className="w-4 h-4"
                        />
                        <label className="text-white">
                            Use Last Seed {lastUsedSeed !== -1 && (
                                <span className="text-blue-400 font-mono">({lastUsedSeed})</span>
                            )}
                        </label>
                    </div>
                    <input
                        type="number"
                        value={options.seed}
                        onChange={(e) => setOptions(prev => ({
                            ...prev,
                            seed: parseInt(e.target.value),
                            useLastSeed: false
                        }))}
                        disabled={options.useLastSeed}
                        className={`w-full p-2 bg-gray-700 text-white rounded ${options.useLastSeed ? 'opacity-50' : ''}`}
                        placeholder="Random Seed (-1)"
                    />
                </div>

                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <label className="text-white">Additional LoRA Models:</label>
                        <button
                            onClick={addLora}
                            disabled={options.loras.length >= 5}
                            className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            Add LoRA
                        </button>
                    </div>
                    {options.loras.map((lora, index) => (
                        <div key={`lora-${index}`} className="flex gap-2 items-end">
                            <div className="flex-1">
                                <select
                                    value={lora.name}
                                    onChange={(e) => handleLoraChange(index, 'name', e.target.value)}
                                    className="w-full p-2 bg-gray-700 text-white rounded"
                                >
                                    <option value="">Select LoRA</option>
                                    {availableModels.loras.map(loraName => (
                                        <option key={loraName} value={loraName}>{loraName}</option>
                                    ))}
                                </select>
                            </div>
                            <input
                                type="number"
                                value={lora.strength}
                                onChange={(e) => handleLoraChange(index, 'strength', parseFloat(e.target.value))}
                                className="w-24 p-2 bg-gray-700 text-white rounded"
                                min="0"
                                max="2"
                                step="0.1"
                            />
                            {index > 0 && (
                                <button
                                    onClick={() => removeLora(index)}
                                    className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700"
                                >
                                    Remove
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default AdvancedOptions;