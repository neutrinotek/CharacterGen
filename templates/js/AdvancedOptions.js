const AdvancedOptions = ({ onOptionsChange }) => {
    const [isExpanded, setIsExpanded] = React.useState(false);
    const [lastUsedSeed, setLastUsedSeed] = React.useState(-1);
    const [availableModels, setAvailableModels] = React.useState({
        checkpoints: [],
        loras: []
    });
    const [options, setOptions] = React.useState(() => {
        // Try to load saved options from localStorage
        const savedOptions = localStorage.getItem('advancedOptions');
        return savedOptions ? JSON.parse(savedOptions) : {
            checkpointModel: 'NewReality-Flux.safetensors',
            width: 1024,
            height: 1024,
            guidance: 3,
            seed: -1,
            useLastSeed: false,
            loras: [{ name: '', strength: 1.0 }]
        };
    });

    // Function to fetch the last seed
    const fetchLastSeed = React.useCallback(async () => {
        try {
            const response = await fetch('/api/last-seed');
            const data = await response.json();
            console.log('Last used seed:', data.seed);
            setLastUsedSeed(data.seed);
        } catch (error) {
            console.error('Error fetching last seed:', error);
        }
    }, []);

    // Function to update workflow options on the server
    const updateWorkflowOptions = async (currentOptions) => {
        try {
            const characterSelect = document.getElementById('character-select');
            if (!characterSelect) return;

            console.log('Sending workflow options update:', {
                character: characterSelect.value,
                options: currentOptions
            });

            const response = await fetch('/api/workflow-options', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    character: characterSelect.value,
                    options: currentOptions
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error('Failed to update workflow options');
            }
        } catch (error) {
            console.error('Error updating workflow options:', error);
        }
    };

    // Fetch available models and last seed when component mounts
    React.useEffect(() => {
        // Fetch models
        fetch('/api/available-models')
            .then(response => response.json())
            .then(data => {
                console.log('Available models:', data);
                setAvailableModels(data);
                if (data.checkpoints.length > 0 && !localStorage.getItem('advancedOptions')) {
                    setOptions(prev => ({
                        ...prev,
                        checkpointModel: data.checkpoints[0]
                    }));
                }
            })
            .catch(error => console.error('Error fetching models:', error));

        // Initial fetch of last seed
        fetchLastSeed();

        // Set up an interval to periodically check for new seeds
        const intervalId = setInterval(fetchLastSeed, 5000);

        // Cleanup interval on unmount
        return () => clearInterval(intervalId);
    }, [fetchLastSeed]);

    // Update parent component and workflow when options change
    React.useEffect(() => {
        localStorage.setItem('advancedOptions', JSON.stringify(options));
        if (onOptionsChange) {
            onOptionsChange(options);
        }
        updateWorkflowOptions(options);
    }, [options, onOptionsChange]);

    const handleLoraChange = (index, field, value) => {
        const newLoras = [...options.loras];
        newLoras[index] = { ...newLoras[index], [field]: value };
        setOptions({ ...options, loras: newLoras });
    };

    const addLora = () => {
        if (options.loras.length < 5) {
            setOptions({
                ...options,
                loras: [...options.loras, { name: '', strength: 1.0 }]
            });
        }
    };

    const removeLora = (index) => {
        if (index > 0) { // Don't remove the first LoRA
            const newLoras = options.loras.filter((_, i) => i !== index);
            setOptions({ ...options, loras: newLoras });
        }
    };

    const handleSeedChange = (useLastSeed) => {
        setOptions(prev => ({
            ...prev,
            useLastSeed,
            // When enabling "Use Last Seed", we don't need to set the seed value
            // as it will be read from the file during workflow generation
            seed: useLastSeed ? -1 : prev.seed
        }));
    };

    const resetToDefaults = async () => {
        const characterSelect = document.getElementById('character-select');
        const character = characterSelect.value;

        try {
            const response = await fetch(`/api/get-default-workflow?character=${character}`);
            const defaultWorkflow = await response.json();

            const defaultOptions = {
                checkpointModel: defaultWorkflow['4'].inputs.ckpt_name,
                width: defaultWorkflow['5'].inputs.width,
                height: defaultWorkflow['5'].inputs.height,
                guidance: defaultWorkflow['16'].inputs.guidance,
                seed: defaultWorkflow['25'].inputs.seed,
                useLastSeed: false,
                loras: [{ name: '', strength: 1.0 }]
            };

            setOptions(defaultOptions);
            localStorage.setItem('advancedOptions', JSON.stringify(defaultOptions));
            await updateWorkflowOptions(defaultOptions);
        } catch (error) {
            console.error('Error resetting to defaults:', error);
        }
    };

    if (!isExpanded) {
        return React.createElement('button', {
            className: 'w-full p-2 bg-gray-800 text-white rounded-lg mb-4 hover:bg-gray-700',
            onClick: () => setIsExpanded(true)
        }, 'Show Advanced Options');
    }

    return React.createElement('div', {
        className: 'w-full bg-gray-800 rounded-lg p-4 mb-4'
    }, [
        // Header with Hide and Reset buttons
        React.createElement('div', {
            key: 'header',
            className: 'flex justify-between items-center mb-4'
        }, [
            React.createElement('button', {
                onClick: () => setIsExpanded(false),
                className: 'text-white hover:bg-gray-700 px-3 py-1 rounded'
            }, 'Hide Advanced Options'),
            React.createElement('button', {
                onClick: resetToDefaults,
                className: 'px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700'
            }, 'Reset to Defaults')
        ]),

        // Options container
        React.createElement('div', {
            key: 'content',
            className: 'space-y-4'
        }, [
            // Checkpoint Model Select
            React.createElement('div', { key: 'model', className: 'space-y-2' }, [
                React.createElement('label', { className: 'block text-white' }, 'Checkpoint Model:'),
                React.createElement('select', {
                    value: options.checkpointModel,
                    onChange: (e) => setOptions({ ...options, checkpointModel: e.target.value }),
                    className: 'w-full p-2 bg-gray-700 text-white rounded'
                }, availableModels.checkpoints.map(model =>
                    React.createElement('option', { key: model, value: model }, model)
                ))
            ]),

            // Width Input
            React.createElement('div', { key: 'width', className: 'space-y-2' }, [
                React.createElement('label', { className: 'block text-white' }, 'Width:'),
                React.createElement('input', {
                    type: 'number',
                    value: options.width,
                    onChange: (e) => setOptions({ ...options, width: parseInt(e.target.value) }),
                    className: 'w-full p-2 bg-gray-700 text-white rounded',
                    min: '512',
                    max: '2048',
                    step: '64'
                })
            ]),

            // Height Input
            React.createElement('div', { key: 'height', className: 'space-y-2' }, [
                React.createElement('label', { className: 'block text-white' }, 'Height:'),
                React.createElement('input', {
                    type: 'number',
                    value: options.height,
                    onChange: (e) => setOptions({ ...options, height: parseInt(e.target.value) }),
                    className: 'w-full p-2 bg-gray-700 text-white rounded',
                    min: '512',
                    max: '2048',
                    step: '64'
                })
            ]),

            // Guidance Scale Input
            React.createElement('div', { key: 'guidance', className: 'space-y-2' }, [
                React.createElement('label', { className: 'block text-white' }, 'Guidance Scale:'),
                React.createElement('input', {
                    type: 'number',
                    value: options.guidance,
                    onChange: (e) => setOptions({ ...options, guidance: parseFloat(e.target.value) }),
                    className: 'w-full p-2 bg-gray-700 text-white rounded',
                    min: '1',
                    max: '20',
                    step: '0.1'
                })
            ]),

            // Seed Section
            React.createElement('div', { key: 'seed', className: 'space-y-2' }, [
                React.createElement('div', { className: 'flex items-center gap-2' }, [
                    React.createElement('input', {
                        type: 'checkbox',
                        checked: options.useLastSeed,
                        onChange: (e) => handleSeedChange(e.target.checked),
                        className: 'w-4 h-4'
                    }),
                    React.createElement('label', { className: 'text-white' }, [
                        'Use Last Seed ',
                        lastUsedSeed !== -1 && React.createElement('span', {
                            className: 'text-blue-400 font-mono'
                        }, `(${lastUsedSeed})`)
                    ])
                ]),
                React.createElement('input', {
                    type: 'number',
                    value: options.seed,
                    onChange: (e) => {
                        const newSeed = parseInt(e.target.value);
                        setOptions({
                            ...options,
                            seed: newSeed,
                            useLastSeed: false
                        });
                    },
                    disabled: options.useLastSeed,
                    className: `w-full p-2 bg-gray-700 text-white rounded ${options.useLastSeed ? 'opacity-50' : ''}`,
                    placeholder: 'Random Seed (-1)'
                })
            ]),

            // LoRA Section
            React.createElement('div', { key: 'loras', className: 'space-y-4' }, [
                React.createElement('div', { className: 'flex justify-between items-center' }, [
                    React.createElement('label', { className: 'text-white' }, 'Additional LoRA Models:'),
                    React.createElement('button', {
                        onClick: addLora,
                        disabled: options.loras.length >= 5,
                        className: 'px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'
                    }, 'Add LoRA')
                ]),
                ...options.loras.map((lora, index) =>
                    React.createElement('div', {
                        key: `lora-${index}`,
                        className: 'flex gap-2 items-end'
                    }, [
                        React.createElement('div', { className: 'flex-1' }, [
                            React.createElement('select', {
                                value: lora.name,
                                onChange: (e) => handleLoraChange(index, 'name', e.target.value),
                                className: 'w-full p-2 bg-gray-700 text-white rounded'
                            }, [
                                React.createElement('option', { value: '' }, 'Select LoRA'),
                                ...availableModels.loras.map(loraName =>
                                    React.createElement('option', { key: loraName, value: loraName }, loraName)
                                )
                            ])
                        ]),
                        React.createElement('input', {
                            type: 'number',
                            value: lora.strength,
                            onChange: (e) => handleLoraChange(index, 'strength', parseFloat(e.target.value)),
                            className: 'w-24 p-2 bg-gray-700 text-white rounded',
                            min: '0',
                            max: '2',
                            step: '0.1'
                        }),
                        index > 0 && React.createElement('button', {
                            onClick: () => removeLora(index),
                            className: 'px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700'
                        }, 'Remove')
                    ])
                )
            ])
        ])
    ]);
};

export default AdvancedOptions;