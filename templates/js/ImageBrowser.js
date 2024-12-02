import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { ChevronLeft, Folder, Image, Trash2 } from 'lucide-react';

const ImageBrowser = () => {
  const [currentPath, setCurrentPath] = useState('/');
  const [currentFiles, setCurrentFiles] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [canDelete, setCanDelete] = useState(false);

  useEffect(() => {
    // Fetch initial files
    fetchFiles(currentPath);

    // Fetch user permissions
    fetch('/api/user/permissions', {
      credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
      setCanDelete(data.can_delete_files);
    })
    .catch(error => console.error('Error fetching permissions:', error));
  }, []);

  const navigateBack = () => {
    if (currentPath === '/') return;
    const newPath = currentPath.split('/').slice(0, -2).join('/') + '/';
    setCurrentPath(newPath);
    fetchFiles(newPath);
    setSelectedItems(new Set());
  };

  const navigateToFolder = (folderName) => {
    const newPath = `${currentPath}${folderName}/`;
    setCurrentPath(newPath);
    fetchFiles(newPath);
    setSelectedItems(new Set());
  };

  const fetchFiles = async (path) => {
    try {
      const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }
      const data = await response.json();
      setCurrentFiles(data);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const toggleItemSelection = (itemName) => {
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemName)) {
        newSet.delete(itemName);
      } else {
        newSet.add(itemName);
      }
      return newSet;
    });
  };

  const selectAll = () => {
    const newSelection = new Set(currentFiles
      .filter(item => item.type === 'file')
      .map(item => item.name));
    setSelectedItems(newSelection);
  };

  const deselectAll = () => {
    setSelectedItems(new Set());
  };

  const deleteSelected = async () => {
    if (!canDelete) return;

    try {
      const response = await fetch('/api/delete-files', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          path: currentPath,
          files: Array.from(selectedItems)
        }),
      });

      if (response.ok) {
        await fetchFiles(currentPath);
        setSelectedItems(new Set());
      }
    } catch (error) {
      console.error('Error deleting files:', error);
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <button
            onClick={navigateBack}
            className="p-2 hover:bg-gray-100 rounded-full"
            disabled={currentPath === '/'}
          >
            <ChevronLeft className="w-6 h-6" />
          </button>
          <span className="text-lg font-medium">
            {currentPath === '/' ? 'Root' : currentPath}
          </span>
        </div>

        {canDelete && (
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              onClick={selectAll}
              className="text-sm"
            >
              Select All
            </Button>
            <Button
              variant="outline"
              onClick={deselectAll}
              className="text-sm"
            >
              Deselect All
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="destructive"
                  disabled={selectedItems.size === 0}
                  className="text-sm"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete Selected
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete Selected Items</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete {selectedItems.size} selected item(s)? This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={deleteSelected}>Delete</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {currentFiles.map((item, index) => (
          <Card key={index} className="relative">
            <CardContent className="p-4">
              {item.type === 'folder' ? (
                <div
                  className="flex items-center space-x-2 cursor-pointer"
                  onClick={() => navigateToFolder(item.name)}
                >
                  <Folder className="w-6 h-6 text-blue-500" />
                  <span>{item.name}</span>
                </div>
              ) : (
                <div className="relative">
                  {canDelete && (
                    <div className="absolute top-2 left-2 z-10">
                      <Checkbox
                        checked={selectedItems.has(item.name)}
                        onCheckedChange={() => toggleItemSelection(item.name)}
                        className="bg-white border-2 border-gray-300"
                      />
                    </div>
                  )}
                  <div
                    className="cursor-pointer"
                    onClick={() => setSelectedImage(item.url)}
                  >
                    <div className="relative w-full pt-[100%]">
                      <img
                        src={item.url}
                        alt={item.name}
                        className="absolute top-0 left-0 w-full h-full object-cover rounded"
                      />
                    </div>
                    <span className="mt-2 text-sm text-center block">{item.name}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedImage && (
        <div
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedImage(null)}
        >
          <img
            src={selectedImage}
            alt="Selected"
            className="max-w-full max-h-[90vh] object-contain"
          />
        </div>
      )}
    </div>
  );
};

export default ImageBrowser;