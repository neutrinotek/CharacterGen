import React, { useState, useEffect } from 'react';
import AdvancedOptions from './AdvancedOptions';

const LoadingStates = () => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [workflowOptions, setWorkflowOptions] = useState(null);
  const [availableModels, setAvailableModels] = useState({ checkpoints: [], loras: [] });

  // Fetch available models on component mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/available-models');
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data);
        }
      } catch (error) {
        console.error('Error fetching models:', error);
      }
    };
    fetchModels();
  }, []);

  const updateWorkflowOptions = async (options) => {
    if (!options) return;
    
    const characterSelect = document.getElementById('character-select');
    if (!characterSelect) return;

    try {
      const response = await fetch('/api/workflow-options', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          character: characterSelect.value,
          options: options
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      console.error('Error updating workflow options:', error);
    }
  };

const handleGenerateClick = async (action, buttonId) => {
    setIsGenerating(true);
    setLoadingMessage(`${action} in progress...`);

    try {
        const characterSelect = document.getElementById('character-select');
        const manualPrompt = document.getElementById('manual-prompt');

        const formData = new FormData();
        formData.append('character', characterSelect.value);

        if ((buttonId === '/manual_generation' || buttonId === '/enhanced_generation') && manualPrompt) {
            formData.append('manual_prompt', manualPrompt.value);
        }

        // Add the current advanced options to the form data
        if (workflowOptions) {
            formData.append('advancedOptions', JSON.stringify(workflowOptions));
        }

        // Update workflow options before generating
        if (workflowOptions) {
            await updateWorkflowOptions(workflowOptions);
        }

        const response = await fetch(buttonId, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        if (result.success) {
            window.location.reload();
        } else {
            throw new Error('Generation failed');
        }
    } catch (error) {
        console.error('Error:', error);
        setLoadingMessage('Error occurred during generation');
    } finally {
        setTimeout(() => {
            setIsGenerating(false);
            setLoadingMessage('');
        }, 3000);
    }
};

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-4">
        {/* Random Generation Button */}
        <button
          onClick={() => handleGenerateClick('Random generation', '/generate_new_image')}
          disabled={isGenerating}
          className="w-full p-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating && (
            <span className="inline-block animate-spin mr-2">⭮</span>
          )}
          Random Generation
        </button>

        {/* Regenerate Button */}
        <button
          onClick={() => handleGenerateClick('Regeneration', '/regenerate_image')}
          disabled={isGenerating}
          className="w-full p-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating && (
            <span className="inline-block animate-spin mr-2">⭮</span>
          )}
          Regenerate Image
        </button>

        {/* Manual Input Section */}
        <div className="space-y-2">
          <textarea
            id="manual-prompt"
            className="w-full p-2 rounded bg-gray-700 text-white"
            placeholder="Enter your prompt here..."
            rows={4}
          />
          <div className="flex gap-2">
            {/* Manual Generation Button */}
            <button
              onClick={() => handleGenerateClick('Manual generation', '/manual_generation')}
              disabled={isGenerating}
              className="flex-1 p-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating && (
                <span className="inline-block animate-spin mr-2">⭮</span>
              )}
              Manual Generation
            </button>
            {/* Enhanced Generation Button */}
            <button
              onClick={() => handleGenerateClick('Enhanced generation', '/enhanced_generation')}
              disabled={isGenerating}
              className="flex-1 p-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating && (
                <span className="inline-block animate-spin mr-2">⭮</span>
              )}
              Enhanced Generation
            </button>
          </div>
        </div>

        {/* Advanced Options */}
        <AdvancedOptions
          availableModels={availableModels}
          onOptionsChange={setWorkflowOptions}
        />
      </div>

      {/* Loading Message */}
      {isGenerating && (
        <div className="fixed top-4 right-4 bg-blue-500 text-white px-4 py-2 rounded shadow-lg flex items-center gap-2 z-50">
          <span className="inline-block animate-spin">⭮</span>
          {loadingMessage}
        </div>
      )}
    </div>
  );
};

export default LoadingStates;