document.addEventListener('DOMContentLoaded', function() {
    // Handle button clicks
    document.querySelectorAll('[data-action]').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();  // Prevent any form submission
            const action = this.dataset.action;
            const userId = this.dataset.userid;

            console.log('Action clicked:', action, 'for user:', userId);  // Debug log

            // Skip if it's an access management action (handled by access-management-modal.js)
            if (action === 'access_management') {
                return;
            }

            // Confirmation for dangerous actions
            if (action === 'delete' && !confirm('Are you sure you want to delete this user?')) {
                return;
            }

            try {
                let endpoint;
                let method = 'POST';
                let body = new FormData();

                // Set the appropriate endpoint based on the action
                if (action === 'delete') {
                    endpoint = `/admin/user/${userId}`;
                    method = 'DELETE';
                    body = null;
                } else if (action === 'approve') {
                    endpoint = `/admin/user/${userId}/approve`;
                } else if (action === 'reject') {
                    endpoint = `/admin/user/${userId}/reject`;
                } else {
                    endpoint = `/admin/user/${userId}`;
                    body.append('action', action);
                }

                console.log('Making request to:', endpoint);  // Debug log

                const response = await fetch(endpoint, {
                    method: method,
                    body: body,
                    credentials: 'include'
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to perform action');
                }

                const result = await response.json();
                console.log('Action result:', result);  // Debug log

                // Show success message
                alert(result.message || 'Action completed successfully');

                // Reload the page to show updated state
                window.location.reload();

            } catch (error) {
                console.error('Error:', error);
                alert('Error performing action: ' + error.message);
            }
        });
    });
});