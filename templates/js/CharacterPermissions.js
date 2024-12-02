import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';

const CharacterPermissions = ({ userId = null }) => {
    const [characters, setCharacters] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [loadingError, setLoadingError] = useState(null);

    useEffect(() => {
        loadCharacterPermissions();
    }, [userId]);

    const loadCharacterPermissions = async () => {
        try {
            const url = userId 
                ? `/admin/api/user/${userId}/characters`
                : '/admin/api/default-characters';
            
            const response = await fetch(url, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            setCharacters(data);
        } catch (error) {
            console.error('Error loading character permissions:', error);
            setLoadingError(error.message);
        }
    };

    const handlePermissionChange = (characterName, permissionType, value) => {
        setCharacters(prevCharacters => 
            prevCharacters.map(char => 
                char.name === characterName
                    ? { ...char, [permissionType]: value }
                    : char
            )
        );
    };

    const savePermissions = async () => {
        try {
            const url = userId 
                ? `/admin/api/user/${userId}/characters`
                : '/admin/api/default-characters';
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(characters),
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to save permissions');
            }

            alert('Permissions saved successfully');
        } catch (error) {
            console.error('Error saving permissions:', error);
            alert(`Error saving permissions: ${error.message}`);
        }
    };

    const filteredCharacters = characters.filter(char =>
        char.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loadingError) {
        return (
            <div className="text-red-500 p-4">
                Error loading character permissions: {loadingError}
            </div>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Character Permissions</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="mb-4">
                    <Input
                        type="text"
                        placeholder="Search characters..."
                        value={searchTerm}
                        onChange={e => setSearchTerm(e.target.value)}
                        className="w-full"
                    />
                </div>

                <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4 font-bold mb-2 p-2 bg-gray-100 dark:bg-gray-800 rounded">
                        <div>Character</div>
                        <div>Can Generate</div>
                        <div>Can Browse</div>
                    </div>

                    {filteredCharacters.map(char => (
                        <div key={char.name} className="grid grid-cols-3 gap-4 items-center p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded">
                            <div>{char.name}</div>
                            <div>
                                <Checkbox
                                    checked={char.can_generate}
                                    onCheckedChange={checked => handlePermissionChange(char.name, 'can_generate', checked)}
                                />
                            </div>
                            <div>
                                <Checkbox
                                    checked={char.can_browse}
                                    onCheckedChange={checked => handlePermissionChange(char.name, 'can_browse', checked)}
                                />
                            </div>
                        </div>
                    ))}
                </div>

                <div className="mt-6">
                    <Button onClick={savePermissions}>
                        Save Permissions
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
};

export default CharacterPermissions;
