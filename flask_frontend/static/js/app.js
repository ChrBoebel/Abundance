// State
let isStreaming = false;
let sessionId = `s-${Date.now().toString(36)}`;
let currentEventSource = null;

// Research state
let currentPhase = 1;
let phaseText = '';
let sourceCount = 0;
let sources = [];
let detailsExpanded = false;
let phases = [
    { id: 1, name: 'Strategie planen', icon: 'clipboard', status: 'pending' },
    { id: 2, name: 'Führe Recherche durch', icon: 'search', status: 'pending' },
    { id: 3, name: 'Synthese der Erkenntnisse', icon: 'lightbulb', status: 'pending' },
    { id: 4, name: 'Erstelle Bericht', icon: 'file-text', status: 'pending' }
];
let researchStatusContainer = null;
let currentActivity = '';

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

// Theme icon management
function updateThemeIcons() {
    if (!sunIcon || !moonIcon) return;
    const isDark = document.documentElement.classList.contains('dark');
    if (isDark) {
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    } else {
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    }
}

updateThemeIcons();
lucide.createIcons();

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
    updateThemeIcons();
});

// Clear Chat
if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
        if (confirm('Chat wirklich leeren?')) {
            messagesEl.innerHTML = '';
            welcomeEl.style.display = 'flex';
            sessionId = `s-${Date.now().toString(36)}`;
            try {
                await fetch(`/api/thread/clear/${sessionId}`, { method: 'POST' });
            } catch (e) {}
        }
    });
}

// Map backend steps to phases
function mapStepToPhase(stepName) {
    const phaseMap = {
        'clarify_with_user': 1,
        'write_research_brief': 1,
        'research_supervisor': 2,
        'supervisor': 2,
        'supervisor_tools': 2,
        'researcher': 2,
        'researcher_tools': 2,
        'compress_research': 3,
        'final_report_generation': 4
    };
    return phaseMap[stepName] || currentPhase;
}

// Create Compact Research Status
function createResearchStatus() {
    if (researchStatusContainer) return researchStatusContainer;

    const container = document.createElement('div');
    container.id = 'research-status';
    container.className = 'message-bubble flex justify-start mb-4';
    container.innerHTML = `
        <div class="compact-status rounded-2xl px-4 py-3 max-w-5xl mr-4" style="background: hsl(var(--card)); border: 2px solid hsl(var(--border));">
            <div class="flex items-center gap-3 mb-2">
                <i id="status-icon" data-lucide="loader-2" class="w-5 h-5 animate-spin" style="color: hsl(var(--primary));"></i>
                <h3 id="status-text" class="text-lg font-semibold" style="color: hsl(var(--primary));">Recherchiere...</h3>
            </div>
            <div id="status-phase" class="text-sm mb-1 flex items-center gap-2" style="color: hsl(var(--foreground) / 0.8);">
                <i id="phase-icon" data-lucide="clipboard" class="w-4 h-4"></i>
                <span>Plane Recherche-Strategie...</span>
            </div>
            <div id="source-counter" class="text-sm font-semibold mb-2 flex items-center gap-2" style="color: hsl(var(--primary));">
                <i data-lucide="book-open" class="w-4 h-4"></i>
                <span id="source-count-text">0 Quellen gefunden</span>
            </div>
            <div id="current-activity" class="text-xs mb-3" style="color: hsl(var(--foreground) / 0.6);"></div>

            <button id="details-toggle" class="text-xs px-3 py-1 rounded transition" style="background: hsl(var(--muted)); color: hsl(var(--foreground));">
                Details anzeigen ▼
            </button>

            <div id="research-details" class="hidden mt-3 pt-3" style="border-top: 1px solid hsl(var(--border));">
                <div class="text-sm font-semibold mb-2">Recherche-Fortschritt:</div>
                <div id="phases-list" class="space-y-1 mb-3"></div>
                <div id="sources-section" class="hidden">
                    <div class="text-sm font-semibold mb-2">Durchsuchte Quellen (<span id="sources-count">0</span>):</div>
                    <div id="sources-list" class="space-y-1 text-xs"></div>
                </div>
            </div>
        </div>
    `;

    welcomeEl.style.display = 'none';
    messagesEl.appendChild(container);
    lucide.createIcons();
    updateThemeIcons();
    researchStatusContainer = container;

    // Setup toggle
    const toggleBtn = container.querySelector('#details-toggle');
    const detailsEl = container.querySelector('#research-details');
    toggleBtn.addEventListener('click', () => {
        detailsExpanded = !detailsExpanded;
        if (detailsExpanded) {
            detailsEl.classList.remove('hidden');
            toggleBtn.innerHTML = 'Details verbergen ▲';
        } else {
            detailsEl.classList.add('hidden');
            toggleBtn.innerHTML = 'Details anzeigen ▼';
        }
    });

    return container;
}

// Update Research Status
function updateResearchStatus() {
    if (!researchStatusContainer) return;

    const phaseEl = researchStatusContainer.querySelector('#status-phase span');
    const phaseIconEl = researchStatusContainer.querySelector('#phase-icon');
    const sourceCountTextEl = researchStatusContainer.querySelector('#source-count-text');
    const activityEl = researchStatusContainer.querySelector('#current-activity');
    const phasesListEl = researchStatusContainer.querySelector('#phases-list');
    const sourcesListEl = researchStatusContainer.querySelector('#sources-list');
    const sourcesCountEl = researchStatusContainer.querySelector('#sources-count');
    const sourcesSectionEl = researchStatusContainer.querySelector('#sources-section');

    // Update phase text and icon
    if (phaseEl && phaseText) {
        phaseEl.textContent = phaseText;
    }
    if (phaseIconEl && currentPhase > 0 && currentPhase <= phases.length) {
        const phaseIcon = phases[currentPhase - 1].icon;
        phaseIconEl.setAttribute('data-lucide', phaseIcon);
        lucide.createIcons();
    }

    // Update source counter
    if (sourceCountTextEl) {
        sourceCountTextEl.textContent = `${sourceCount} ${sourceCount !== 1 ? 'Quellen' : 'Quelle'} gefunden`;
    }

    // Update current activity
    if (activityEl && currentActivity) {
        activityEl.textContent = `↳ Aktuell: ${currentActivity}`;
    }

    // Update phases list
    if (phasesListEl) {
        phasesListEl.innerHTML = phases.map(phase => {
            const iconName = phase.status === 'completed' ? 'check-circle' :
                           phase.status === 'running' ? 'loader-2' : 'circle';
            const iconClass = phase.status === 'running' ? 'animate-spin' : '';
            const color = phase.status === 'completed' ? '#10b981' :
                         phase.status === 'running' ? 'hsl(var(--primary))' : 'hsl(var(--foreground) / 0.4)';
            return `<div class="flex items-center gap-2" style="color: ${color};">
                <i data-lucide="${iconName}" class="w-4 h-4 ${iconClass}"></i>
                <i data-lucide="${phase.icon}" class="w-4 h-4"></i>
                <span class="text-sm">${phase.name}</span>
            </div>`;
        }).join('');
        lucide.createIcons();
    }

    // Update sources list
    if (sources.length > 0 && sourcesListEl) {
        sourcesSectionEl.classList.remove('hidden');
        sourcesCountEl.textContent = sources.length;
        sourcesListEl.innerHTML = sources.map(source =>
            `<div class="flex items-start gap-2" style="color: hsl(var(--foreground) / 0.7);">
                <i data-lucide="external-link" class="w-4 h-4 mt-0.5 flex-shrink-0"></i>
                <a href="${source.url}" target="_blank" rel="noopener noreferrer"
                   class="text-sm hover:underline transition-colors"
                   style="color: hsl(var(--primary)); word-break: break-word;">
                    ${source.title}
                </a>
            </div>`
        ).join('');
        lucide.createIcons();
    }
}

// Update Phase Status
function updatePhase(phaseId, status) {
    const phase = phases.find(p => p.id === phaseId);
    if (phase) {
        phase.status = status;
        updateResearchStatus();
    }
}

// Complete Research
function completeResearch() {
    if (!researchStatusContainer) return;

    const statusIcon = researchStatusContainer.querySelector('#status-icon');
    const statusText = researchStatusContainer.querySelector('#status-text');
    const sourceCounter = researchStatusContainer.querySelector('#source-counter');

    if (statusIcon) {
        statusIcon.setAttribute('data-lucide', 'check-circle');
        statusIcon.classList.remove('animate-spin');
        statusIcon.style.color = '#10b981';
    }

    if (statusText) {
        statusText.textContent = 'Recherche abgeschlossen';
        statusText.style.color = '#10b981';
    }

    const sourceCountText = researchStatusContainer.querySelector('#source-count-text');
    if (sourceCountText) {
        sourceCountText.textContent = `${sourceCount} ${sourceCount !== 1 ? 'Quellen' : 'Quelle'} analysiert`;
    }

    // Mark all phases as completed
    phases.forEach(phase => phase.status = 'completed');
    updateResearchStatus();

    lucide.createIcons();
    updateThemeIcons();
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

        bubbleDiv.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });

        bubbleDiv.querySelectorAll('a').forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        });

        // Make citation numbers clickable
        const walker = document.createTreeWalker(bubbleDiv, NodeFilter.SHOW_TEXT, null);
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
                    if (match.index > lastIndex) {
                        fragment.appendChild(document.createTextNode(text.substring(lastIndex, match.index)));
                    }

                    const citation = document.createElement('a');
                    const sourceNumber = match[1];
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

                if (lastIndex < text.length) {
                    fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
                }

                textNode.parentNode.replaceChild(fragment, textNode);
            }
        });

        // Format sources section
        const sourcesHeading = Array.from(bubbleDiv.querySelectorAll('h3')).find(h3 =>
            h3.textContent.toLowerCase().includes('quellen') || h3.textContent.toLowerCase().includes('sources')
        );

        if (sourcesHeading) {
            const sourcesContainer = sourcesHeading.nextElementSibling;
            if (sourcesContainer && sourcesContainer.tagName === 'P') {
                const sourcesText = sourcesContainer.textContent;
                const sourcesArray = sourcesText.split(/\[(\d+)\]/).filter(s => s.trim());

                const sourcesList = document.createElement('div');
                sourcesList.className = 'sources-list';
                sourcesList.style.cssText = 'display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem;';

                for (let i = 0; i < sourcesArray.length; i += 2) {
                    if (sourcesArray[i] && sourcesArray[i + 1]) {
                        const sourceNumber = sourcesArray[i];
                        const sourceText = sourcesArray[i + 1].trim();

                        const sourceItem = document.createElement('div');
                        sourceItem.id = `source-${sourceNumber}`;
                        sourceItem.className = 'source-item';
                        sourceItem.style.cssText = 'padding: 0.75rem; background: hsl(var(--muted) / 0.3); border-radius: 0.25rem; transition: background 0.3s;';

                        const sourceNumberEl = document.createElement('span');
                        sourceNumberEl.style.cssText = 'font-weight: 600; color: hsl(var(--primary)); margin-right: 0.5rem;';
                        sourceNumberEl.textContent = `[${sourceNumber}]`;

                        const sourceContent = document.createElement('span');
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
    updateThemeIcons();
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return thinkingDiv;
}

// Send Message
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message || isStreaming) return;

    addMessage('user', message);
    messageInput.value = '';

    // Reset research state
    currentPhase = 1;
    phaseText = '';
    sourceCount = 0;
    sources = [];
    detailsExpanded = false;
    phases = [
        { id: 1, name: 'Strategie planen', icon: 'clipboard', status: 'pending' },
        { id: 2, name: 'Führe Recherche durch', icon: 'search', status: 'pending' },
        { id: 3, name: 'Synthese der Erkenntnisse', icon: 'lightbulb', status: 'pending' },
        { id: 4, name: 'Erstelle Bericht', icon: 'file-text', status: 'pending' }
    ];
    researchStatusContainer = null;
    currentActivity = '';

    const thinkingEl = addThinkingIndicator();
    isStreaming = true;
    sendBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Läuft...</span>';
    sendBtn.disabled = true;
    lucide.createIcons();
    updateThemeIcons();

    try {
        const url = `/api/chat/stream?thread_id=${sessionId}&message=${encodeURIComponent(message)}`;
        currentEventSource = new EventSource(url);

        currentEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'thinking') {
                    if (thinkingEl && thinkingEl.parentNode) {
                        thinkingEl.remove();
                    }
                    createResearchStatus();
                } else if (data.type === 'step_start') {
                    createResearchStatus();
                    // Use step_name for mapping (English name)
                    const stepName = data.step_name || data.name;
                    console.log('Step started:', stepName, data);
                    const phaseId = mapStepToPhase(stepName);
                    currentPhase = phaseId;
                    phaseText = phases[phaseId - 1].name;
                    updatePhase(phaseId, 'running');
                } else if (data.type === 'step_complete') {
                    // Use step_name for mapping (English name)
                    const stepName = data.step_name || data.name;
                    console.log('Step completed:', stepName, data);
                    const phaseId = mapStepToPhase(stepName);
                    updatePhase(phaseId, 'completed');
                } else if (data.type === 'tool_call_start') {
                    createResearchStatus();

                    // Show current activity for search tools
                    if (data.name === 'tavily_search' || data.name === 'arxiv_search' || data.name === 'pubmed_search' || data.name === 'web_search' || data.name === 'tavily_search_results_json') {
                        // Extract query to show what we're searching for
                        let query = '';
                        if (data.args && typeof data.args === 'object') {
                            if (data.args.queries && Array.isArray(data.args.queries)) {
                                query = data.args.queries[0];
                            } else if (data.args.query) {
                                query = data.args.query;
                            }
                        }

                        if (query) {
                            const shortQuery = query.length > 60 ? query.substring(0, 60) + '...' : query;
                            currentActivity = `"${shortQuery}"`;
                            updateResearchStatus();
                        }
                    }
                } else if (data.type === 'tool_call_complete') {
                    // Count actual sources from results
                    if (data.name === 'tavily_search' || data.name === 'arxiv_search' || data.name === 'pubmed_search' || data.name === 'web_search' || data.name === 'tavily_search_results_json') {
                        // Debug logging
                        console.log('🔍 Tool result type:', typeof data.result);
                        console.log('📄 Tool result preview:', data.result?.substring(0, 300));

                        // tavily_search returns a formatted string like "--- SOURCE 1: Title ---\nURL: https://..."
                        if (data.result && typeof data.result === 'string') {
                            // Count sources by matching "--- SOURCE X:" pattern
                            const sourceMatches = data.result.match(/--- SOURCE \d+:/g);
                            console.log('📊 Source pattern matches:', sourceMatches?.length || 0);

                            if (sourceMatches && sourceMatches.length > 0) {
                                const newSourceCount = sourceMatches.length;
                                sourceCount += newSourceCount;

                                // Extract titles and URLs from the result string
                                // Format: "--- SOURCE X: Title ---\nURL: https://...\n"
                                const titleRegex = /--- SOURCE \d+: (.+?) ---/g;
                                const urlRegex = /URL: (.+?)$/gm;

                                const titles = [];
                                const urls = [];

                                let titleMatch;
                                while ((titleMatch = titleRegex.exec(data.result)) !== null) {
                                    titles.push(titleMatch[1].trim());
                                }

                                let urlMatch;
                                while ((urlMatch = urlRegex.exec(data.result)) !== null) {
                                    urls.push(urlMatch[1].trim());
                                }

                                console.log('📝 Titles extracted:', titles.length);
                                console.log('🔗 URLs extracted:', urls.length);

                                // Combine titles and URLs into source objects
                                for (let i = 0; i < Math.min(titles.length, urls.length); i++) {
                                    const title = titles[i];
                                    const url = urls[i];
                                    const shortTitle = title.length > 80 ? title.substring(0, 80) + '...' : title;

                                    sources.push({
                                        title: shortTitle,
                                        url: url
                                    });
                                }

                                console.log('✅ Sources added:', sources.length);
                            } else {
                                // Fallback: No sources found in string
                                console.warn('⚠️ No SOURCE patterns found in result');
                                sourceCount += 1;
                                sources.push({
                                    title: 'Unbekannte Quelle',
                                    url: '#'
                                });
                            }
                        } else if (data.result && typeof data.result === 'object') {
                            // Fallback for different format (object/array)
                            let resultsArray = [];

                            if (Array.isArray(data.result)) {
                                resultsArray = data.result;
                            } else if (data.result.results && Array.isArray(data.result.results)) {
                                resultsArray = data.result.results;
                            }

                            if (resultsArray.length > 0) {
                                sourceCount += resultsArray.length;
                                resultsArray.forEach(result => {
                                    if (result.url || result.title) {
                                        const title = result.title || result.url;
                                        const url = result.url || '#';
                                        const shortTitle = title.length > 80 ? title.substring(0, 80) + '...' : title;
                                        sources.push({
                                            title: shortTitle,
                                            url: url
                                        });
                                    }
                                });
                            } else {
                                sourceCount += 1;
                                sources.push({
                                    title: 'Unbekannte Quelle',
                                    url: '#'
                                });
                            }
                        } else {
                            // Fallback: count as 1 source
                            sourceCount += 1;
                            sources.push({
                                title: 'Unbekannte Quelle',
                                url: '#'
                            });
                        }

                        updateResearchStatus();
                    }
                } else if (data.type === 'agent_message') {
                    completeResearch();
                    addMessage('agent', data.content);
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                } else if (data.type === 'done') {
                    completeResearch();
                    if (currentEventSource) {
                        currentEventSource.close();
                        currentEventSource = null;
                    }
                    isStreaming = false;
                    sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span class="hidden sm:inline">Senden</span>';
                    sendBtn.disabled = false;
                    lucide.createIcons();
                    updateThemeIcons();
                } else if (data.type === 'error') {
                    if (thinkingEl && thinkingEl.parentNode) {
                        thinkingEl.remove();
                    }
                    addMessage('agent', `❌ Fehler: ${data.error}`);
                    if (currentEventSource) {
                        currentEventSource.close();
                        currentEventSource = null;
                    }
                    isStreaming = false;
                    sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span class="hidden sm:inline">Senden</span>';
                    sendBtn.disabled = false;
                    lucide.createIcons();
                    updateThemeIcons();
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
            sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span class="hidden sm:inline">Senden</span>';
            sendBtn.disabled = false;
            lucide.createIcons();
            updateThemeIcons();
        };

    } catch (err) {
        console.error('Request error:', err);
        if (thinkingEl && thinkingEl.parentNode) {
            thinkingEl.remove();
        }
        addMessage('agent', `❌ Fehler: ${err.message}`);
        isStreaming = false;
        sendBtn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span class="hidden sm:inline">Senden</span>';
        sendBtn.disabled = false;
        lucide.createIcons();
        updateThemeIcons();
    }
});
