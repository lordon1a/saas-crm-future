// Team Management JavaScript

let currentUser = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadTeamMembers();
    loadPendingInvitations();
    setupInviteForm();
});

// Load team members
async function loadTeamMembers() {
    try {
        const response = await fetch('/api/team/members');
        if (!response.ok) throw new Error('Failed to load team members');
        
        const data = await response.json();
        currentUser = data.current_user;
        renderTeamMembers(data.members);
    } catch (error) {
        console.error('Error loading team members:', error);
        showAlert('inviteAlert', 'Takım üyeleri yüklenemedi', 'error');
    }
}

// Render team members table
function renderTeamMembers(members) {
    const tbody = document.getElementById('teamMembersTable');
    
    if (!members || members.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500">Henüz takım üyesi yok</td></tr>';
        return;
    }

    tbody.innerHTML = members.map(member => {
        const isOwner = member.role === 'owner';
        const isCurrentUser = currentUser && currentUser.id === member.id;
        const canEdit = currentUser && (currentUser.role === 'owner' || (currentUser.role === 'admin' && !isOwner));
        
        const lastLogin = member.last_login 
            ? new Date(member.last_login).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
            : 'Hiç giriş yapmadı';

        const roleColors = {
            owner: 'bg-purple-100 text-purple-800',
            admin: 'bg-blue-100 text-blue-800',
            member: 'bg-green-100 text-green-800',
            viewer: 'bg-gray-100 text-gray-800'
        };

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center text-brand-600 font-semibold">
                            ${member.name.charAt(0).toUpperCase()}
                        </div>
                        <div class="ml-3">
                            <div class="text-sm font-medium text-gray-900">${escapeHtml(member.name)}</div>
                            ${isCurrentUser ? '<span class="text-xs text-gray-500">(Siz)</span>' : ''}
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${escapeHtml(member.email)}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${canEdit && !isOwner ? `
                        <select onchange="updateMemberRole(${member.id}, this.value)" class="text-xs font-medium px-3 py-1 rounded-full ${roleColors[member.role]} border-0 cursor-pointer">
                            <option value="admin" ${member.role === 'admin' ? 'selected' : ''}>Admin</option>
                            <option value="member" ${member.role === 'member' ? 'selected' : ''}>Member</option>
                            <option value="viewer" ${member.role === 'viewer' ? 'selected' : ''}>Viewer</option>
                        </select>
                    ` : `
                        <span class="text-xs font-medium px-3 py-1 rounded-full ${roleColors[member.role]}">${member.role.charAt(0).toUpperCase() + member.role.slice(1)}</span>
                    `}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${lastLogin}</td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm">
                    ${canEdit && !isOwner && !isCurrentUser ? `
                        <button onclick="removeMember(${member.id}, '${escapeHtml(member.name)}')" class="text-red-600 hover:text-red-800 font-medium">
                            <i class="fas fa-trash-alt mr-1"></i> Kaldır
                        </button>
                    ` : ''}
                    ${currentUser && currentUser.role === 'owner' && member.role === 'admin' && !isCurrentUser ? `
                        <button onclick="transferOwnership(${member.id}, '${escapeHtml(member.name)}')" class="ml-3 text-purple-600 hover:text-purple-800 font-medium">
                            <i class="fas fa-crown mr-1"></i> Sahipliği Devret
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

// Load pending invitations
async function loadPendingInvitations() {
    try {
        const response = await fetch('/api/team/members');
        if (!response.ok) throw new Error('Failed to load invitations');
        
        const data = await response.json();
        renderInvitations(data.invitations);
    } catch (error) {
        console.error('Error loading invitations:', error);
    }
}

// Render invitations table
function renderInvitations(invitations) {
    const tbody = document.getElementById('invitationsTable');
    
    if (!invitations || invitations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500">Bekleyen davet yok</td></tr>';
        return;
    }

    tbody.innerHTML = invitations.map(inv => {
        const expiresAt = new Date(inv.expires_at).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        
        const roleColors = {
            admin: 'bg-blue-100 text-blue-800',
            member: 'bg-green-100 text-green-800',
            viewer: 'bg-gray-100 text-gray-800'
        };

        // Generate invitation link
        const invitationLink = `${window.location.origin}/accept-invitation/${inv.token}`;

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${escapeHtml(inv.invitee_email)}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="text-xs font-medium px-3 py-1 rounded-full ${roleColors[inv.role]}">${inv.role.charAt(0).toUpperCase() + inv.role.slice(1)}</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${escapeHtml(inv.inviter_name)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${expiresAt}</td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                    <button onclick="copyInvitationLink('${invitationLink}')" class="text-brand-600 hover:text-brand-800 font-medium" title="Davet linkini kopyala">
                        <i class="fas fa-link mr-1"></i> Linki Kopyala
                    </button>
                    <button onclick="cancelInvitation(${inv.id}, '${escapeHtml(inv.invitee_email)}')" class="text-red-600 hover:text-red-800 font-medium">
                        <i class="fas fa-times mr-1"></i> İptal Et
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Setup invite form
function setupInviteForm() {
    document.getElementById('inviteForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await sendInvitation();
    });
}

// Show invite modal
function showInviteModal() {
    document.getElementById('inviteModal').classList.remove('hidden');
    document.getElementById('inviteEmail').value = '';
    document.getElementById('inviteRole').value = 'member';
    document.getElementById('inviteAlert').classList.add('hidden');
}

// Close invite modal
function closeInviteModal() {
    document.getElementById('inviteModal').classList.add('hidden');
}

// Send invitation
async function sendInvitation() {
    const email = document.getElementById('inviteEmail').value.trim();
    const role = document.getElementById('inviteRole').value;
    const alertDiv = document.getElementById('inviteAlert');

    if (!email) {
        showAlert('inviteAlert', 'Lütfen e-posta adresini girin', 'error');
        return;
    }

    try {
        const response = await fetch('/api/team/invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, role })
        });

        const data = await response.json();

        if (response.ok) {
            showAlert('inviteAlert', 'Davet başarıyla gönderildi!', 'success');
            setTimeout(() => {
                closeInviteModal();
                loadPendingInvitations();
            }, 1500);
        } else {
            showAlert('inviteAlert', data.error || 'Davet gönderilemedi', 'error');
        }
    } catch (error) {
        console.error('Error sending invitation:', error);
        showAlert('inviteAlert', 'Bağlantı hatası', 'error');
    }
}

// Cancel invitation
async function cancelInvitation(invitationId, email) {
    if (!confirm(`${email} adresine gönderilen daveti iptal etmek istediğinizden emin misiniz?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/team/invitations/${invitationId}/cancel`, {
            method: 'POST'
        });

        if (response.ok) {
            loadPendingInvitations();
        } else {
            const data = await response.json();
            alert(data.error || 'Davet iptal edilemedi');
        }
    } catch (error) {
        console.error('Error cancelling invitation:', error);
        alert('Bağlantı hatası');
    }
}

// Update member role
async function updateMemberRole(memberId, newRole) {
    try {
        const response = await fetch(`/api/team/members/${memberId}/role`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: newRole })
        });

        if (response.ok) {
            loadTeamMembers();
        } else {
            const data = await response.json();
            alert(data.error || 'Rol güncellenemedi');
            loadTeamMembers(); // Reload to reset dropdown
        }
    } catch (error) {
        console.error('Error updating role:', error);
        alert('Bağlantı hatası');
        loadTeamMembers();
    }
}

// Remove member
async function removeMember(memberId, memberName) {
    if (!confirm(`${memberName} adlı üyeyi takımdan kaldırmak istediğinizden emin misiniz? Bu işlem geri alınamaz.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/team/members/${memberId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadTeamMembers();
        } else {
            const data = await response.json();
            alert(data.error || 'Üye kaldırılamadı');
        }
    } catch (error) {
        console.error('Error removing member:', error);
        alert('Bağlantı hatası');
    }
}

// Transfer ownership
async function transferOwnership(memberId, memberName) {
    if (!confirm(`Workspace sahipliğini ${memberName} adlı üyeye devretmek istediğinizden emin misiniz? Bu işlem sonrası sizin rolünüz Admin olacaktır.`)) {
        return;
    }

    try {
        const response = await fetch('/api/team/transfer-ownership', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_owner_id: memberId })
        });

        if (response.ok) {
            alert('Sahiplik başarıyla devredildi');
            loadTeamMembers();
        } else {
            const data = await response.json();
            alert(data.error || 'Sahiplik devredilemedi');
        }
    } catch (error) {
        console.error('Error transferring ownership:', error);
        alert('Bağlantı hatası');
    }
}

// Show alert helper
function showAlert(elementId, message, type) {
    const alertDiv = document.getElementById(elementId);
    alertDiv.textContent = message;
    alertDiv.className = `p-3 rounded-lg text-sm ${
        type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
    }`;
    alertDiv.classList.remove('hidden');
}

// Escape HTML helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Copy invitation link to clipboard
async function copyInvitationLink(link) {
    try {
        await navigator.clipboard.writeText(link);
        showToast('Davet linki kopyalandı! Artık bu linki paylaşabilirsiniz.', 'success');
    } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = link;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showToast('Davet linki kopyalandı!', 'success');
        } catch (err) {
            showToast('Link kopyalanamadı. Lütfen manuel olarak kopyalayın: ' + link, 'error');
        }
        document.body.removeChild(textArea);
    }
}
