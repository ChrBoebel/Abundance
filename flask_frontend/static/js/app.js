// State
let isStreaming = false;
let sessionId = `s-${Date.now().toString(36)}`;
let currentEventSource = null;
let activeToolCalls = new Map();
let researchTree = {};  // Hierarchical tree structure
let researchProgressContainer = null;  // Single research progress element

// Elements
const messagesEl = document.getElementById('messages');
const welcomeEl = document.getElementById('welcome');
const messageInput = document.getElementById('message-input');
const chatForm = document.getElementById('chat-form');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-btn');
const themeToggle = document.getElementById('theme-toggle');
const sunIcon = document.getElementById('sun-icon');
const moonIcon = document.getElementById('moon-icon');

// Preserve Theme Icons after lucide.createIcons() calls
function preserveThemeIcons() {
    if (!sunIcon || !moonIcon) return;
    const isDark = document.documentElement.classList.contains('dark');
    if (isDark) {
        // Dark Mode: Show sun icon (to switch to light)
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    } else {
        // Light Mode: Show moon icon (to switch to dark)
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    }
}

// Initialize Lucide icons and set correct theme icons
lucide.createIcons();
preserveThemeIcons();

// Theme Toggle
themeToggle.addEventListener('click', () => {
    const html = document.documentElement;
    const isDark = html.classList.contains('dark');

    if (isDark) {
        html.classList.remove('dark');
        html.classList.add('light');
    } else {
        html.classList.remove('light');
        html.classList.add('dark');
    }

    // Update icons immediately after theme change
    preserveThemeIcons();
});

// Clear Chat
if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
        if (confirm('Chat wirklich leeren?')) {
            messagesEl.innerHTML = '';
            welcomeEl.style.display = 'flex';
            sessionId = `s-${Date.now().toString(36)}`;
            activeToolCalls.clear();
            try {
                await fetch(`/api/thread/clear/${sessionId}`, { method: 'POST' });
            } catch (e) {}
        }
    });
}

// Helper: Get German name for tools
function getGermanToolName(toolName) {
    const names = {
        'tavily_search': 'Websuche',
        'web_search': 'Websuche',
        'tavily_search_results_json': 'Websuche',
        'ConductResearch': 'Teilrecherche starten',
        'ResearchComplete': 'Recherche abschließen',
        'think_tool': 'Nachdenken',
        'file_read': 'Datei lesen',
        'default': toolName
    };
    return names[toolName] || names.default;
}

// Helper: Get icon for tool type
function getToolIcon(toolName) {
    const icons = {
        'tavily_search': 'search',
        'web_search': 'search',
        'tavily_search_results_json': 'search',
        'think_tool': 'brain',
        'ConductResearch': 'users',
        'ResearchComplete': 'check-circle',
        'file_read': 'file-text',
        'default': 'wrench'
    };
    return icons[toolName] || icons.default;
}

// Helper: Get icon for step type
function getStepIcon() {
    return 'settings';
}

// Create Research Progress Container (Perplexity-style)
function createResearchProgressContainer() {
    if (researchProgressContainer) return researchProgressContainer;

    const container = document.createElement('div');
    container.id = 'research-progress';
    container.className = 'message-bubble flex justify-start mb-4';
    container.innerHTML = `
        <div class="rounded-2xl px-4 py-3 max-w-5xl mr-4" style="background: hsl(var(--card)); border: 2px solid hsl(var(--border));">
            <div class="flex items-center gap-3 mb-3">
                <i data-lucide="loader-2" class="w-5 h-5 animate-spin" style="color: hsl(var(--primary));"></i>
                <h3 class="text-lg font-semibold" style="color: hsl(var(--primary));">Recherche läuft...</h3>
            </div>
            <div id="research-tree" class="space-y-2"></div>
        </div>
    `;

    welcomeEl.style.display = 'none';
    messagesEl.appendChild(container);
    lucide.createIcons();
    preserveThemeIcons();
    researchProgressContainer = container;
    return container;
}

// Update Research Tree (hierarchical, expandable)
function updateResearchTree() {
    const treeEl = document.getElementById('research-tree');
    if (!treeEl) return;

    // Build hierarchical HTML
    let html = '';

    // Top-level items
    Object.entries(researchTree).forEach(([id, item]) => {
        if (item.level === 0) {
            html += renderTreeItem(id, item, 0);
        }
    });

    treeEl.innerHTML = html;
    lucide.createIcons();
    preserveThemeIcons();
}

// Render Tree Item (recursive for children)
function renderTreeItem(id, item, depth) {
    const indent = depth * 20;
    const statusIcon = item.status === 'completed' ? 'check-circle' :
                     item.status === 'running' ? 'loader-2' :
                     'circle';
    const statusClass = item.status === 'completed' ? 'text-green-500' :
                       item.status === 'running' ? 'text-blue-500 animate-spin' :
                       'text-gray-400';

    const hasChildren = item.children && item.children.length > 0;
    const expanded = item.expanded !== false; // Default expanded

    let html = `
        <div class="tree-item" style="margin-left: ${indent}px;">
            <div class="flex items-center gap-2 py-1 cursor-pointer hover:bg-gray-800/50 rounded px-2" onclick="toggleTreeItem('${id}')">
                ${hasChildren ? `<i data-lucide="${expanded ? 'chevron-down' : 'chevron-right'}" class="w-4 h-4"></i>` : '<span class="w-4"></span>'}
                <i data-lucide="${statusIcon}" class="w-4 h-4 ${statusClass}"></i>
                <span class="text-sm">${item.name}</span>
            </div>
    `;

    // Render children if expanded
    if (hasChildren && expanded) {
        html += '<div class="children">';
        item.children.forEach(childId => {
            const child = researchTree[childId];
            if (child) {
                html += renderTreeItem(childId, child, depth + 1);
            }
        });
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Toggle Tree Item Expand/Collapse
function toggleTreeItem(id) {
    if (researchTree[id]) {
        researchTree[id].expanded = !researchTree[id].expanded;
        updateResearchTree();
    }
}

// Add/Update Tree Node
function addOrUpdateTreeNode(id, data) {
    if (!researchTree[id]) {
        researchTree[id] = {
            id: id,
            name: data.name,
            status: data.status || 'running',
            level: data.level || 0,
            parent_id: data.parent_id || null,
            children: [],
            expanded: true
        };

        // Add to parent's children if applicable
        if (data.parent_id && researchTree[data.parent_id]) {
            researchTree[data.parent_id].children.push(id);
        }
    } else {
        // Update existing node
        researchTree[id].status = data.status || researchTree[id].status;
        if (data.name) researchTree[id].name = data.name;
    }

    updateResearchTree();
}

// Complete Research Progress
function completeResearchProgress() {
    if (researchProgressContainer) {
        const headerEl = researchProgressContainer.querySelector('h3');
        const iconEl = researchProgressContainer.querySelector('i[data-lucide="loader-2"]');
        if (headerEl) headerEl.textContent = 'Recherche abgeschlossen';
        if (iconEl) {
            iconEl.setAttribute('data-lucide', 'check-circle');
            iconEl.classList.remove('animate-spin');
            lucide.createIcons();
            preserveThemeIcons();
        }
    }
}

// Add Message
function addMessage(role, content, isComplete = true) {
    welcomeEl.style.display = 'none';

    const messageDiv = document.createElement('div');
    messageDiv.className = `message-bubble flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `${role === 'user' ? 'rounded-2xl px-4 py-3 max-w-3xl ml-16' : 'rounded-lg px-6 py-5 w-full report-content'}`;

    if (role === 'user') {
        bubbleDiv.style.background = 'hsl(var(--primary))';
        bubbleDiv.style.color = 'white';
        bubbleDiv.textContent = content;
    } else {
        bubbleDiv.className += ' markdown-content';
        bubbleDiv.style.background = 'hsl(var(--card))';
        bubbleDiv.style.color = 'hsl(var(--foreground))';
        bubbleDiv.style.border = '1px solid hsl(var(--border))';
        bubbleDiv.innerHTML = marked.parse(content);

        // Highlight code blocks
        bubbleDiv.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });

        // Make links open in new tab
        bubbleDiv.querySelectorAll('a').forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        });

        // Make citation numbers clickable and link to sources
        // Find all text nodes and replace [1], [2], etc. with clickable links
        const walker = document.createTreeWalker(
            bubbleDiv,
            NodeFilter.SHOW_TEXT,
            null
        );

        const nodesToReplace = [];
        let node;
        while (node = walker.nextNode()) {
            if (node.textContent.match(/\[\d+\]/)) {
                nodesToReplace.push(node);
            }
        }

        nodesToReplace.forEach(textNode => {
            const text = textNode.textContent;
            const regex = /\[(\d+)\]/g;

            if (regex.test(text)) {
                const fragment = document.createDocumentFragment();
                let lastIndex = 0;
                const newRegex = /\[(\d+)\]/g;
                let match;

                while ((match = newRegex.exec(text)) !== null) {
                    // Add text before the match
                    if (match.index > lastIndex) {
                        fragment.appendChild(document.createTextNode(text.substring(lastIndex, match.index)));
                    }

                    // Create clickable citation
                    const citation = document.createElement('a');
                    const sourceNumber = match[1]; // Capture the source number in closure
                    citation.href = `#source-${sourceNumber}`;
                    citation.textContent = match[0];
                    citation.className = 'citation-link';
                    citation.style.cssText = 'color: hsl(var(--primary)); font-weight: 500; cursor: pointer; text-decoration: none;';
                    citation.onclick = (e) => {
                        e.preventDefault();
                        const sourceEl = bubbleDiv.querySelector(`#source-${sourceNumber}`);
                        if (sourceEl) {
                            sourceEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            sourceEl.style.background = 'hsl(var(--primary) / 0.1)';
                            setTimeout(() => {
                                sourceEl.style.background = '';
                            }, 2000);
                        }
                    };
                    fragment.appendChild(citation);

                    lastIndex = newRegex.lastIndex;
                }

                // Add remaining text
                if (lastIndex < text.length) {
                    fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
                }

                textNode.parentNode.replaceChild(fragment, textNode);
            }
        });

        // Format sources section - add IDs and line breaks
        const sourcesHeading = Array.from(bubbleDiv.querySelectorAll('h3')).find(h3 =>
            h3.textContent.toLowerCase().includes('quellen') || h3.textContent.toLowerCase().includes('sources')
        );

        if (sourcesHeading) {
            const sourcesContainer = sourcesHeading.nextElementSibling;
            if (sourcesContainer && sourcesContainer.tagName === 'P') {
                const sourcesText = sourcesContainer.textContent;
                const sources = sourcesText.split(/\[(\d+)\]/).filter(s => s.trim());

                // Rebuild sources as a list
                const sourcesList = document.createElement('div');
                sourcesList.className = 'sources-list';
                sourcesList.style.cssText = 'display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem;';

                for (let i = 0; i < sources.length; i += 2) {
                    if (sources[i] && sources[i + 1]) {
                        const sourceNumber = sources[i];
                        const sourceText = sources[i + 1].trim();

                        const sourceItem = document.createElement('div');
                        sourceItem.id = `source-${sourceNumber}`;
                        sourceItem.className = 'source-item';
                        sourceItem.style.cssText = 'padding: 0.75rem; background: hsl(var(--muted) / 0.3); border-radius: 0.25rem; transition: background 0.3s;';

                        const sourceNumberEl = document.createElement('span');
                        sourceNumberEl.style.cssText = 'font-weight: 600; color: hsl(var(--primary)); margin-right: 0.5rem;';
                        sourceNumberEl.textContent = `[${sourceNumber}]`;

                        const sourceContent = document.createElement('span');
                        // Konvertiere URLs zu anklickbaren Links
                        const urlRegex = /(https?:\/\/[^\s]+)/g;
                        const textWithLinks = sourceText.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: hsl(var(--primary)); text-decoration: underline; cursor: pointer;">$1</a>');
                        sourceContent.innerHTML = textWithLinks;

                        sourceItem.appendChild(sourceNumberEl);
                        sourceItem.appendChild(sourceContent);
                        sourcesList.appendChild(sourceItem);
                    }
                }

                sourcesContainer.replaceWith(sourcesList);
            }
        }
    }

    messageDiv.appendChild(bubbleDiv);
    messagesEl.appendChild(messageDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    return bubbleDiv;
}

// Add Thinking Indicator
function addThinkingIndicator() {
    const thinkingDiv = document.createElement('div');
    thinkingDiv.id = 'thinking-indicator';
    thinkingDiv.className = 'flex justify-start mb-4';
    thinkingDiv.innerHTML = `
        <div class="flex items-center space-x-3">
            <div class="relative w-8 h-8 rounded-full flex items-center justify-center" style="background: linear-gradient(to bottom right, hsl(var(--agent-avatar-from)), hsl(var(--agent-avatar-to)));">
                <span class="absolute inset-0 rounded-full animate-ping" style="background: hsl(var(--primary) / 0.5); animation-duration: 2s;"></span>
                <i data-lucide="bot" class="w-4 h-4 relative z-10" style="color: hsl(var(--foreground));"></i>
            </div>
            <div class="px-4 py-3 rounded-2xl" style="background: hsl(var(--card)); border: 2px solid hsl(var(--border));">
                <div class="flex items-center gap-2 text-sm font-medium">
                    <i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i>
                    Agent arbeitet...
                </div>
                <div class="thinking-dots flex gap-1.5 mt-2">
                    <span class="w-2 h-2 rounded-full" style="background: hsl(var(--primary));"></span>
                    <span class="w-2 h-2 rounded-full" style="background: hsl(var(--primary));"></span>
                    <span class="w-2 h-2 rounded-full" style="background: hsl(var(--primary));"></span>
                </div>
            </div>
        </div>
    `;
    messagesEl.appendChild(thinkingDiv);
    lucide.createIcons();
    preserveThemeIcons();
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return thinkingDiv;
}

// Format Tool Result
function formatToolResult(result, toolName) {
    if (!result) return '';

    // Try to parse as JSON for search results
    try {
        const data = typeof result === 'string' ? JSON.parse(result) : result;

        // Handle search results specially
        if (data.citations && Array.isArray(data.citations)) {
            let html = '';
            if (data.answer) {
                html += `<div class="mb-3 text-sm">${data.answer}</div>`;
            }
            if (data.citations.length > 0) {
                html += '<div class="space-y-2"><p class="text-xs font-semibold mb-2">Quellen:</p><div class="flex flex-wrap gap-2">';
                data.citations.slice(0, 10).forEach(citation => {
                    const domain = new URL(citation.url).hostname;
                    html += `
                        <a href="${citation.url}" target="_blank" rel="noopener noreferrer" class="source-link">
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                            <span class="text-xs font-medium">${citation.title || domain}</span>
                        </a>
                    `;
                });
                html += '</div></div>';
            }
            setTimeout(() => {
                lucide.createIcons();
                preserveThemeIcons();
            }, 0);
            return html;
        }

        // Default JSON formatting
        return `<pre class="whitespace-pre-wrap">${JSON.stringify(data, null, 2)}</pre>`;
    } catch (e) {
        // Plain text fallback
        return `<pre class="whitespace-pre-wrap">${result}</pre>`;
    }
}

// Send Message
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message || isStreaming) return;

    // Add user message
    addMessage('user', message);
    messageInput.value = '';

    // Reset research tree state
    researchTree = {};
    researchProgressContainer = null;

    // Show thinking
    const thinkingEl = addThinkingIndicator();
    isStreaming = true;
    sendBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Läuft...</span>';
    sendBtn.disabled = true;
    lucide.createIcons();
    preserveThemeIcons();

    let agentBubble = null;
    let fullContent = '';

    try {
        // Create EventSource for SSE
        const url = `/api/chat/stream?thread_id=${sessionId}&message=${encodeURIComponent(message)}`;
        currentEventSource = new EventSource(url);

        currentEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'thinking') {
                    // Thinking started - remove thinking indicator, create research tree
                    if (thinkingEl && thinkingEl.parentNode) {
                        thinkingEl.remove();
                    }
                    createResearchProgressContainer();
                } else if (data.type === 'step_start') {
                    // Workflow step started
                    createResearchProgressContainer();
                    addOrUpdateTreeNode(data.id, {
                        name: data.name,
                        status: 'running',
                        level: data.level || 0,
                        parent_id: data.parent_id
                    });
                } else if (data.type === 'step_complete') {
                    // Workflow step completed
                    addOrUpdateTreeNode(data.id, {
                        name: data.name,
                        status: 'completed'
                    });
                } else if (data.type === 'tool_call_start') {
                    // Tool execution started
                    createResearchProgressContainer();
                    const germanName = getGermanToolName(data.name);
                    addOrUpdateTreeNode(data.id, {
                        name: germanName,
                        status: 'running',
                        level: data.level || 2,
                        parent_id: data.parent_id
                    });
                } else if (data.type === 'tool_call_complete') {
                    // Tool execution completed
                    const germanName = getGermanToolName(data.name);
                    addOrUpdateTreeNode(data.id, {
                        name: germanName,
                        status: data.status === 'error' ? 'error' : 'completed'
                    });
                } else if (data.type === 'agent_message') {
                    // Complete message received - add as chat message BELOW research progress
                    completeResearchProgress();
                    addMessage('agent', data.content);
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                } else if (data.type === 'done') {
                    // Stream complete
                    completeResearchProgress();
                    if (currentEventSource) {
                        currentEventSource.close();
                        currentEventSource = null;
                    }
                    isStreaming = false;
                    sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span>Senden</span>';
                    sendBtn.disabled = false;
                    lucide.createIcons();
                    preserveThemeIcons();
                } else if (data.type === 'error') {
                    // Error occurred
                    if (thinkingEl && thinkingEl.parentNode) {
                        thinkingEl.remove();
                    }
                    addMessage('agent', `❌ Fehler: ${data.error}`);
                    if (currentEventSource) {
                        currentEventSource.close();
                        currentEventSource = null;
                    }
                    isStreaming = false;
                    sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span>Senden</span>';
                    sendBtn.disabled = false;
                    lucide.createIcons();
                    preserveThemeIcons();
                }
            } catch (err) {
                console.error('Parse error:', err);
            }
        };

        currentEventSource.onerror = () => {
            if (thinkingEl && thinkingEl.parentNode) {
                thinkingEl.remove();
            }
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
            isStreaming = false;
            sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span>Senden</span>';
            sendBtn.disabled = false;
            lucide.createIcons();
            preserveThemeIcons();
        };

    } catch (err) {
        console.error('Request error:', err);
        if (thinkingEl && thinkingEl.parentNode) {
            thinkingEl.remove();
        }
        addMessage('agent', `❌ Fehler: ${err.message}`);
        isStreaming = false;
        sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span>Senden</span>';
        sendBtn.disabled = false;
        lucide.createIcons();
        preserveThemeIcons();
    }
});

// Focus input on load
messageInput.focus();
