const socket = io();

// Chat functionality
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const chatMessages = document.getElementById('chat-messages');

function sendMessage() {
    const message = messageInput.value.trim();
    if (message) {
        socket.emit('send_message', {
            message: message,
            bill_id: 1
        });
        messageInput.value = '';
    }
}

sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

socket.on('new_message', (data) => {
    const messageDiv = document.createElement('div');
    messageDiv.className = `flex ${data.type === 'user' ? 'justify-end' : 'justify-start'} chat-message`;
    
    const messageBubble = document.createElement('div');
    messageBubble.className = `rounded-lg p-4 max-w-3/4 ${
        data.type === 'user' 
            ? 'bg-blue-500 text-white' 
            : 'bg-blue-100 text-gray-700'
    }`;
    
    const userHeader = document.createElement('div');
    userHeader.className = `font-semibold ${
        data.type === 'user' ? 'text-blue-100' : 'text-blue-800'
    }`;
    userHeader.textContent = data.user;
    
    const messageContent = document.createElement('div');
    messageContent.className = data.type === 'user' ? 'text-white' : 'text-gray-700';
    messageContent.textContent = data.message;
    
    const timestamp = document.createElement('div');
    timestamp.className = `text-xs mt-1 ${
        data.type === 'user' ? 'text-blue-200' : 'text-gray-500'
    }`;
    timestamp.textContent = new Date(data.timestamp).toLocaleTimeString();
    
    messageBubble.appendChild(userHeader);
    messageBubble.appendChild(messageContent);
    messageBubble.appendChild(timestamp);
    messageDiv.appendChild(messageBubble);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
});

// Bill modal functionality
let participantCount = 0;
let friendsList = [];

// Load friends list
async function loadFriends() {
    try {
        // In a real app, you'd fetch from an API endpoint
        // For now, we'll use the friends data from the template
        friendsList = window.friendsData || [];
        updateFriendSelection();
    } catch (error) {
        console.error('Error loading friends:', error);
    }
}

function updateFriendSelection() {
    const containers = document.querySelectorAll('#participants-container > div');
    containers.forEach(container => {
        const select = container.querySelector('select');
        if (select) {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Select a friend</option>' +
                friendsList.map(friend => 
                    `<option value="${friend.id}" ${friend.id == currentValue ? 'selected' : ''}>${friend.name}</option>`
                ).join('');
        }
    });
}

function calculateFinalAmount() {
    const totalAmount = parseFloat(document.getElementById('bill-amount').value) || 0;
    const taxAmount = parseFloat(document.getElementById('tax-amount').value) || 0;
    const discountAmount = parseFloat(document.getElementById('discount-amount').value) || 0;
    
    const finalAmount = totalAmount + taxAmount - discountAmount;
    document.getElementById('final-amount-display').textContent = `$${finalAmount.toFixed(2)}`;
    
    return finalAmount;
}

function openBillModal() {
    document.getElementById('bill-modal').classList.remove('hidden');
    document.getElementById('bill-modal').classList.add('flex');
    participantCount = 0;
    document.getElementById('participants-container').innerHTML = '';
    calculateFinalAmount();
    addParticipant();
}

function closeBillModal() {
    document.getElementById('bill-modal').classList.add('hidden');
    document.getElementById('bill-modal').classList.remove('flex');
}

function addParticipant() {
    participantCount++;
    const container = document.getElementById('participants-container');
    const participantDiv = document.createElement('div');
    participantDiv.className = 'flex space-x-2 items-center';
    participantDiv.innerHTML = `
        <select class="flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" required>
            <option value="">Select a friend</option>
            ${friendsList.map(friend => `<option value="${friend.id}">${friend.name}</option>`).join('')}
        </select>
        <input type="number" class="w-24 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" 
               placeholder="Amount" step="0.01" min="0" required>
        <button type="button" onclick="this.parentElement.remove()" class="text-red-500 hover:text-red-700">
            <i class="fas fa-times"></i>
        </button>
    `;
    container.appendChild(participantDiv);
}

// Add event listeners for amount calculations
document.getElementById('bill-amount')?.addEventListener('input', calculateFinalAmount);
document.getElementById('tax-amount')?.addEventListener('input', calculateFinalAmount);
document.getElementById('discount-amount')?.addEventListener('input', calculateFinalAmount);

document.getElementById('bill-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const description = document.getElementById('bill-description').value;
    const visitDetails = document.getElementById('visit-details').value;
    const visitDate = document.getElementById('visit-date').value;
    const totalAmount = parseFloat(document.getElementById('bill-amount').value);
    const taxAmount = parseFloat(document.getElementById('tax-amount').value) || 0;
    const discountAmount = parseFloat(document.getElementById('discount-amount').value) || 0;
    
    const participantInputs = document.querySelectorAll('#participants-container > div');
    const participants = [];
    
    for (const div of participantInputs) {
        const select = div.querySelector('select');
        const amountInput = div.querySelector('input[type="number"]');
        
        const friendId = parseInt(select.value);
        const amount = parseFloat(amountInput.value);
        
        if (friendId && !isNaN(amount)) {
            participants.push({
                friend_id: friendId,
                amount_owed: amount
            });
        }
    }
    
    if (participants.length === 0) {
        alert('Please add at least one participant');
        return;
    }
    
    try {
        const response = await fetch('/create_bill', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                description,
                visit_details: visitDetails,
                visit_date: visitDate,
                total_amount: totalAmount,
                tax_amount: taxAmount,
                discount_amount: discountAmount,
                participants
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            closeBillModal();
            alert('Bill created successfully!');
            window.location.reload();
        } else {
            alert('Error creating bill: ' + result.error);
        }
    } catch (error) {
        alert('Error creating bill: ' + error.message);
    }
});

// Friend modal functionality
function openFriendModal() {
    document.getElementById('friend-modal').classList.remove('hidden');
    document.getElementById('friend-modal').classList.add('flex');
    document.getElementById('friend-form').reset();
}

function closeFriendModal() {
    document.getElementById('friend-modal').classList.add('hidden');
    document.getElementById('friend-modal').classList.remove('flex');
}

document.getElementById('friend-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('friend-name').value;
    const email = document.getElementById('friend-email').value;
    const phone = document.getElementById('friend-phone').value;
    
    try {
        const response = await fetch('/add_friend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name,
                email,
                phone
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            closeFriendModal();
            alert('Friend added successfully!');
            window.location.reload();
        } else {
            alert('Error adding friend: ' + result.error);
        }
    } catch (error) {
        alert('Error adding friend: ' + error.message);
    }
});

async function deleteFriend(friendId) {
    if (!confirm('Are you sure you want to delete this friend? This will remove them from all bills.')) {
        return;
    }
    
    try {
        const response = await fetch(`/delete_friend/${friendId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Friend deleted successfully!');
            window.location.reload();
        } else {
            alert('Error deleting friend: ' + result.error);
        }
    } catch (error) {
        alert('Error deleting friend: ' + error.message);
    }
}

// Initialize friends list when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Pass friends data from template to JavaScript
    if (typeof window.friendsData === 'undefined') {
        window.friendsData = [];
    }
    loadFriends();
});