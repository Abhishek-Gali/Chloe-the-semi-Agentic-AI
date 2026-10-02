/**
 * Project Chloe - Web HUD Interactive Controller
 * Real-time WebSocket streaming, low-latency audio queue player, visualizer canvas, and MCP HUD.
 */

// Application State
let currentMode = "PARTIALLY_ISOLATED";
let speakEnabled = true;
let currentVoice = localStorage.getItem("chloe_voice") || "edge:en-US-AriaNeural";
let ws = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let analyser = null;
let visualizerAnimationId = null;
let activeAssistantBubble = null;
let activeAssistantRaw = "";

// Low-Latency Gapless Audio Playback Queue
class AudioPlaybackQueue {
    constructor() {
        this.queue = [];
        this.isPlaying = false;
        this.currentAudio = null;
    }

    enqueue(base64Audio) {
        if (!base64Audio) return;
        // Detect audio format (WAV header starts with UklGR or RIFF in b64, fallback to MP3)
        const mimeType = base64Audio.startsWith("UklGR") ? "audio/wav" : "audio/mp3";
        const audioSrc = `data:${mimeType};base64,${base64Audio}`;
        
        // Preload HTML5 Audio instance in advance to eliminate inter-sentence buffer latency
        const audioObj = new Audio(audioSrc);
        audioObj.preload = "auto";
        this.queue.push(audioObj);

        if (!this.isPlaying) {
            this.playNext();
        }
    }

    playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            this.currentAudio = null;
            
            // Hide stop button when done talking
            const stopBtn = document.getElementById("stopBtn");
            const sendBtn = document.getElementById("sendBtn");
            if (stopBtn) stopBtn.style.display = "none";
            if (sendBtn) sendBtn.style.display = "flex";

            if (autoListenMode) {
                document.getElementById('statusText').innerText = "HANDS-FREE // LISTENING...";
                setAvatarState("listening");
                if (webSpeechRecognizer && !isWebSpeechRunning) {
                    try {
                        webSpeechRecognizer.start();
                        isWebSpeechRunning = true;
                    } catch (e) {}
                }
            } else {
                document.getElementById('statusText').innerText = "CHLOE ONLINE // READY";
                setAvatarState("idle");
            }
            return;
        }

        this.isPlaying = true;
        setAvatarState("speaking");
        document.getElementById('statusText').innerText = "CHLOE SPEAKING...";
        this.currentAudio = this.queue.shift();
        
        this.currentAudio.onended = () => {
            this.playNext();
        };

        this.currentAudio.onerror = (e) => {
            console.warn("Audio playback error:", e);
            this.playNext();
        };

        this.currentAudio.play().catch(e => {
            console.warn("Autoplay block / playback error:", e);
            this.playNext();
        });
    }

    clear() {
        this.queue = [];
        if (this.currentAudio) {
            try { this.currentAudio.pause(); } catch(e) {}
            this.currentAudio = null;
        }
        this.isPlaying = false;
        
        // Hide stop button
        const stopBtn = document.getElementById("stopBtn");
        const sendBtn = document.getElementById("sendBtn");
        if (stopBtn) stopBtn.style.display = "none";
        if (sendBtn) sendBtn.style.display = "flex";

        setAvatarState("idle");
    }
}

/// Character Avatar State Controller for 4 Poses
let currentAvatarState = "idle";
let lipSyncInterval = null;
let blinkInterval = null;
let isReactingToClick = false;

function setAvatarState(state) {
    if (isReactingToClick && state === "idle") return;
    currentAvatarState = state;
    const container = document.getElementById("avatarSpriteContainer");
    const avatarImg = document.getElementById("chloeAvatarImg");
    const stateText = document.getElementById("avatarStateText");
    const stateDot = document.getElementById("avatarStateDot");
    if (!container || !avatarImg) return;

    container.dataset.state = state;

    if (lipSyncInterval) {
        clearInterval(lipSyncInterval);
        lipSyncInterval = null;
    }

    if (state === "speaking") {
        if (stateText) stateText.innerText = "CHLOE // SPEAKING";
        if (stateDot) stateDot.style.background = "#00f3ff";
        
        let mouthOpen = true;
        avatarImg.src = "/static/assets/avatar/chloe_speaking.png";
        lipSyncInterval = setInterval(() => {
            if (currentAvatarState !== "speaking") {
                clearInterval(lipSyncInterval);
                lipSyncInterval = null;
                return;
            }
            mouthOpen = !mouthOpen;
            avatarImg.src = mouthOpen 
                ? "/static/assets/avatar/chloe_speaking.png" 
                : "/static/assets/avatar/chloe_idle.png";
        }, 150);

    } else if (state === "listening") {
        avatarImg.src = "/static/assets/avatar/chloe_listening.png";
        if (stateText) stateText.innerText = "CHLOE // LISTENING";
        if (stateDot) stateDot.style.background = "#10b981";
    } else if (state === "thinking") {
        avatarImg.src = "/static/assets/avatar/chloe_thinking.png";
        if (stateText) stateText.innerText = "CHLOE // THINKING";
        if (stateDot) stateDot.style.background = "#a855f7";
    } else {
        avatarImg.src = "/static/assets/avatar/chloe_idle.png";
        if (stateText) stateText.innerText = "CHLOE // ONLINE";
        if (stateDot) stateDot.style.background = "#00f3ff";
    }
}

// Natural Periodic Blinking Loop
function initAvatarBlinkLoop() {
    if (blinkInterval) clearInterval(blinkInterval);
    
    blinkInterval = setInterval(() => {
        if (currentAvatarState === "idle" && !isReactingToClick) {
            const avatarImg = document.getElementById("chloeAvatarImg");
            if (avatarImg) {
                avatarImg.src = "/static/assets/avatar/chloe_blink.png";
                setTimeout(() => {
                    if (currentAvatarState === "idle" && !isReactingToClick) {
                        avatarImg.src = "/static/assets/avatar/chloe_idle.png";
                    }
                }, 150);
            }
        }
    }, 3500); // Blink every 3.5 seconds
}

function initAvatarEngine() {
    // Start blinking loop
    initAvatarBlinkLoop();

    // Click reaction: Force a quick blink as feedback
    const container = document.getElementById("avatarSpriteContainer");
    const avatarImg = document.getElementById("chloeAvatarImg");
    if (container && avatarImg) {
        container.addEventListener("click", () => {
            if (currentAvatarState !== "idle" || isReactingToClick) return;
            isReactingToClick = true;
            avatarImg.src = "/static/assets/avatar/chloe_blink.png";
            
            setTimeout(() => {
                isReactingToClick = false;
                setAvatarState(currentAvatarState);
            }, 200);
        });
    }
}

const audioQueue = new AudioPlaybackQueue();

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    initParticleGrid();
    initVisualizerCanvas();
    initEventHandlers();
    initAvatarEngine();
    fetchChatHistory();
    pollTelemetry();
    setInterval(pollTelemetry, 3000);
    autoDetectAndApplyKeys();
});

let serverKeysConfig = {
    groq_configured: false,
    gemini_configured: false,
    ollama_host: "http://localhost:11434",
    groq_model: "qwen/qwen3.8-27b",
    gemini_model: "gemini-3.6-flash"
};

// Refresh Active Model and API Key Status Badge in Top Bar
async function refreshActiveModelHud() {
    try {
        const res = await fetch("/api/config/keys");
        if (res.ok) {
            serverKeysConfig = await res.json();
        }
    } catch (e) {}

    const modelNameEl = document.getElementById("activeModelName");
    const modelTierEl = document.getElementById("activeModelTier");
    const modelIconEl = document.getElementById("modelBadgeIcon");
    const groqDot = document.getElementById("groqApiDot");
    const geminiDot = document.getElementById("geminiApiDot");

    if (groqDot) {
        groqDot.className = `api-dot ${serverKeysConfig.groq_configured ? 'active-key' : ''}`;
        groqDot.title = serverKeysConfig.groq_configured ? `Groq Active (${serverKeysConfig.groq_model})` : 'Groq API Key Missing';
    }
    if (geminiDot) {
        geminiDot.className = `api-dot ${serverKeysConfig.gemini_configured ? 'active-key' : ''}`;
        geminiDot.title = serverKeysConfig.gemini_configured ? `Gemini Active (${serverKeysConfig.gemini_model})` : 'Gemini API Key Missing';
    }

    if (currentMode === "FULLY_ISOLATED") {
        if (modelNameEl) modelNameEl.innerText = "chloe:latest";
        if (modelTierEl) modelTierEl.innerText = "OLLAMA // AIR-GAPPED";
        if (modelIconEl) modelIconEl.innerText = "🛡️";
    } else if (currentMode === "COMPLETELY_OPEN") {
        if (modelNameEl) modelNameEl.innerText = serverKeysConfig.gemini_model || "gemini-2.0-flash";
        if (modelTierEl) modelTierEl.innerText = "GEMINI // FRONTIER CLOUD";
        if (modelIconEl) modelIconEl.innerText = "🧠";
    } else {
        if (modelNameEl) modelNameEl.innerText = serverKeysConfig.groq_model || "llama-3.3-70b-versatile";
        if (modelTierEl) modelTierEl.innerText = "GROQ // HYBRID FAST-PATH";
        if (modelIconEl) modelIconEl.innerText = "⚡";
    }
}

// Auto-detect .env API keys and activate the right mode silently on startup
async function autoDetectAndApplyKeys() {
    try {
        const res = await fetch("/api/config/keys");
        if (!res.ok) return;
        const data = await res.json();
        serverKeysConfig = data;

        const chips = document.querySelectorAll(".mode-chip");

        if (data.gemini_configured) {
            // Gemini available → prefer Frontier Cloud
            chips.forEach(c => c.classList.remove("active"));
            chips.forEach(c => {
                if (c.dataset.mode === "COMPLETELY_OPEN") {
                    c.classList.add("active");
                    currentMode = "COMPLETELY_OPEN";
                }
            });
            console.log(`[Chloe] Auto-mode: Frontier Cloud (Gemini ${data.gemini_preview}, model: ${data.gemini_model})`);
        } else if (data.groq_configured) {
            // Only Groq → Hybrid Local
            chips.forEach(c => c.classList.remove("active"));
            chips.forEach(c => {
                if (c.dataset.mode === "PARTIALLY_ISOLATED") {
                    c.classList.add("active");
                    currentMode = "PARTIALLY_ISOLATED";
                }
            });
            console.log(`[Chloe] Auto-mode: Hybrid Local (Groq ${data.groq_preview}, model: ${data.groq_model})`);
        } else {
            // No cloud keys → Air-Gapped
            chips.forEach(c => c.classList.remove("active"));
            chips.forEach(c => {
                if (c.dataset.mode === "FULLY_ISOLATED") {
                    c.classList.add("active");
                    currentMode = "FULLY_ISOLATED";
                }
            });
            console.log("[Chloe] Auto-mode: Air-Gapped (no cloud keys found in .env)");
        }
        await refreshActiveModelHud();
    } catch (e) {
        console.warn("[Chloe] Could not auto-detect keys from server:", e);
    }
}

async function fetchChatHistory() {
    try {
        const res = await fetch("/api/history?limit=30");
        if (res.ok) {
            const data = await res.json();
            if (data.messages && data.messages.length > 0) {
                const chatContainer = document.getElementById("chatMessages");
                chatContainer.innerHTML = "";
                data.messages.forEach(msg => {
                    const msgDiv = document.createElement("div");
                    msgDiv.className = `message ${msg.role === "user" ? "user-message" : "chloe-message"}`;
                    
                    const avatar = document.createElement("div");
                    avatar.className = "avatar";
                    avatar.innerText = msg.role === "user" ? "AB" : "CH";

                    const bubble = document.createElement("div");
                    bubble.className = "bubble";
                    bubble.innerHTML = `<p>${escapeHtml(cleanAssistantOutput(msg.content))}</p>`;

                    msgDiv.appendChild(avatar);
                    msgDiv.appendChild(bubble);
                    chatContainer.appendChild(msgDiv);
                });
                scrollToBottom();
            }
        }
    } catch (e) {
        console.warn("Could not load conversation history:", e);
    }
}

// WebSocket Connection
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/audio`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("WebSocket connected to Chloe Gateway.");
        document.getElementById("statusText").innerText = "CHLOE ONLINE // READY";
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    ws.onclose = () => {
        console.log("WebSocket disconnected. Reconnecting in 2s...");
        document.getElementById("statusText").innerText = "CONNECTION LOST // RETRYING...";
        setTimeout(initWebSocket, 2000);
    };

    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

// Current streaming assistant message element & raw buffer
// Hands-Free Continuous Voice Activity Detection (VAD) State
let autoListenMode = false;
let autoAudioStream = null;
let autoAudioContext = null;
let autoAnalyser = null;
let autoVADLoopId = null;
let autoMediaRecorder = null;
let autoAudioChunks = [];
let isAutoRecordingActive = false;
let autoSilenceTimer = null;
let autoSpeechStartTime = 0;
const VAD_SPEECH_THRESHOLD = 0.0008; // Ultra-sensitive responsive laptop & headset microphone threshold
const VAD_SILENCE_DURATION_MS = 1200; // 1200ms natural human breathing pause before finalizing complete sentences

// Clean Assistant Output Helper (Double-layer regex)
function cleanAssistantOutput(text) {
    if (!text) return "";
    let cleaned = text;
    // Strip completed or in-flight <think> blocks
    cleaned = cleaned.replace(/<think>[\s\S]*?<\/think>/gi, "");
    cleaned = cleaned.replace(/<think>[\s\S]*/gi, "");
    // Strip raw tool json codeblocks
    cleaned = cleaned.replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/gi, "");
    cleaned = cleaned.replace(/```json[\s\S]*/gi, "");
    return cleaned;
}

function handleServerEvent(data) {
    const chatContainer = document.getElementById("chatMessages");
    const mcpLiveHud = document.getElementById("mcpLiveHud");
    const mcpToolName = document.getElementById("mcpToolName");
    const mcpToolDetails = document.getElementById("mcpToolDetails");

    switch (data.type) {
        case "model_info":
            if (data.model) {
                const modelNameEl = document.getElementById("activeModelName");
                const modelTierEl = document.getElementById("activeModelTier");
                const modelIconEl = document.getElementById("modelBadgeIcon");
                if (modelNameEl) modelNameEl.innerText = data.model;
                if (modelTierEl) {
                    if (data.mode === "FULLY_ISOLATED") {
                        modelTierEl.innerText = "OLLAMA // AIR-GAPPED";
                        if (modelIconEl) modelIconEl.innerText = "🛡️";
                    } else if (data.mode === "COMPLETELY_OPEN") {
                        modelTierEl.innerText = "GEMINI // FRONTIER CLOUD";
                        if (modelIconEl) modelIconEl.innerText = "🧠";
                    } else {
                        modelTierEl.innerText = "GROQ // HYBRID FAST-PATH";
                        if (modelIconEl) modelIconEl.innerText = "⚡";
                    }
                }
            }
            break;

        case "transcription":
            appendMessage("user", data.text);
            activeAssistantRaw = "";
            activeAssistantBubble = createAssistantMessage();
            
            // Show stop button, hide send button
            const tStopBtn = document.getElementById("stopBtn");
            const tSendBtn = document.getElementById("sendBtn");
            if (tStopBtn) tStopBtn.style.display = "flex";
            if (tSendBtn) tSendBtn.style.display = "none";
            break;

        case "token":
            if (!activeAssistantBubble) {
                activeAssistantRaw = "";
                activeAssistantBubble = createAssistantMessage();
            }
            if (!audioQueue.isPlaying) {
                setAvatarState("thinking");
            }
            activeAssistantRaw += data.token;
            const cleaned = cleanAssistantOutput(activeAssistantRaw);
            
            // Hide typing indicator once tokens start arriving
            const bubbleEl = activeAssistantBubble.closest(".bubble");
            if (bubbleEl) {
                const indicator = bubbleEl.querySelector(".typing-indicator");
                if (indicator && indicator.style.display !== "none") {
                    indicator.style.display = "none";
                }
            }
            activeAssistantBubble.style.display = "block";
            activeAssistantBubble.textContent = cleaned || activeAssistantRaw;
            scrollToBottom();
            
            // Ensure stop button is shown while tokens arrive
            const tokStopBtn = document.getElementById("stopBtn");
            const tokSendBtn = document.getElementById("sendBtn");
            if (tokStopBtn && tokStopBtn.style.display !== "flex") {
                tokStopBtn.style.display = "flex";
                if (tokSendBtn) tokSendBtn.style.display = "none";
            }
            break;

        case "sentence_audio":
            if (data.audio_base64 && speakEnabled) {
                audioQueue.enqueue(data.audio_base64);
            }
            break;

        case "tool_start":
            mcpLiveHud.style.display = "block";
            mcpToolName.innerText = `MCP: ${data.tool.toUpperCase()}`;
            mcpToolDetails.innerText = `Executing with params: ${JSON.stringify(data.params)}`;
            setAvatarState("thinking");
            
            // Show stop button during tool execution
            const tsStopBtn = document.getElementById("stopBtn");
            const tsSendBtn = document.getElementById("sendBtn");
            if (tsStopBtn) tsStopBtn.style.display = "flex";
            if (tsSendBtn) tsSendBtn.style.display = "none";
            break;

        case "tool_result":
            mcpLiveHud.style.display = "none";
            appendToolResultCard(data.tool, data.result);
            break;

        case "interrupted":
            // Stop button reset
            const intStopBtn = document.getElementById("stopBtn");
            const intSendBtn = document.getElementById("sendBtn");
            if (intStopBtn) intStopBtn.style.display = "none";
            if (intSendBtn) intSendBtn.style.display = "flex";
            
            if (activeAssistantBubble) {
                const bEl = activeAssistantBubble.closest(".bubble");
                if (bEl) {
                    const indicator = bEl.querySelector(".typing-indicator");
                    if (indicator) indicator.remove();
                }
                activeAssistantBubble.style.display = "block";
                activeAssistantBubble.textContent = (cleanAssistantOutput(activeAssistantRaw) || activeAssistantRaw) + " [Generation Stopped]";
            }
            activeAssistantBubble = null;
            activeAssistantRaw = "";
            audioQueue.clear();
            setAvatarState("idle");
            break;

        case "done":
            if (activeAssistantBubble) {
                const bubbleEl = activeAssistantBubble.closest(".bubble");
                if (bubbleEl) {
                    const indicator = bubbleEl.querySelector(".typing-indicator");
                    if (indicator) indicator.remove();
                }
                activeAssistantBubble.style.display = "block";
                const finalClean = cleanAssistantOutput(activeAssistantRaw);
                if (finalClean) {
                    activeAssistantBubble.textContent = finalClean;
                } else if (activeAssistantRaw) {
                    activeAssistantBubble.textContent = activeAssistantRaw;
                } else {
                    activeAssistantBubble.closest(".message")?.remove();
                }
            }
            activeAssistantBubble = null;
            activeAssistantRaw = "";
            
            // Only hide stop button and show send button if audio queue isn't speaking
            if (!audioQueue.isPlaying) {
                const dStopBtn = document.getElementById("stopBtn");
                const dSendBtn = document.getElementById("sendBtn");
                if (dStopBtn) dStopBtn.style.display = "none";
                if (dSendBtn) dSendBtn.style.display = "flex";
            }
            
            // Re-arm Hands-Free VAD if active and not already listening
            if (autoListenMode && !audioQueue.isPlaying) {
                document.getElementById("statusText").innerText = "HANDS-FREE // LISTENING...";
                setAvatarState("listening");
            } else if (!audioQueue.isPlaying) {
                setAvatarState("idle");
            }
            break;
    }
}

function appendMessage(role, text) {
    const chatContainer = document.getElementById("chatMessages");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role === "user" ? "user-message" : "chloe-message"}`;
    
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.innerText = role === "user" ? "AB" : "CH";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = `<p>${escapeHtml(text)}</p>`;

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
}

function createAssistantMessage() {
    const chatContainer = document.getElementById("chatMessages");
    const msgDiv = document.createElement("div");
    msgDiv.className = "message chloe-message";
    
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.innerText = "CH";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    
    // Model Tag Badge
    const activeName = document.getElementById("activeModelName")?.innerText || "chloe:latest";
    const tag = document.createElement("div");
    tag.className = "msg-model-tag";
    tag.innerText = `⚡ ${activeName}`;
    bubble.appendChild(tag);

    // Glowing cyber typing indicator animation
    const typingIndicator = document.createElement("div");
    typingIndicator.className = "typing-indicator";
    typingIndicator.innerHTML = "<span></span><span></span><span></span>";
    
    const p = document.createElement("p");
    p.style.display = "none";
    p.style.whiteSpace = "pre-wrap";

    bubble.appendChild(typingIndicator);
    bubble.appendChild(p);

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
    return p;
}

function appendToolResultCard(toolName, result) {
    // For background/system actions like launch_app, suppress raw JSON status dump
    if (toolName === "launch_app") {
        return;
    }

    const chatContainer = document.getElementById("chatMessages");
    const card = document.createElement("div");
    card.className = "mcp-card";
    card.style.margin = "8px 0";
    card.style.animation = "fadeIn 0.3s ease";
    
    card.innerHTML = `
        <div class="mcp-badge">
            <span>⚡</span>
            <span>TOOL OUTPUT: ${escapeHtml(toolName)}</span>
        </div>
        <div class="mcp-details" style="font-family: monospace; font-size: 0.8rem; overflow-x: auto; max-width: 100%;">
            <pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>
        </div>
    `;
    chatContainer.appendChild(card);
    scrollToBottom();
}

function stopProcessing() {
    // 1. Clear playback queue (this stops audio and sets state to idle/listening)
    audioQueue.clear();
    
    // 2. Hide stop button and show send button
    const stopBtn = document.getElementById("stopBtn");
    const sendBtn = document.getElementById("sendBtn");
    if (stopBtn) stopBtn.style.display = "none";
    if (sendBtn) sendBtn.style.display = "flex";
    
    // 3. Send stop command to backend WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
    }
    
    // 4. Handle UI state cleanup
    if (activeAssistantBubble) {
        // Remove typing indicator if exists
        const bubbleEl = activeAssistantBubble.closest(".bubble");
        if (bubbleEl) {
            const indicator = bubbleEl.querySelector(".typing-indicator");
            if (indicator) indicator.remove();
        }
        activeAssistantBubble.textContent = (cleanAssistantOutput(activeAssistantRaw) || activeAssistantRaw) + " [Generation Stopped]";
        activeAssistantBubble = null;
        activeAssistantRaw = "";
    }
    setAvatarState("idle");
}

function scrollToBottom() {
    const chatSection = document.getElementById("chatSection") || document.querySelector(".chat-section");
    if (chatSection) {
        chatSection.scrollTop = chatSection.scrollHeight;
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// User Interaction & Audio Recording
function initEventHandlers() {
    // Mode Switcher
    const modeChips = document.querySelectorAll(".mode-chip");
    modeChips.forEach(chip => {
        chip.addEventListener("click", () => {
            modeChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentMode = chip.dataset.mode;
            refreshActiveModelHud();
            console.log(`Operating mode set to: ${currentMode}`);
            
            // If switching to Cloud or Hybrid mode, free up background Ollama RAM
            if (currentMode !== "FULLY_ISOLATED") {
                fetch("/api/system/unload_ollama", { method: "POST" }).catch(() => {});
            }
        });
    });

    // Active Model HUD Click to open settings
    const activeModelHud = document.getElementById("activeModelHud");
    if (activeModelHud) {
        activeModelHud.addEventListener("click", openSettingsModal);
    }

    // Voice Speech Feedback Toggle Button
    const speakToggleBtn = document.getElementById("speakToggleBtn");
    if (speakToggleBtn) {
        speakToggleBtn.addEventListener("click", () => {
            speakEnabled = !speakEnabled;
            const label = speakToggleBtn.querySelector(".voice-toggle-label");
            if (speakEnabled) {
                speakToggleBtn.classList.remove("muted");
                speakToggleBtn.classList.add("active");
                if (label) label.innerText = "Voice ON";
                console.log("Voice Feedback ON (Kokoro Female Voice)");
            } else {
                speakToggleBtn.classList.remove("active");
                speakToggleBtn.classList.add("muted");
                if (label) label.innerText = "Voice OFF";
                audioQueue.clear();
                console.log("Voice Feedback OFF");
            }
        });
    }

    // Send Button & Enter Key
    const textInput = document.getElementById("textInput");
    const sendBtn = document.getElementById("sendBtn");

    function sendText() {
        const text = textInput.value.trim();
        if (!text || !ws) return;
        
        appendMessage("user", text);
        activeAssistantBubble = createAssistantMessage();
        
        // Show stop button, hide send button
        const stopBtn = document.getElementById("stopBtn");
        const sendBtn = document.getElementById("sendBtn");
        if (stopBtn) stopBtn.style.display = "flex";
        if (sendBtn) sendBtn.style.display = "none";

        lastDispatchedTime = Date.now();

        ws.send(JSON.stringify({
            text: text,
            mode: currentMode,
            speak: speakEnabled,
            voice: currentVoice
        }));
        
        textInput.value = "";
    }

    sendBtn.addEventListener("click", sendText);
    const stopBtn = document.getElementById("stopBtn");
    if (stopBtn) stopBtn.addEventListener("click", stopProcessing);
    
    textInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendText();
    });

    // Voice Selector Sync (Input Bar & Settings Modal)
    const voiceSelect = document.getElementById("voiceSelect");
    const modalVoiceSelect = document.getElementById("modalVoiceSelect");

    if (voiceSelect) {
        voiceSelect.value = currentVoice;
        voiceSelect.addEventListener("change", (e) => {
            currentVoice = e.target.value;
            localStorage.setItem("chloe_voice", currentVoice);
            if (modalVoiceSelect) modalVoiceSelect.value = currentVoice;
            console.log("Voice changed to:", currentVoice);
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "voice_change", voice: currentVoice }));
            }
        });
    }

    if (modalVoiceSelect) {
        modalVoiceSelect.value = currentVoice;
        modalVoiceSelect.addEventListener("change", (e) => {
            currentVoice = e.target.value;
            localStorage.setItem("chloe_voice", currentVoice);
            if (voiceSelect) voiceSelect.value = currentVoice;
            console.log("Modal Voice changed to:", currentVoice);
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "voice_change", voice: currentVoice }));
            }
        });
    }

    // Mic Manual Toggle Button
    const micBtn = document.getElementById("micBtn");
    if (micBtn) micBtn.addEventListener("click", toggleRecording);

    // Hands-Free Auto-Listen Toggle Button
    const autoListenBtn = document.getElementById("autoListenBtn");
    if (autoListenBtn) autoListenBtn.addEventListener("click", toggleAutoListen);

    // Modals & Sidebar Panels
    const vaultBtn = document.getElementById("vaultBtn");
    const uploadModal = document.getElementById("uploadModal") || document.getElementById("vaultModal");
    const closeUploadBtn = document.getElementById("closeUploadBtn") || document.getElementById("closeVaultBtn");

    if (vaultBtn) {
        vaultBtn.addEventListener("click", () => {
            const ragPanel = document.getElementById("ragMonitorPanel");
            if (ragPanel) {
                ragPanel.style.display = (ragPanel.style.display === "none" ? "flex" : "none");
            }
            if (uploadModal) uploadModal.classList.add("active");
        });
    }
    if (closeUploadBtn && uploadModal) {
        closeUploadBtn.addEventListener("click", () => uploadModal.classList.remove("active"));
    }

    const qrBtn = document.getElementById("qrBtn");
    const qrModal = document.getElementById("qrModal");
    const closeQrBtn = document.getElementById("closeQrBtn");

    if (qrBtn) qrBtn.addEventListener("click", openQrModal);
    if (closeQrBtn && qrModal) closeQrBtn.addEventListener("click", () => qrModal.classList.remove("active"));

    // Settings Modal
    const settingsBtn = document.getElementById("settingsBtn");
    const settingsModal = document.getElementById("settingsModal");
    const closeSettingsBtn = document.getElementById("closeSettingsBtn");
    const saveKeysBtn = document.getElementById("saveKeysBtn");

    if (settingsBtn) settingsBtn.addEventListener("click", openSettingsModal);
    if (closeSettingsBtn && settingsModal) closeSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("active"));
    if (saveKeysBtn) saveKeysBtn.addEventListener("click", saveSettingsKeys);

    // System & Launch Control Actions
    const refreshStatsBtn = document.getElementById("refreshStatsBtn");
    if (refreshStatsBtn) refreshStatsBtn.addEventListener("click", pollTelemetry);

    const flushVaultBtn = document.getElementById("flushVaultBtn");
    if (flushVaultBtn) flushVaultBtn.addEventListener("click", flushChromaAndContext);

    // 1-Click Quick Launcher Buttons
    document.querySelectorAll(".launcher-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const cmd = btn.getAttribute("data-cmd");
            if (cmd) {
                const textInput = document.getElementById("textInput");
                if (textInput) {
                    textInput.value = cmd;
                    sendText();
                }
            }
        });
    });

    // Mini Dropzone File Input
    const miniDropZone = document.getElementById("miniDropZone");
    const miniFileInput = document.getElementById("miniFileInput");
    if (miniDropZone && miniFileInput) {
        miniDropZone.addEventListener("click", () => miniFileInput.click());
        miniFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) uploadVaultFile(e.target.files[0]);
        });
    }

    // Modal File Input
    const fileInput = document.getElementById("fileInput");
    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) uploadVaultFile(e.target.files[0]);
        });
    }

    // Setup Chat Drag and Drop
    setupChatDragAndDrop();

    // Fetch initial RAG Vault Stats
    fetchVaultStats();
}

// Studio-Grade Microphone Audio Constraints (Universal Driver Compatibility)
const STUDIO_AUDIO_CONSTRAINTS = {
    audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
    }
};

// Global Voice State
let webSpeechRecognizer = null;
let webSpeechTranscript = "";
let isWebSpeechRunning = false;
let latestLiveTranscript = "";
let isDispatchingSpeech = false;
let lastDispatchedSpeech = "";
let lastDispatchedTime = 0;

function dispatchVoiceMessage(text) {
    if (!text || !text.trim()) return;
    const cleanText = text.trim();
    const now = Date.now();

    // Prevent duplicate dispatch within 1.5 seconds
    if (cleanText.toLowerCase() === lastDispatchedSpeech.toLowerCase() && (now - lastDispatchedTime) < 1500) {
        console.log("Suppressed duplicate voice dispatch:", cleanText);
        return;
    }

    if (isDispatchingSpeech) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    isDispatchingSpeech = true;
    lastDispatchedSpeech = cleanText;
    lastDispatchedTime = now;
    webSpeechTranscript = "";
    latestLiveTranscript = "";
    autoAudioChunks = [];

    // Safely stop any pending recorders without triggering onstop
    if (autoMediaRecorder && autoMediaRecorder.state !== "inactive") {
        try {
            autoMediaRecorder.ondataavailable = null;
            autoMediaRecorder.onstop = null;
            autoMediaRecorder.stop();
        } catch (e) {}
    }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        try {
            mediaRecorder.ondataavailable = null;
            mediaRecorder.onstop = null;
            mediaRecorder.stop();
        } catch (e) {}
        isRecording = false;
        const micBtn = document.getElementById("micBtn");
        if (micBtn) micBtn.classList.remove("recording");
    }
    isAutoRecordingActive = false;

    appendMessage("user", cleanText);
    activeAssistantBubble = createAssistantMessage();
    
    // Show stop button, hide send button
    const stopBtn = document.getElementById("stopBtn");
    const sendBtn = document.getElementById("sendBtn");
    if (stopBtn) stopBtn.style.display = "flex";
    if (sendBtn) sendBtn.style.display = "none";

    ws.send(JSON.stringify({
        text: cleanText,
        mode: currentMode,
        speak: speakEnabled,
        voice: currentVoice
    }));
    document.getElementById("statusText").innerText = "PROCESSING DIRECTIVE...";

    setTimeout(() => {
        isDispatchingSpeech = false;
    }, 1000);
}

function initWebSpeechEngine() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    try {
        const sr = new SpeechRecognition();
        sr.continuous = true;
        sr.interimResults = true;
        sr.lang = "en-US";
           sr.onresult = (event) => {
            let interim = "";
            let finalPart = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalPart += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }
            if (finalPart) {
                webSpeechTranscript = (webSpeechTranscript + " " + finalPart).trim();
            }
            latestLiveTranscript = (webSpeechTranscript + " " + interim).trim();
            if (latestLiveTranscript) {
                document.getElementById("statusText").innerText = `HEARING: "${latestLiveTranscript}"`;

                // Voice Interrupt: If user speaks while Chloe is talking or generating, stop her instantly!
                // Only trigger if at least 2 seconds have passed since the user sent their query to avoid self-interruption.
                const now = Date.now();
                const stopBtn = document.getElementById("stopBtn");
                if (now - lastDispatchedTime > 2000) {
                    if (audioQueue.isPlaying || (stopBtn && stopBtn.style.display === "flex")) {
                        console.log("Speech detected during Chloe speech/generation. Interrupting.");
                        stopProcessing();
                    }
                }

                // In Hands-Free mode, reset silence countdown so user can pause naturally between words
                if (autoListenMode && !audioQueue.isPlaying) {
                    if (autoSilenceTimer) {
                        clearTimeout(autoSilenceTimer);
                    }
                    autoSilenceTimer = setTimeout(() => {
                        const fullSentence = (webSpeechTranscript || latestLiveTranscript).trim();
                        if (fullSentence && autoListenMode && !audioQueue.isPlaying) {
                            dispatchVoiceMessage(fullSentence);
                        }
                        autoSilenceTimer = null;
                    }, VAD_SILENCE_DURATION_MS);
                }
            }
        };

        sr.onend = () => {
            isWebSpeechRunning = false;
            if (autoListenMode && !audioQueue.isPlaying) {
                try {
                    sr.start();
                    isWebSpeechRunning = true;
                } catch (e) {}
            }
        };

        sr.onerror = (e) => {
            if (e.error !== "no-speech") {
                console.log("Web Speech API note:", e.error);
            }
        };

        return sr;
    } catch (e) {
        return null;
    }
}

// 1. Manual Recording & Audio Capture
async function toggleRecording() {
    const micBtn = document.getElementById("micBtn");
    
    if (!isRecording) {
        try {
            webSpeechTranscript = "";
            latestLiveTranscript = "";
            if (!webSpeechRecognizer) {
                webSpeechRecognizer = initWebSpeechEngine();
            }
            if (webSpeechRecognizer && !isWebSpeechRunning) {
                try {
                    webSpeechRecognizer.start();
                    isWebSpeechRunning = true;
                } catch (e) {}
            }

            const stream = await navigator.mediaDevices.getUserMedia(STUDIO_AUDIO_CONSTRAINTS);
            
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (audioContext.state === "suspended") {
                await audioContext.resume();
            }
            const source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 128;
            source.connect(analyser);

            const mimeType = (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("audio/webm;codecs=opus"))
                ? "audio/webm;codecs=opus"
                : "audio/webm";

            mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                if (audioChunks.length > 0) {
                    const audioBlob = new Blob(audioChunks, { type: mimeType });
                    const arrayBuffer = await audioBlob.arrayBuffer();
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        document.getElementById("statusText").innerText = "TRANSCRIBING AUDIO (WHISPER)...";
                        ws.send(arrayBuffer);
                    }
                }
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start(50);
            isRecording = true;
            micBtn.classList.add("recording");
            document.getElementById("statusText").innerText = "LISTENING TO ABHISHEK...";
        } catch (err) {
            console.error("Mic access failed:", err);
            alert("Microphone access denied or unavailable.");
        }
    } else {
        if (webSpeechRecognizer && isWebSpeechRunning) {
            try {
                webSpeechRecognizer.stop();
                isWebSpeechRunning = false;
            } catch (e) {}
        }
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }
        isRecording = false;
        micBtn.classList.remove("recording");
    }
}

// 2. Hands-Free Continuous Voice Activity Detection (VAD) Mode
async function toggleAutoListen() {
    const autoBtn = document.getElementById("autoListenBtn");
    const label = autoBtn.querySelector(".auto-listen-label");

    autoListenMode = !autoListenMode;

    if (autoListenMode) {
        try {
            webSpeechTranscript = "";
            latestLiveTranscript = "";
            if (!webSpeechRecognizer) {
                webSpeechRecognizer = initWebSpeechEngine();
            }
            if (webSpeechRecognizer && !isWebSpeechRunning) {
                try {
                    webSpeechRecognizer.start();
                    isWebSpeechRunning = true;
                } catch (e) {}
            }

            autoAudioStream = await navigator.mediaDevices.getUserMedia(STUDIO_AUDIO_CONSTRAINTS);
            if (!autoAudioContext) {
                autoAudioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (autoAudioContext.state === "suspended") {
                await autoAudioContext.resume();
            }
            const source = autoAudioContext.createMediaStreamSource(autoAudioStream);
            autoAnalyser = autoAudioContext.createAnalyser();
            autoAnalyser.fftSize = 256;
            source.connect(autoAnalyser);

            autoBtn.classList.add("active");
            if (label) label.innerText = "Hands-Free: ON";
            document.getElementById("statusText").innerText = "HANDS-FREE // LISTENING...";
            console.log("Hands-Free Continuous Mode Activated.");

            startVADMonitoring();
        } catch (err) {
            console.error("Hands-Free Mic init failed:", err);
            alert("Could not access microphone for Hands-Free mode.");
            autoListenMode = false;
            autoBtn.classList.remove("active");
            if (label) label.innerText = "Hands-Free: OFF";
        }
    } else {
        stopVADMonitoring();
        autoBtn.classList.remove("active", "listening");
        if (label) label.innerText = "Hands-Free: OFF";
        document.getElementById("statusText").innerText = "CHLOE ONLINE // READY";
        console.log("Hands-Free Continuous Mode Deactivated.");
    }
}

function startVADMonitoring() {
    const dataArray = new Float32Array(autoAnalyser.fftSize);

    function checkAudioLevel() {
        if (!autoListenMode) return;

        // If Chloe is actively speaking out loud, pause VAD listening to avoid self-feedback
        if (audioQueue.isPlaying) {
            autoVADLoopId = requestAnimationFrame(checkAudioLevel);
            return;
        }

        autoAnalyser.getFloatTimeDomainData(dataArray);

        // Compute Root-Mean-Square (RMS) amplitude
        let sumSquares = 0.0;
        for (let i = 0; i < dataArray.length; i++) {
            sumSquares += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);

        const autoBtn = document.getElementById("autoListenBtn");

        // Speech Detected
        if (rms > VAD_SPEECH_THRESHOLD) {
            if (!isAutoRecordingActive) {
                isAutoRecordingActive = true;
                autoSpeechStartTime = Date.now();
                autoAudioChunks = [];

                const mimeType = (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("audio/webm;codecs=opus"))
                    ? "audio/webm;codecs=opus"
                    : "audio/webm";

                autoMediaRecorder = new MediaRecorder(autoAudioStream, { mimeType: mimeType });

                autoMediaRecorder.ondataavailable = (e) => {
                    if (e.data.size > 0) autoAudioChunks.push(e.data);
                };

                autoMediaRecorder.onstop = async () => {
                    if (autoAudioChunks.length > 0 && !isDispatchingSpeech) {
                        const audioBlob = new Blob(autoAudioChunks, { type: mimeType });
                        if (audioBlob.size > 1000 && ws && ws.readyState === WebSocket.OPEN) {
                            const arrayBuffer = await audioBlob.arrayBuffer();
                            document.getElementById("statusText").innerText = "TRANSCRIBING AUDIO (WHISPER)...";
                            ws.send(arrayBuffer);
                        }
                    }
                };

                autoMediaRecorder.start(40);
                autoBtn.classList.add("listening");
                document.getElementById("statusText").innerText = "LISTENING TO ABHISHEK...";
            }

            // Reset silence countdown while user continues speaking
            if (autoSilenceTimer) {
                clearTimeout(autoSilenceTimer);
                autoSilenceTimer = null;
            }
        } else {
            // User is silent
            if (isAutoRecordingActive && !autoSilenceTimer) {
                autoSilenceTimer = setTimeout(() => {
                    if (isAutoRecordingActive) {
                        if (autoMediaRecorder && autoMediaRecorder.state !== "inactive") {
                            autoMediaRecorder.stop();
                        }
                        isAutoRecordingActive = false;
                        autoBtn.classList.remove("listening");
                        if (autoListenMode && !audioQueue.isPlaying) {
                            document.getElementById("statusText").innerText = "HANDS-FREE // LISTENING...";
                        }
                    }
                    autoSilenceTimer = null;
                }, VAD_SILENCE_DURATION_MS);
            }
        }

        autoVADLoopId = requestAnimationFrame(checkAudioLevel);
    }

    autoVADLoopId = requestAnimationFrame(checkAudioLevel);
}

function stopVADMonitoring() {
    if (autoVADLoopId) {
        cancelAnimationFrame(autoVADLoopId);
        autoVADLoopId = null;
    }
    if (autoSilenceTimer) {
        clearTimeout(autoSilenceTimer);
        autoSilenceTimer = null;
    }
    if (autoMediaRecorder && autoMediaRecorder.state !== "inactive") {
        try { autoMediaRecorder.stop(); } catch (e) {}
    }
    if (autoAudioStream) {
        autoAudioStream.getTracks().forEach(track => track.stop());
        autoAudioStream = null;
    }
    if (webSpeechRecognizer && isWebSpeechRunning) {
        try {
            webSpeechRecognizer.stop();
            isWebSpeechRunning = false;
        } catch (e) {}
    }
    isAutoRecordingActive = false;
}

// Visualizer Wave Animation
function initVisualizerCanvas() {
    const canvas = document.getElementById("waveCanvas");
    const ctx = canvas.getContext("2d");
    const dataArray = new Uint8Array(64);

    function draw() {
        requestAnimationFrame(draw);
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = 45;

        if (analyser && isRecording) {
            analyser.getByteFrequencyData(dataArray);
        } else if (autoAnalyser && autoListenMode) {
            autoAnalyser.getByteFrequencyData(dataArray);
        } else {
            // Idle subtle pulsating wave
            for (let i = 0; i < dataArray.length; i++) {
                dataArray[i] = 10 + Math.sin(Date.now() * 0.003 + i * 0.2) * 8;
            }
        }

        ctx.beginPath();
        for (let i = 0; i < dataArray.length; i++) {
            const angle = (i / dataArray.length) * Math.PI * 2;
            const barHeight = (dataArray[i] / 255) * 25;
            const r = radius + barHeight;
            const x = centerX + Math.cos(angle) * r;
            const y = centerY + Math.sin(angle) * r;

            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = "#00f3ff";
        ctx.lineWidth = 2;
        ctx.shadowBlur = 12;
        ctx.shadowColor = "#00f3ff";
        ctx.stroke();
    }

    draw();
}

// Background Particle Grid
function initParticleGrid() {
    const canvas = document.getElementById("bg-canvas");
    const ctx = canvas.getContext("2d");

    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener("resize", () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const particles = [];
    for (let i = 0; i < 45; i++) {
        particles.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            radius: Math.random() * 1.5 + 0.5
        });
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "rgba(0, 243, 255, 0.25)";

        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();
        });

        requestAnimationFrame(animate);
    }
    animate();
}

// Telemetry Poller
async function pollTelemetry() {
    try {
        const res = await fetch("/api/system/info");
        if (res.ok) {
            const data = await res.json();
            if (data.cpu) {
                const cpuVal = `${data.cpu.percent}%`;
                const topCpu = document.querySelector("#cpuStat .stat-val");
                if (topCpu) topCpu.innerText = cpuVal;
                
                const sideCpuVal = document.getElementById("sidebarCpuVal");
                if (sideCpuVal) sideCpuVal.innerText = cpuVal;
                
                const sideCpuFill = document.getElementById("sidebarCpuFill");
                if (sideCpuFill) sideCpuFill.style.width = `${Math.min(100, Math.max(0, data.cpu.percent))}%`;
            }
            if (data.memory) {
                const memVal = `${data.memory.used_percent}%`;
                const topMem = document.querySelector("#memStat .stat-val");
                if (topMem) topMem.innerText = memVal;

                const sideMemVal = document.getElementById("sidebarMemVal");
                if (sideMemVal) sideMemVal.innerText = memVal;

                const sideMemFill = document.getElementById("sidebarMemFill");
                if (sideMemFill) sideMemFill.style.width = `${Math.min(100, Math.max(0, data.memory.used_percent))}%`;
            }
            if (data.os) {
                const osBadge = document.getElementById("hostOsBadge");
                if (osBadge) osBadge.innerText = data.os.system ? data.os.system.toUpperCase() : "WIN-64";
            }
        }
    } catch (e) {}
}

// ==========================================
// RAG & ChromaDB Live Monitor & Ingestion
// ==========================================

async function fetchVaultStats() {
    try {
        const res = await fetch("/api/vault/stats");
        if (res.ok) {
            const data = await res.json();
            
            // Update total chunks badge
            const totalChunksEl = document.getElementById("vaultTotalChunks");
            if (totalChunksEl) totalChunksEl.innerText = `${data.total_chunks || 0} Chunks`;

            // Update document list
            const docListEl = document.getElementById("vaultDocList");
            if (docListEl) {
                if (!data.documents || data.documents.length === 0) {
                    docListEl.innerHTML = `<div class="empty-docs-msg" id="emptyDocsMsg">No documents indexed in ChromaDB yet.</div>`;
                } else {
                    docListEl.innerHTML = "";
                    data.documents.forEach(doc => {
                        const item = document.createElement("div");
                        item.className = "vault-doc-item";
                        item.innerHTML = `
                            <div class="doc-info" onclick="askDocumentQuestion('${escapeHtml(doc.source)}')">
                                <span class="doc-name" title="${escapeHtml(doc.source)}">📄 ${escapeHtml(doc.source)}</span>
                                <span class="doc-meta">${doc.chunks} chunks • ${doc.char_count || '~'} chars</span>
                            </div>
                            <div class="doc-actions">
                                <button class="doc-ask-btn" onclick="askDocumentQuestion('${escapeHtml(doc.source)}')" title="Ask questions about this document">Ask</button>
                                <button class="doc-del-btn" onclick="deleteVaultDocument('${escapeHtml(doc.source)}')" title="Delete from ChromaDB">🗑️</button>
                            </div>
                        `;
                        docListEl.appendChild(item);
                    });
                }
            }

            // Estimate context token load (approx 4 chars/token from loaded messages & chunks)
            const chatMessages = document.getElementById("chatMessages");
            const charTotal = chatMessages ? chatMessages.innerText.length : 120;
            const approxTokens = Math.max(80, Math.floor(charTotal / 3.8));
            const maxTokens = 128000;
            const pct = Math.min(100, Math.max(1, ((approxTokens / maxTokens) * 100).toFixed(1)));

            const tokenCountEl = document.getElementById("contextTokenCount");
            if (tokenCountEl) tokenCountEl.innerText = `~${approxTokens.toLocaleString()} tokens loaded`;

            const contextPctEl = document.getElementById("contextPct");
            if (contextPctEl) contextPctEl.innerText = `${pct}%`;

            const contextFillEl = document.getElementById("contextProgressFill");
            if (contextFillEl) contextFillEl.style.width = `${pct}%`;
        }
    } catch (e) {
        console.warn("Error fetching vault stats:", e);
    }
}

async function deleteVaultDocument(filename) {
    if (!confirm(`Delete "${filename}" from ChromaDB vector vault?`)) return;

    try {
        const res = await fetch(`/api/vault/document/${encodeURIComponent(filename)}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            appendMessage("chloe", `Document "${filename}" was removed from the ChromaDB vector vault.`);
            fetchVaultStats();
        } else {
            alert(`Failed to delete document: ${data.message}`);
        }
    } catch (e) {
        alert("Network error deleting document.");
    }
}

async function flushChromaAndContext() {
    if (!confirm("Flush all ChromaDB vector embeddings and reset conversation memory? This cannot be undone.")) return;

    try {
        const res = await fetch("/api/vault/flush", {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            const chatContainer = document.getElementById("chatMessages");
            chatContainer.innerHTML = `
                <div class="message chloe-message">
                    <div class="avatar">CH</div>
                    <div class="bubble">
                        <p>Memory context and ChromaDB vector vault have been completely flushed and reset to zero. All systems fresh and ready.</p>
                    </div>
                </div>
            `;
            fetchVaultStats();
            document.getElementById("statusText").innerText = "CHLOE ONLINE // VAULT FLUSHED";
        }
    } catch (e) {
        alert("Network error flushing vault.");
    }
}

function askDocumentQuestion(filename) {
    const textInput = document.getElementById("textInput");
    textInput.value = `Tell me what insights and details are inside ${filename}?`;
    textInput.focus();
}

function setupChatDragAndDrop() {
    const chatSection = document.getElementById("chatSection");
    const dropOverlay = document.getElementById("dropOverlay");

    if (!chatSection || !dropOverlay) return;

    ["dragenter", "dragover"].forEach(eventName => {
        chatSection.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropOverlay.classList.add("active");
            chatSection.classList.add("drag-active");
        }, false);
    });

    ["dragleave", "dragend"].forEach(eventName => {
        chatSection.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropOverlay.classList.remove("active");
            chatSection.classList.remove("drag-active");
        }, false);
    });

    chatSection.addEventListener("drop", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropOverlay.classList.remove("active");
        chatSection.classList.remove("drag-active");

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            uploadVaultFile(files[0]);
        }
    }, false);
}

// Multi-Stage Document Ingestion
async function uploadVaultFile(file) {
    const ingestionCard = document.getElementById("ingestionCard");
    const fileNameEl = document.getElementById("ingestFileName");
    const statusTagEl = document.getElementById("ingestStatusTag");
    const progressBar = document.getElementById("ingestProgressBar");
    const stepText = document.getElementById("ingestStepText");
    const statusDiv = document.getElementById("uploadStatus");

    if (ingestionCard) {
        ingestionCard.style.display = "flex";
        fileNameEl.innerText = file.name;
        statusTagEl.innerText = "PARSING (20%)";
        progressBar.style.width = "25%";
        stepText.innerText = "Extracting text & optical elements...";
    }
    if (statusDiv) {
        statusDiv.innerHTML = `<span style="color: var(--accent-cyan)">Ingesting <b>${file.name}</b> to Split-Path RAG...</span>`;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", currentMode);

    // Progress simulation during upload/processing
    const timer1 = setTimeout(() => {
        if (statusTagEl) statusTagEl.innerText = "CHUNKING (60%)";
        if (progressBar) progressBar.style.width = "65%";
        if (stepText) stepText.innerText = "Splitting semantic context windows...";
    }, 400);

    const timer2 = setTimeout(() => {
        if (statusTagEl) statusTagEl.innerText = "EMBEDDING (85%)";
        if (progressBar) progressBar.style.width = "88%";
        if (stepText) stepText.innerText = "Generating dense vector embeddings...";
    }, 900);

    try {
        const res = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });
        clearTimeout(timer1);
        clearTimeout(timer2);
        
        const data = await res.json();
        if (res.ok) {
            if (statusTagEl) statusTagEl.innerText = "INDEXED (100%)";
            if (progressBar) progressBar.style.width = "100%";
            const chunks = data.fast_path?.chunks_indexed || 1;
            if (stepText) stepText.innerText = `Stored ${chunks} chunks in ChromaDB!`;
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--accent-emerald)">✓ Successfully indexed <b>${data.filename}</b> (${chunks} chunks) into ChromaDB!</span>`;
            }

            appendMessage("chloe", `Document "${data.filename}" ingested into ChromaDB (${chunks} semantic chunks). Ask me anything about it!`);
            
            const textInput = document.getElementById("textInput");
            textInput.value = `Analyze "${data.filename}" and summarize its core points.`;
            textInput.focus();

            fetchVaultStats();

            setTimeout(() => {
                if (ingestionCard) ingestionCard.style.display = "none";
            }, 3000);
        } else {
            if (statusTagEl) statusTagEl.innerText = "ERROR";
            if (stepText) stepText.innerText = data.message || "Failed to index.";
            if (statusDiv) {
                statusDiv.innerHTML = `<span style="color: var(--accent-rose)">Upload failed: ${data.message || "Error"}</span>`;
            }
        }
    } catch (err) {
        clearTimeout(timer1);
        clearTimeout(timer2);
        if (statusTagEl) statusTagEl.innerText = "FAILED";
        if (stepText) stepText.innerText = "Network error during upload.";
        if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: var(--accent-rose)">Network error uploading file.</span>`;
        }
    }
}

// Android Remote QR Modal
async function openQrModal() {
    const qrModal = document.getElementById("qrModal");
    const netDetails = document.getElementById("networkDetails");
    qrModal.classList.add("active");

    try {
        const res = await fetch("/api/network");
        if (res.ok) {
            const data = await res.json();
            const hostIp = data.local_ips[0] || "localhost";
            const appUrl = `http://${hostIp}:${data.port}`;
            
            netDetails.innerHTML = `
                <div><b>Local LAN IP:</b> ${hostIp}</div>
                <div><b>App URL:</b> <a href="${appUrl}" target="_blank" style="color: var(--accent-cyan)">${appUrl}</a></div>
                <div><b>WebSocket:</b> ${data.ws_url}</div>
            `;

            // Generate QR Code via reliable SVG image generator
            const qrImg = document.getElementById("qrImage");
            qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(appUrl)}`;
            qrImg.style.display = "block";
        }
    } catch (e) {
        netDetails.innerText = "Error loading network topology.";
    }
}

// Settings Modal Handler
async function openSettingsModal() {
    const modal = document.getElementById("settingsModal");
    const statusDiv = document.getElementById("settingsSaveStatus");
    statusDiv.innerHTML = "";
    modal.classList.add("active");

    try {
        const res = await fetch("/api/config/keys");
        if (res.ok) {
            const data = await res.json();

            const groqInput = document.getElementById("groqKeyInput");
            const geminiInput = document.getElementById("geminiKeyInput");
            const ollamaInput = document.getElementById("ollamaHostInput");

            // Auto-fill values from .env so fields are never empty
            if (data.groq_configured && data.groq_full) {
                groqInput.value = data.groq_full;
                groqInput.placeholder = `Active (${data.groq_preview})`;
            } else if (data.groq_configured) {
                groqInput.placeholder = `✅ Active (${data.groq_preview}) — loaded from .env`;
            }

            if (data.gemini_configured && data.gemini_full) {
                geminiInput.value = data.gemini_full;
                geminiInput.placeholder = `Active (${data.gemini_preview})`;
            } else if (data.gemini_configured) {
                geminiInput.placeholder = `✅ Active (${data.gemini_preview}) — loaded from .env`;
            }

            if (data.ollama_host) {
                ollamaInput.value = data.ollama_host;
            }

            // Show key status summary
            const groqStatus = data.groq_configured ? `<span style="color:var(--accent-emerald)">✅ Groq Ready (${data.groq_preview})</span>` : `<span style="color:var(--accent-rose)">❌ Groq key missing</span>`;
            const geminiStatus = data.gemini_configured ? `<span style="color:var(--accent-emerald)">✅ Gemini Ready (${data.gemini_preview})</span>` : `<span style="color:var(--accent-rose)">❌ Gemini key missing</span>`;
            statusDiv.innerHTML = `${groqStatus} &nbsp;|&nbsp; ${geminiStatus}`;
        }
    } catch (e) {
        statusDiv.innerHTML = `<span style="color:var(--accent-rose)">Could not load key status from server.</span>`;
    }
}

async function saveSettingsKeys() {
    const groqKey = document.getElementById("groqKeyInput").value.trim();
    const geminiKey = document.getElementById("geminiKeyInput").value.trim();
    const ollamaHost = document.getElementById("ollamaHostInput").value.trim();
    const statusDiv = document.getElementById("settingsSaveStatus");

    statusDiv.innerHTML = `<span style="color: var(--accent-cyan)">Saving configuration...</span>`;

    const payload = {};
    if (groqKey) payload.groq_api_key = groqKey;
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (ollamaHost) payload.ollama_host = ollamaHost;

    try {
        const res = await fetch("/api/config/keys", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            statusDiv.innerHTML = `<span style="color: var(--accent-emerald)">✓ ${data.message}</span>`;

            // Auto-switch mode based on what keys are now active
            if (geminiKey) {
                // Gemini key saved → auto-activate Frontier Cloud mode
                const chips = document.querySelectorAll(".mode-chip");
                chips.forEach(c => c.classList.remove("active"));
                chips.forEach(c => {
                    if (c.dataset.mode === "COMPLETELY_OPEN") {
                        c.classList.add("active");
                        currentMode = "COMPLETELY_OPEN";
                    }
                });
                statusDiv.innerHTML += ` <span style="color:var(--accent-emerald)">→ Switched to Frontier Cloud mode.</span>`;
            } else if (groqKey && !geminiKey) {
                // Only Groq → Hybrid Local
                const chips = document.querySelectorAll(".mode-chip");
                chips.forEach(c => c.classList.remove("active"));
                chips.forEach(c => {
                    if (c.dataset.mode === "PARTIALLY_ISOLATED") {
                        c.classList.add("active");
                        currentMode = "PARTIALLY_ISOLATED";
                    }
                });
                statusDiv.innerHTML += ` <span style="color:var(--accent-cyan)">→ Switched to Hybrid Local mode.</span>`;
            }

            setTimeout(() => {
                document.getElementById("settingsModal").classList.remove("active");
            }, 1800);
        } else {
            statusDiv.innerHTML = `<span style="color: var(--accent-rose)">Failed to save settings.</span>`;
        }
    } catch (e) {
        statusDiv.innerHTML = `<span style="color: var(--accent-rose)">Network error saving settings.</span>`;
    }
}
