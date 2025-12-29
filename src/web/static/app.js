/**
 * Nova Voice Assistant - Dashboard JavaScript
 */

// Socket.IO connection
let socket = null;

// State
const state = {
    isListening: false,
    currentSection: 'dashboard',
    conversations: [],
    voices: []
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    initNavigation();
    initDashboard();
    loadConversations();
    loadVoices();
});

// Socket.IO
function initSocket() {
    try {
        socket = io();
        
        socket.on('connect', () => {
            console.log('Connected to server');
            updateStatus('Ready', 'success');
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            updateStatus('Disconnected', 'error');
        });
        
        socket.on('status', (data) => {
            if (data.listening) {
                setListening(true);
            } else {
                setListening(false);
            }
        });
        
        socket.on('message', (data) => {
            addMessage(data.role, data.content);
        });
        
    } catch (error) {
        console.log('Socket.IO not available, running in standalone mode');
    }
}

// Navigation
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            const section = item.dataset.section;
            showSection(section);
            
            // Update active nav
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function showSection(sectionId) {
    const sections = document.querySelectorAll('.section');
    sections.forEach(s => s.classList.remove('active'));
    
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.add('active');
        state.currentSection = sectionId;
    }
}

// Dashboard
function initDashboard() {
    const startBtn = document.getElementById('start-btn');
    
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            toggleListening();
        });
    }
    
    // Save settings
    const saveBtn = document.getElementById('save-settings');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveSettings);
    }
}

function toggleListening() {
    if (state.isListening) {
        stopListening();
    } else {
        startListening();
    }
}

function startListening() {
    state.isListening = true;
    setListening(true);
    
    if (socket) {
        socket.emit('start_listening');
    }
    
    updateStatus('Listening...', 'active');
}

function stopListening() {
    state.isListening = false;
    setListening(false);
    
    if (socket) {
        socket.emit('stop_listening');
    }
    
    updateStatus('Ready', 'success');
}

function setListening(isListening) {
    const btn = document.getElementById('start-btn');
    const visualizer = document.getElementById('visualizer');
    const statusText = document.getElementById('assistant-status');
    
    if (isListening) {
        btn.innerHTML = '<span>⏹️</span> Stop Listening';
        visualizer.classList.add('active');
        statusText.textContent = 'Listening... Speak now!';
    } else {
        btn.innerHTML = '<span>🎤</span> Start Listening';
        visualizer.classList.remove('active');
        statusText.textContent = 'Press the button to start';
    }
}

function updateStatus(text, type = 'success') {
    const statusText = document.getElementById('status-text');
    const statusDot = document.querySelector('.status-dot');
    
    if (statusText) {
        statusText.textContent = text;
    }
    
    if (statusDot) {
        statusDot.style.background = type === 'success' ? 'var(--success)' : 
                                      type === 'error' ? 'var(--error)' : 
                                      'var(--warning)';
    }
}

// Messages
function addMessage(role, content) {
    const messagesEl = document.getElementById('messages');
    
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    
    messageEl.innerHTML = `
        <span class="avatar">${avatar}</span>
        <div class="bubble">${escapeHtml(content)}</div>
    `;
    
    messagesEl.appendChild(messageEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Conversations
async function loadConversations() {
    try {
        const response = await fetch('/api/conversations');
        const conversations = await response.json();
        
        state.conversations = conversations;
        renderConversations();
        
        // Update count
        const countEl = document.getElementById('session-count');
        if (countEl) {
            countEl.textContent = conversations.length;
        }
        
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

function renderConversations() {
    const listEl = document.getElementById('conversations-list');
    
    if (!state.conversations.length) {
        listEl.innerHTML = '<p class="empty-state">No conversations yet. Start talking!</p>';
        return;
    }
    
    listEl.innerHTML = state.conversations.map(conv => `
        <div class="conversation-item" data-id="${conv.session_id}">
            <div class="conversation-meta">
                <div class="conversation-date">${formatDate(conv.created_at)}</div>
                <div class="conversation-preview">Session: ${conv.session_id}</div>
            </div>
            <span class="conversation-count">${conv.message_count} messages</span>
        </div>
    `).join('');
    
    // Add click handlers
    listEl.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            viewConversation(item.dataset.id);
        });
    });
}

async function viewConversation(sessionId) {
    try {
        const response = await fetch(`/api/conversations/${sessionId}`);
        const conversation = await response.json();
        
        // Show messages
        const messagesEl = document.getElementById('messages');
        messagesEl.innerHTML = '';
        
        conversation.messages.forEach(msg => {
            addMessage(msg.role, msg.content);
        });
        
        // Switch to dashboard
        showSection('dashboard');
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelector('[data-section="dashboard"]').classList.add('active');
        
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

// Voices
async function loadVoices() {
    try {
        const response = await fetch('/api/voices');
        const voices = await response.json();
        
        state.voices = voices;
        renderVoices();
        
    } catch (error) {
        console.error('Failed to load voices:', error);
        document.getElementById('voices-grid').innerHTML = 
            '<p class="empty-state">Could not load voices. Make sure edge-tts is installed.</p>';
    }
}

function renderVoices() {
    const gridEl = document.getElementById('voices-grid');
    
    if (!state.voices.length) {
        gridEl.innerHTML = '<p class="empty-state">No voices available.</p>';
        return;
    }
    
    gridEl.innerHTML = state.voices.slice(0, 20).map(voice => {
        const genderIcon = voice.gender === 'Female' ? '♀️' : '♂️';
        
        return `
            <div class="voice-card" data-voice="${voice.name}">
                <div class="voice-info">
                    <span class="voice-icon">${genderIcon}</span>
                    <div>
                        <div class="voice-name">${voice.name.split('-').pop().replace('Neural', '')}</div>
                        <div class="voice-locale">${voice.locale}</div>
                    </div>
                </div>
                <button class="voice-preview" onclick="previewVoice('${voice.name}')">▶️ Preview</button>
            </div>
        `;
    }).join('');
}

async function previewVoice(voiceName) {
    try {
        const response = await fetch('/api/voices/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                voice: voiceName,
                text: 'Hello! This is how I sound. I am your voice assistant.'
            })
        });
        
        const data = await response.json();
        
        if (data.audio) {
            const audio = new Audio('data:audio/mp3;base64,' + data.audio);
            audio.play();
        }
        
    } catch (error) {
        console.error('Failed to preview voice:', error);
    }
}

// Settings
async function saveSettings() {
    const settings = {
        name: document.getElementById('setting-name').value,
        prompt: document.getElementById('setting-prompt').value,
        model: document.getElementById('setting-model').value,
        whisper: document.getElementById('setting-whisper').value
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            alert('Settings saved!');
        }
        
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings');
    }
}

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    if (!isoString) return '';
    
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
