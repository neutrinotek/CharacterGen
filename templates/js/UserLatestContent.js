import React, { useState, useEffect } from 'react';

const UserLatestContent = ({ userId }) => {
  const [prompt, setPrompt] = useState('');
  const [imageUrl, setImageUrl] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLatestContent = async () => {
      try {
        // Fetch user's latest content
        const response = await fetch('/api/user/latest-content', {
          credentials: 'include'
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch latest content');
        }

        const data = await response.json();
        if (data.prompt) {
          setPrompt(data.prompt);
        }
        if (data.image_url) {
          setImageUrl(data.image_url);
        }
      } catch (error) {
        console.error('Error fetching latest content:', error);
        setError('Failed to load latest content');
      }
    };

    fetchLatestContent();
  }, [userId]);

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}
      
      <div>
        <h3 className="text-lg font-medium text-white mb-2">Current Prompt:</h3>
        <div className="bg-gray-800 p-4 rounded">
          {prompt || "No prompt generated yet."}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-medium text-white mb-2">Generated Image:</h3>
        <div className="bg-gray-800 p-4 rounded">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt="Generated"
              className="max-w-full h-auto rounded"
            />
          ) : (
            <div className="text-gray-400 text-center py-8">
              No image generated yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UserLatestContent;