// ⚡ VISION OS - DASHBOARD LOGIC AND THREE.JS RENDERER

const HOST = "127.0.0.1";
const API_PORT = 8000;
const WS_URL = `ws://${HOST}:${API_PORT}/ws`;

let socket = null;
let scene, camera, renderer, orbitControls;
let memoryCubes = [];
let memoryNodesGroup = null;
let memoryNodeMeshes = {};

let spinnerInterval = null;
let spinnerElement = null;

// ---------------------------------------------------------------------------
// Module State — accumulators for each cognitive module panel
// ---------------------------------------------------------------------------
const moduleState = {
    services: {},            // latest from /api/health → { name: { status, pid, uptime_s } }
    emotion: null,           // { estado, intensidad }
    memory_tier: {},         // { hot_usage_pct, hot_usage_gb }
    amigdala: {
        blockedCount: 0,
        lastAlert: null,
        alerts: []           // ring buffer, last 10
    },
    vision: {
        lastCaptureTime: null,
        cambioDetectado: null,
        statusText: "Esperando..."
    },
    oido: {
        lastTranscript: null,
        lastTranscriptTime: null,
        isListening: false
    },
    intriga: {
        active: 0,
        completed: 0,
        lastFinding: null
    },
    ejecutor: {
        totalActions: 0,
        lastActions: []       // ring buffer, last 5
    },
    imaginacion: {
        lastPrompt: null,
        lastImageTime: null
    }
};

// ---------------------------------------------------------------------------
// Initialize dashboard on DOM load
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    initThreeJS();
    connectWebSocket();
    setupEventListeners();
    setupDragAndDrop();
    setupSPARouter();
    setupHardwareToggles();
    setupCredentialSaving();

    // Periodic memory node graph update
    updateMemoryNodes();
    setInterval(updateMemoryNodes, 5000);

    // Periodic health polling
    updateHealthDashboard();
    setInterval(updateHealthDashboard, 3000);

    // Activate default SPA view from URL hash or default
    const hash = window.location.hash.replace("#", "");
    activateView(hash || "sistema");
});

// ===========================================================================
// 1. ForceGraph3D: 3D Force-Directed Memory Matrix Preview
// ===========================================================================
let graphInstance = null;

function initThreeJS() {
    const container = document.getElementById("canvas-container");
    if (!container) return;

    graphInstance = ForceGraph3D()(container)
        .backgroundColor('rgba(0, 0, 0, 0)')
        .showNavInfo(false)
        .width(container.clientWidth || 300)
        .height(container.clientHeight || 500)
        .nodeColor(node => {
            const txt = (node.texto || "").toLowerCase();
            if (txt.includes("anomalia") || txt.includes("error") || txt.includes("panic")) return "#ff00ff";
            if (txt.includes("opera") || txt.includes("navegador") || txt.includes("web")) return "#00f3ff";
            if (txt.includes("modelo") || txt.includes("api") || txt.includes("config")) return "#ffcc00";
            if (txt.includes("intrig") || txt.includes("aprend")) return "#39ff14";
            return "#ff9900";
        })
        .nodeVal(4.5)
        .nodeLabel(node => `<div class="scene-tooltip"><strong>Memoria</strong><br>${node.texto}</div>`)
        .linkColor(link => {
            const dist = link.distance;
            if (dist < 0.8) return '#39ff14';
            if (dist < 1.3) return '#ffcc00';
            return '#ff3333';
        })
        .linkWidth(1.5)
        .onNodeClick(node => {
            addTerminalLog(`🧠 Leyendo nodo de memoria: "${node.texto}"`, "system-msg");
        });

    graphInstance.d3Force('charge').strength(-80);
    graphInstance.d3Force('link').distance(40);

    // Setup ResizeObserver to handle precise client size updates
    const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            const width = Math.floor(entry.contentRect.width || container.clientWidth);
            const height = Math.floor(entry.contentRect.height || container.clientHeight);
            if (graphInstance && width > 0 && height > 0) {
                graphInstance.width(width);
                graphInstance.height(height);
            }
        }
    });
    resizeObserver.observe(container);

    // Initial deferred trigger to guarantee layout calculation
    setTimeout(() => {
        if (graphInstance && container.clientWidth > 0) {
            graphInstance.width(container.clientWidth);
            graphInstance.height(container.clientHeight);
        }
    }, 150);
}

// ===========================================================================
// 2. WebSocket: Bidirectional Event Relay
// ===========================================================================
function connectWebSocket() {
    addTerminalLog("Estableciendo conexión WebSocket...", "system-msg");
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        addTerminalLog("Conexión WebSocket establecida con éxito.", "resp-success");
        flashMemoryCubes(0x39ff14);
    };

    socket.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            handleBrokerEvent(payload);
        } catch (e) {
            console.error("Failed to parse websocket event: ", e);
        }
    };

    socket.onclose = () => {
        addTerminalLog("Conexión cerrada por el servidor. Reintentando en 3 segundos...", "resp-error");
        setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket error: ", err);
    };
}

// ===========================================================================
// 3. Health Dashboard — Poll /api/health every 3s
// ===========================================================================
const SERVICE_NAMES = {
    broker: "BROKER", amigdala: "AMÍGDALA", router: "ROUTER",
    lancedb: "DB", hipocampo: "HIPOCAMPO", vision: "VISIÓN",
    contexto: "CONTEXTO", oido: "OÍDO", ejecutor: "EJECUTOR",
    imaginacion: "IMAGINACIÓN", periferico: "PERIFÉRICO", intriga: "INTRIGA"
};
const SERVICE_ORDER = [
    "broker", "amigdala", "router", "lancedb", "hipocampo",
    "vision", "contexto", "oido", "ejecutor", "imaginacion",
    "periferico", "intriga"
];

function updateHealthDashboard() {
    fetch(`http://${HOST}:${API_PORT}/api/health`)
        .then(r => r.json())
        .then(data => {
            moduleState.services = data.services || {};
            moduleState.emotion = data.emotion || null;
            moduleState.memory_tier = data.memory_tier || {};

            renderServiceGrid(data.services);
            renderEmotionDisplay(data.emotion);
            renderMemoryUsage(data.memory_tier);

            // Timestamp
            const ts = document.getElementById("health-timestamp");
            if (ts) {
                const now = new Date();
                ts.textContent = now.toLocaleTimeString();
            }
        })
        .catch(err => {
            // Silently fail — services may not be up yet
            console.debug("Health poll failed (expected during startup):", err);
        });
}

function renderServiceGrid(services) {
    const grid = document.getElementById("service-grid");
    if (!grid) return;

    const entries = SERVICE_ORDER.map(name => {
        const svc = services[name] || { status: "stopped" };
        return { name, ...svc };
    });

    const running = entries.filter(e => e.status === "running").length;
    const total = entries.length;

    // Update count badge
    const countEl = document.getElementById("service-count");
    if (countEl) countEl.textContent = `${running}/${total}`;

    grid.innerHTML = entries.map(e => {
        const displayName = SERVICE_NAMES[e.name] || e.name.toUpperCase();
        let ledClass = "led-stopped";
        let ledChar = "●";
        if (e.status === "running") { ledClass = "led-running"; ledChar = "●"; }
        else if (e.status === "restarting") { ledClass = "led-restarting"; ledChar = "◐"; }

        return `
            <div class="service-card" title="${e.name}: ${e.status}${e.uptime_s ? ` (uptime: ${formatUptime(e.uptime_s)})` : ""}">
                <span class="service-led ${ledClass}">${ledChar}</span>
                <span class="service-name">${displayName}</span>
            </div>
        `;
    }).join("");
}

function renderEmotionDisplay(emotion) {
    if (!emotion) return;

    const estado = (emotion.estado || "neutral").toLowerCase();
    const intensidad = emotion.intensidad || 0;

    // Emotion value in module panel
    const valueEl = document.getElementById("emotion-value");
    if (valueEl) {
        valueEl.textContent = estado.toUpperCase();
        valueEl.className = getEmotionClass(estado);
    }

    // Intensity bar
    const barEl = document.getElementById("intensity-bar");
    if (barEl) barEl.style.width = `${Math.min(intensidad * 100, 100)}%`;

    const intValEl = document.getElementById("intensity-value");
    if (intValEl) intValEl.textContent = intensidad.toFixed(2);

    // Header emotion badge
    const headerText = document.getElementById("header-emotion-text");
    if (headerText) {
        headerText.textContent = estado.toUpperCase();
        headerText.className = getEmotionClass(estado);
    }

    const headerIcon = document.getElementById("header-emotion-icon");
    if (headerIcon) {
        const icons = { neutral: "🧠", positivo: "😊", feliz: "😊", contento: "😊", negativo: "😟", triste: "😢", enojado: "😠", alerta: "⚠️", anomalia: "🚨" };
        headerIcon.textContent = icons[estado] || "🧠";
    }

    const headerInt = document.getElementById("header-emotion-intensity");
    if (headerInt) headerInt.textContent = intensidad.toFixed(2);
}

function renderMemoryUsage(mt) {
    if (!mt) return;
    const pct = mt.hot_usage_pct || 0;
    const el = document.getElementById("memory-hot-pct");
    if (el) el.textContent = `${(pct * 100).toFixed(1)}%`;
}

function getEmotionClass(estado) {
    if (["positivo", "feliz", "contento"].includes(estado)) return "emotion-positivo";
    if (["negativo", "triste", "enojado"].includes(estado)) return "emotion-negativo";
    if (["alerta", "anomalia", "panic"].includes(estado)) return "emotion-alerta";
    return "emotion-neutral";
}

// ===========================================================================
// 4. Handle Events coming from Broker — Update module-specific panels
// ===========================================================================
function handleBrokerEvent(event) {
    const topic = event.topic;
    const data = event.data || {};

    if (topic === "canal.cognitivo.entrada" || topic === "canal.cognitivo.peticion") {
        startThinkingSpinner();
    } else if (topic === "canal.cognitivo.respuesta") {
        const isSuccess = data.status === "success";
        const modelUsed = data.model_used || "modelo local";
        stopThinkingSpinner(isSuccess, modelUsed);

        if (isSuccess) {
            addTerminalLog(`🤖 [LobeFrontal] (${modelUsed}): ${data.response}`, "resp-success");
        } else {
            addTerminalLog(`❌ [LobeFrontal Error]: ${data.error}`, "resp-error");
        }

    } else if (topic === "canal.sistema.contexto_actual") {
        const contexto = data.contexto || "";
        const cleanContext = contexto.trim();
        const hasAnomaly = cleanContext.startsWith("ANOMALIA_DETECTADA:") || 
                            cleanContext.startsWith("**ANOMALIA_DETECTADA:**") ||
                            cleanContext.startsWith("### ANOMALIA_DETECTADA:") ||
                            cleanContext.startsWith("### **ANOMALIA_DETECTADA:**");
        if (hasAnomaly) {
            addTerminalLog(`🚨 [ANOMALÍA] ${contexto}`, "resp-anomalia");
            pulseMemoryCubes(0xff9900);
            // Update amigdala panel
            updateAmigdalaPanel(contexto);
        } else {
            addTerminalLog(`👁️ [Contexto] ${contexto}`, "system-msg");
        }

    } else if (topic === "canal.sensorial.audio.transcripcion") {
        const text = data.transcripcion || "";
        addTerminalLog(`🎙️ [Voz Transcrita] "${text}"`, "user-cmd");

        setMicStatus("⚙️ TRANSCRIBIENDO WHISPER", "status-transcribiendo");
        setTimeout(() => {
            setMicStatus("[ 💤 SILENCIO ]", "status-silencio");
        }, 2000);

        // Update oido panel
        updateOidoPanel(text);

    } else if (topic === "canal.sensorial.vision") {
        const captureTime = data.timestamp || Date.now();
        const cambio = data.cambio_detectado ? "SÍ" : "no";
        addTerminalLog(`👁️ [Visión] Captura recibida. Cambio: ${cambio}`, "system-msg");
        updateVisionPanel(captureTime, cambio);

    } else if (topic === "canal.imaginacion.respuesta") {
        const imagePath = data.image_path || "";
        addTerminalLog(`🎨 [Occipital] Imagen generada en: ${imagePath}`, "resp-success");

        const filename = imagePath.split(/[\\/]/).pop();
        if (filename) {
            showOccipitalImage(`http://${HOST}:${API_PORT}/artifacts/${filename}`, data.prompt || "Visualización generada.");
        }

        // Update imaginacion panel
        updateImaginacionPanel(data.prompt, data.timestamp);

    } else if (topic === "canal.sistema.anuncios") {
        const msg = data.mensaje || "";
        const errorText = data.error_original;

        addTerminalLog(`📢 [Anuncio] ${msg}`, "resp-anomalia");

        if (msg.includes("¿Me das permiso para crear un ticket de situación")) {
            createHITLTicket(
                "TICKET_INTRIGA",
                `Investigar solución técnica para: <strong>${escapeHtml(errorText || "Error detectado en pantalla")}</strong>`,
                () => {
                    sendWebSocketMessage("canal.sensorial.audio.transcripcion", {
                        "transcripcion": "si, procede a investigar por favor"
                    });
                },
                () => {
                    sendWebSocketMessage("canal.sensorial.audio.transcripcion", {
                        "transcripcion": "no, abortar investigacion"
                    });
                }
            );
        }

        // Update intriga panel
        if (msg.includes("investigar") || msg.includes("intriga")) {
            updateIntrigaPanel(msg);
        }

    } else if (topic === "canal.ejecucion.accion") {
        const tool = data.herramienta;
        const params = data.parametros || [];
        const reqId = data.request_id;

        addTerminalLog(`⚙️ [Ejecución] Solicitud para herramienta '${tool}'`, "system-msg");

        // Update ejecutor panel
        updateEjecutorPanel(tool, params, reqId, "pending");

        // The executor runs nothing until it receives this decision on canal.ejecucion.aprobacion.
        const label = tool === "ejecutar_script" ? "Ejecución de comando de sistema"
            : tool === "control_ui" ? "Ejecución de Automatización de Teclado/Mouse"
            : `Herramienta '${tool}'`;
        createHITLTicket(
            reqId,
            `${escapeHtml(label)}: <strong>${escapeHtml(JSON.stringify(params))}</strong>`,
            () => {
                sendWebSocketMessage("canal.ejecucion.aprobacion", { "request_id": reqId, "approved": true });
                updateEjecutorPanel(tool, params, reqId, "approved");
            },
            () => {
                sendWebSocketMessage("canal.ejecucion.aprobacion", { "request_id": reqId, "approved": false });
                updateEjecutorPanel(tool, params, reqId, "rejected");
            }
        );

    } else if (topic === "canal.ejecucion.resultado") {
        const res = data.resultado || {};
        const detail = res.detail ? ` — ${res.detail}` : "";
        addTerminalLog(
            `⚙️ [Ejecución] ${data.request_id}: ${res.status}${detail}`,
            res.status === "success" ? "resp-success" : "resp-error"
        );
    }
}

// ---------------------------------------------------------------------------
// Module Panel Update Helpers
// ---------------------------------------------------------------------------

function updateAmigdalaPanel(contexto) {
    moduleState.amigdala.blockedCount++;
    moduleState.amigdala.lastAlert = contexto;

    // Ring buffer: last 10 alerts
    moduleState.amigdala.alerts.unshift(contexto);
    if (moduleState.amigdala.alerts.length > 10) moduleState.amigdala.alerts.pop();

    const countEl = document.getElementById("amigdala-count");
    if (countEl) countEl.textContent = moduleState.amigdala.blockedCount;

    const blockedEl = document.getElementById("amigdala-blocked");
    if (blockedEl) blockedEl.textContent = moduleState.amigdala.blockedCount;

    const lastEl = document.getElementById("amigdala-last-alert");
    if (lastEl) {
        lastEl.innerHTML = moduleState.amigdala.alerts.slice(0, 3).map(a =>
            `<div class="alert-item">${escapeHtml(a)}</div>`
        ).join("");
    }
}

function updateVisionPanel(timestamp, cambio) {
    const ts = timestamp ? new Date(timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
    moduleState.vision.lastCaptureTime = ts;
    moduleState.vision.cambioDetectado = cambio;
    moduleState.vision.statusText = "🟢 Activo";

    const statusEl = document.getElementById("vision-status");
    if (statusEl) statusEl.textContent = moduleState.vision.statusText;

    const tsEl = document.getElementById("vision-timestamp");
    if (tsEl) tsEl.textContent = ts;

    const cambioEl = document.getElementById("vision-cambio");
    if (cambioEl) {
        cambioEl.textContent = cambio;
        cambioEl.style.color = cambio === "SÍ" ? "#ff9900" : "#8fa0b5";
    }
}

function updateOidoPanel(transcript) {
    moduleState.oido.lastTranscript = transcript;
    moduleState.oido.lastTranscriptTime = new Date().toLocaleTimeString();
    moduleState.oido.isListening = true;

    const statusEl = document.getElementById("oido-status");
    if (statusEl) statusEl.textContent = "🎙️ TRANSCRIBIENDO";

    const micEl = document.getElementById("oido-mic");
    if (micEl) micEl.textContent = "🟢 Activo";

    const transcriptEl = document.getElementById("oido-transcript");
    if (transcriptEl) transcriptEl.textContent = `"${transcript}"`;
}

function updateIntrigaPanel(msg) {
    moduleState.intriga.active++;
    moduleState.intriga.lastFinding = msg;

    const activeEl = document.getElementById("intriga-activas");
    if (activeEl) activeEl.textContent = moduleState.intriga.active;

    const completedEl = document.getElementById("intriga-completadas");
    if (completedEl) completedEl.textContent = moduleState.intriga.completed;

    const lastEl = document.getElementById("intriga-ultimo");
    if (lastEl) lastEl.textContent = msg.substring(0, 60) + (msg.length > 60 ? "..." : "");

    const countEl = document.getElementById("intriga-count");
    if (countEl) countEl.textContent = moduleState.intriga.active;
}

function updateEjecutorPanel(tool, params, reqId, status) {
    moduleState.ejecutor.totalActions++;

    const actionStr = `${tool}(${JSON.stringify(params).substring(0, 40)})`;
    const statusIcon = status === "approved" ? "✅" : status === "rejected" ? "❌" : "⏳";
    const actionClass = status === "approved" ? "action-approved" : status === "rejected" ? "action-rejected" : "";

    moduleState.ejecutor.lastActions.unshift({
        text: actionStr,
        status: status,
        id: reqId,
        time: new Date().toLocaleTimeString()
    });
    if (moduleState.ejecutor.lastActions.length > 5) moduleState.ejecutor.lastActions.pop();

    const totalEl = document.getElementById("ejecutor-total");
    if (totalEl) totalEl.textContent = moduleState.ejecutor.totalActions;

    const listEl = document.getElementById("ejecutor-last-actions");
    if (listEl) {
        listEl.innerHTML = moduleState.ejecutor.lastActions.map(a =>
            `<div class="action-item ${a.status === "approved" ? "action-approved" : a.status === "rejected" ? "action-rejected" : ""}">
                <span class="action-status-icon">${a.status === "approved" ? "✅" : a.status === "rejected" ? "❌" : "⏳"}</span>
                <span>${escapeHtml(a.text)}</span>
                <span style="color:#5d6f83; margin-left: auto; font-size: 7px;">${a.time}</span>
            </div>`
        ).join("");
    }

    const countEl = document.getElementById("ejecutor-count");
    if (countEl) countEl.textContent = moduleState.ejecutor.totalActions;
}

function updateImaginacionPanel(prompt, timestamp) {
    moduleState.imaginacion.lastPrompt = prompt;
    moduleState.imaginacion.lastImageTime = timestamp ? new Date(timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();

    const promptEl = document.getElementById("imaginacion-prompt");
    if (promptEl) promptEl.textContent = prompt || "—";

    const tsEl = document.getElementById("imaginacion-timestamp");
    if (tsEl) tsEl.textContent = moduleState.imaginacion.lastImageTime;
}

// ===========================================================================
// 5. Collapsible Module Sections
// ===========================================================================
function toggleModuleSection(headerEl) {
    const content = headerEl.nextElementSibling;
    const toggle = headerEl.querySelector(".module-toggle");
    if (!content || !toggle) return;

    const isCollapsed = content.classList.toggle("collapsed");
    toggle.classList.toggle("collapsed", isCollapsed);
}

// ===========================================================================
// 6. Interactive HUD Actions & Settings
// ===========================================================================
function setupEventListeners() {
    // Panic Button Trigger
    const btnPanic = document.getElementById("btn-panic");
    if (btnPanic) {
        btnPanic.addEventListener("click", () => {
            addTerminalLog("🛑 BOTÓN DE PÁNICO PULSADO: Purgando colas y reseteando broker...", "resp-error");
            pulseMemoryCubes(0xe61f2b);
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ "action": "panic" }));
            }
        });
    }

    // Console Command Input Line
    const consoleInput = document.getElementById("console-input");
    if (consoleInput) {
        consoleInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const text = consoleInput.value.trim();
                if (!text) return;

                addTerminalLog(`> ${text}`, "user-cmd");
                consoleInput.value = "";

                sendWebSocketMessage("canal.cognitivo.entrada", {
                    "request_id": `manual-${Date.now()}`,
                    "prompt": text,
                    "esfuerzo_requerido": "esfuerzo_bajo",
                    "mock": false
                });
            }
        });
    }

    // Occipital Modal Close
    const closeModal = document.getElementById("close-modal");
    const imageModal = document.getElementById("image-modal");
    if (closeModal && imageModal) {
        closeModal.addEventListener("click", () => {
            imageModal.classList.add("hidden");
        });
    }

    // ---- Config Panel Modal Controls (LLM Router Configurator) ----
    const btnSettings = document.getElementById("btn-settings");
    const settingsModal = document.getElementById("settings-modal");
    const closeSettings = document.getElementById("close-settings");
    const settingsForm = document.getElementById("settings-form");
    const configProvider = document.getElementById("config-provider");
    const configModelSelect = document.getElementById("config-model-select");
    const configModelCustom = document.getElementById("config-model-custom");
    const configApiBase = document.getElementById("config-api-base");
    const configApiKey = document.getElementById("config-api-key");

    const PROVIDERS_TEMPLATES = {
        ollama: {
            name: "Ollama (Local / Offline)",
            api_base: "http://localhost:11434",
            placeholder_key: "No requiere API Key",
            models: ["llama3.2:latest","qwen2.5-coder:14b","deepseek-r1:14b","llama3.1:latest","gemma4:latest","minicpm-v:latest"]
        },
        openrouter: {
            name: "OpenRouter (Cloud / Todos los modelos)",
            api_base: "https://openrouter.ai/api/v1",
            placeholder_key: "sk-or-v1-...",
            models: ["google/gemini-2.5-flash:free","google/gemini-2.5-pro","meta-llama/llama-3.3-70b-instruct:free","deepseek/deepseek-r1","anthropic/claude-3.5-sonnet","qwen/qwen-2.5-coder-32b-instruct"]
        },
        openai: {
            name: "OpenAI (Oficial)",
            api_base: "https://api.openai.com/v1",
            placeholder_key: "sk-proj-...",
            models: ["gpt-4o-mini","gpt-4o","o1-mini","o3-mini"]
        },
        anthropic: {
            name: "Anthropic (Claude)",
            api_base: "https://api.anthropic.com/v1",
            placeholder_key: "sk-ant-...",
            models: ["claude-3-5-sonnet-20241022","claude-3-5-haiku-20241022","claude-3-opus-20240229"]
        },
        gemini: {
            name: "Google Gemini Developer API",
            api_base: "https://generativelanguage.googleapis.com/v1beta",
            placeholder_key: "AIzaSy...",
            models: ["gemini-1.5-flash","gemini-1.5-pro","gemini-2.0-flash-exp"]
        },
        groq: {
            name: "Groq (Inferencia Ultrarrápida)",
            api_base: "https://api.groq.com/openai/v1",
            placeholder_key: "gsk_...",
            models: ["llama-3.3-70b-versatile","mixtral-8x7b-32768","gemma2-9b-it"]
        },
        lmstudio: {
            name: "LM Studio (Local / Puerto Custom)",
            api_base: "http://localhost:1234/v1",
            placeholder_key: "No requiere API Key (lm-studio)",
            models: ["local-model"]
        },
        custom: {
            name: "Otro Proveedor (Personalizado)",
            api_base: "",
            placeholder_key: "API Key / Env Variable (opcional)",
            models: []
        }
    };

    function populateModelSelect(providerKey) {
        if (!configModelSelect) return;
        configModelSelect.innerHTML = "";
        const providerData = PROVIDERS_TEMPLATES[providerKey] || { models: [] };
        providerData.models.forEach(model => {
            const opt = document.createElement("option");
            opt.value = model;
            opt.textContent = model;
            configModelSelect.appendChild(opt);
        });
        const customOpt = document.createElement("option");
        customOpt.value = "custom_write";
        customOpt.textContent = "✏️ Escribir modelo personalizado...";
        configModelSelect.appendChild(customOpt);
        configModelSelect.dispatchEvent(new Event("change"));
    }

    async function refreshActiveRoutingVisualizer() {
        try {
            const resp = await fetch(`http://${HOST}:${API_PORT}/api/config`);
            const cfg = await resp.json();
            const strategy = document.getElementById("config-routing-strategy").value;
            const strategies = cfg.strategies || {};
            const models = strategies[strategy] || {};

            document.getElementById("active-model-bajo").textContent = models.esfuerzo_bajo?.model || "No configurado";
            document.getElementById("active-model-medio").textContent = models.esfuerzo_medio?.model || "No configurado";
            document.getElementById("active-model-alto").textContent = models.esfuerzo_alto?.model || "No configurado";

            const strategyNames = {
                locales: "💻 LOCALES (Ollama)",
                hibrido_api: "⚡ HÍBRIDO (Llamada API)",
                suscripcion_mensual: "💎 MENSUAL (Suscripción)"
            };
            const labelEl = document.getElementById("editing-strategy-name");
            if (labelEl) labelEl.textContent = (strategyNames[strategy] || strategy).toUpperCase();
        } catch (err) {
            console.error("Error reading active router config: ", err);
        }
    }

    if (btnSettings && settingsModal) {
        btnSettings.addEventListener("click", async () => {
            if (settingsForm) settingsForm.reset();
            if (configProvider) configProvider.value = "ollama";
            if (configApiBase) configApiBase.value = PROVIDERS_TEMPLATES.ollama.api_base;
            if (configApiKey) configApiKey.placeholder = PROVIDERS_TEMPLATES.ollama.placeholder_key;

            populateModelSelect("ollama");

            try {
                const resp = await fetch(`http://${HOST}:${API_PORT}/api/config`);
                const cfg = await resp.json();
                const activeStrategy = cfg.routing_strategy || "locales";
                document.getElementById("config-routing-strategy").value = activeStrategy;
            } catch (err) {
                console.error("Error loading active strategy: ", err);
            }

            // Load Oído, Habla, and Cámara configurations
            try {
                // 1. Fetch microphones
                const micResp = await fetch(`http://${HOST}:${API_PORT}/api/config/microfonos`);
                const micData = await micResp.json();
                const micSelect = document.getElementById("config-oido-device");
                if (micSelect) {
                    micSelect.innerHTML = '<option value="default">Default (Predeterminado)</option>';
                    if (micData.status === "success" && micData.devices) {
                        micData.devices.forEach(dev => {
                            const opt = document.createElement("option");
                            opt.value = dev.index;
                            opt.textContent = `[ID ${dev.index}] ${dev.name}`;
                            micSelect.appendChild(opt);
                        });
                    }
                }

                // 2. Fetch altavoces (speakers)
                const spkResp = await fetch(`http://${HOST}:${API_PORT}/api/config/altavoces`);
                const spkData = await spkResp.json();
                const spkSelect = document.getElementById("config-habla-device");
                if (spkSelect) {
                    spkSelect.innerHTML = '<option value="default">Default (Predeterminado)</option>';
                    if (spkData.status === "success" && spkData.devices) {
                        spkData.devices.forEach(dev => {
                            const opt = document.createElement("option");
                            opt.value = dev.index;
                            opt.textContent = `[ID ${dev.index}] ${dev.name}`;
                            spkSelect.appendChild(opt);
                        });
                    }
                }

                // 3. Fetch cameras
                const camResp = await fetch(`http://${HOST}:${API_PORT}/api/config/camaras`);
                const camData = await camResp.json();
                const camSelect = document.getElementById("config-vision-camara-device");
                if (camSelect) {
                    camSelect.innerHTML = "";
                    if (camData.status === "success" && camData.devices && camData.devices.length > 0) {
                        camData.devices.forEach(dev => {
                            const opt = document.createElement("option");
                            opt.value = dev.id;
                            opt.textContent = `[ID ${dev.id}] ${dev.nombre}`;
                            camSelect.appendChild(opt);
                        });
                    } else {
                        const opt = document.createElement("option");
                        opt.value = "0";
                        opt.textContent = "Cámara Index 0 (Default)";
                        camSelect.appendChild(opt);
                    }
                }

                // 4. Fetch current hardware config
                const hwResp = await fetch(`http://${HOST}:${API_PORT}/api/config/hardware`);
                const hwData = await hwResp.json();
                if (hwData.status === "success" && hwData.config) {
                    const oidoCfg = hwData.config.oido_activo || {};
                    const hablaCfg = hwData.config.habla_activa || {};
                    const visionCfg = hwData.config.vision_activa || {};

                    document.getElementById("config-oido-threshold").value = oidoCfg.energy_threshold !== undefined ? oidoCfg.energy_threshold : 300;
                    document.getElementById("config-oido-whisper").value = oidoCfg.whisper_model || "tiny";
                    if (micSelect && oidoCfg.input_device_index !== undefined && oidoCfg.input_device_index !== null) {
                        micSelect.value = oidoCfg.input_device_index;
                    }

                    document.getElementById("config-habla-tts").value = hablaCfg.tts_engine || "edge-tts";
                    if (spkSelect && hablaCfg.output_device_index !== undefined && hablaCfg.output_device_index !== null) {
                        spkSelect.value = hablaCfg.output_device_index;
                    }

                    document.getElementById("config-vision-camara-activa").value = visionCfg.camara_activa ? "true" : "false";
                    if (camSelect && visionCfg.camara_index !== undefined && visionCfg.camara_index !== null) {
                        camSelect.value = visionCfg.camara_index;
                    }
                    document.getElementById("config-vision-camera-ip").value = visionCfg.camera_ip || "";
                }

                // 5. Fetch startup config
                const arrResp = await fetch(`http://${HOST}:${API_PORT}/api/config/arranque`);
                const arrData = await arrResp.json();
                if (arrData.status === "success" && arrData.config && arrData.config.modos_mock) {
                    const mockOido = arrData.config.modos_mock.oido_parietal;
                    const mockHabla = arrData.config.modos_mock.habla_parietal;
                    document.getElementById("config-oido-mock").value = mockOido ? "true" : "false";
                    document.getElementById("config-habla-mock").value = mockHabla ? "true" : "false";
                }
            } catch (err) {
                console.error("Error loading hardware/audio config in UI: ", err);
            }

            await refreshActiveRoutingVisualizer();
            settingsModal.classList.remove("hidden");
        });
    }

    if (closeSettings && settingsModal) {
        closeSettings.addEventListener("click", () => settingsModal.classList.add("hidden"));
    }

    const routingStrategySelect = document.getElementById("config-routing-strategy");
    if (routingStrategySelect) {
        routingStrategySelect.addEventListener("change", async (e) => {
            const newStrategy = e.target.value;
            try {
                const getResp = await fetch(`http://${HOST}:${API_PORT}/api/config`);
                const currentCfg = await getResp.json();
                currentCfg.routing_strategy = newStrategy;

                const postResp = await fetch(`http://${HOST}:${API_PORT}/api/config`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(currentCfg)
                });
                const res = await postResp.json();
                if (res.status === "success") {
                    addTerminalLog(`🔄 Lóbulo Frontal: Estrategia de ruteo cambiada a "${newStrategy}".`, "system-msg");
                    refreshActiveRoutingVisualizer();
                    flashMemoryCubes(0x00f3ff);
                }
            } catch (err) {
                console.error("Failed to update active strategy: ", err);
            }
        });
    }

    if (configProvider) {
        configProvider.addEventListener("change", (e) => {
            const provKey = e.target.value;
            const template = PROVIDERS_TEMPLATES[provKey];
            if (template) {
                configApiBase.value = template.api_base;
                configApiKey.placeholder = template.placeholder_key;
                populateModelSelect(provKey);
            }
        });
    }

    if (configModelSelect && configModelCustom) {
        configModelSelect.addEventListener("change", (e) => {
            if (e.target.value === "custom_write") {
                configModelCustom.classList.remove("hidden");
                configModelCustom.required = true;
            } else {
                configModelCustom.classList.add("hidden");
                configModelCustom.required = false;
            }
        });
    }

    if (settingsForm) {
        settingsForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const effortLevel = document.getElementById("config-effort-level").value;
            const strategy = document.getElementById("config-routing-strategy").value;
            const provider = document.getElementById("config-provider").value;
            const selectedVal = configModelSelect.value;
            let modelName = (selectedVal === "custom_write")
                ? configModelCustom.value.trim()
                : selectedVal;

            const apiBase = configApiBase.value.trim();
            const apiKey = configApiKey.value.trim();

            if (!modelName) {
                addTerminalLog("⚠️ Nombre de modelo inválido.", "resp-error");
                return;
            }

            let fullModelPath = modelName;
            if (provider === "ollama" && !modelName.startsWith("ollama/")) fullModelPath = `ollama/${modelName}`;
            else if (provider === "openrouter" && !modelName.startsWith("openrouter/")) fullModelPath = `openrouter/${modelName}`;
            else if (provider === "openai" && !modelName.startsWith("openai/")) fullModelPath = `openai/${modelName}`;
            else if (provider === "anthropic" && !modelName.startsWith("anthropic/")) fullModelPath = `anthropic/${modelName}`;
            else if (provider === "gemini" && !modelName.startsWith("gemini/")) fullModelPath = `gemini/${modelName}`;
            else if (provider === "groq" && !modelName.startsWith("groq/")) fullModelPath = `groq/${modelName}`;
            else if (provider === "lmstudio" && !modelName.startsWith("openai/")) fullModelPath = `openai/${modelName}`;

            // Extract Oído values
            const mockOidoVal = (document.getElementById("config-oido-mock").value === "true");
            const micVal = document.getElementById("config-oido-device").value;
            const inputDeviceIndex = micVal === "default" ? null : parseInt(micVal);
            const energyThreshold = parseInt(document.getElementById("config-oido-threshold").value) || 300;
            const whisperModel = document.getElementById("config-oido-whisper").value;

            // Extract Habla values
            const mockHablaVal = (document.getElementById("config-habla-mock").value === "true");
            const spkVal = document.getElementById("config-habla-device").value;
            const outputDeviceIndex = spkVal === "default" ? null : parseInt(spkVal);
            const ttsEngine = document.getElementById("config-habla-tts").value;

            // Extract Visión values
            const camaraActiva = (document.getElementById("config-vision-camara-activa").value === "true");
            const camaraIndex = parseInt(document.getElementById("config-vision-camara-device").value) || 0;
            const cameraIp = document.getElementById("config-vision-camera-ip").value.trim();

            try {
                // 1. Save LLM Router config
                const getResp = await fetch(`http://${HOST}:${API_PORT}/api/config`);
                const currentCfg = await getResp.json();

                if (!currentCfg.strategies) currentCfg.strategies = {};
                if (!currentCfg.strategies[strategy]) currentCfg.strategies[strategy] = {};
                if (!currentCfg.strategies[strategy][effortLevel]) currentCfg.strategies[strategy][effortLevel] = {};

                currentCfg.strategies[strategy][effortLevel].model = fullModelPath;
                if (apiBase) currentCfg.strategies[strategy][effortLevel].api_base = apiBase;
                else delete currentCfg.strategies[strategy][effortLevel].api_base;
                if (apiKey) currentCfg.strategies[strategy][effortLevel].api_key = apiKey;
                else delete currentCfg.strategies[strategy][effortLevel].api_key;

                await fetch(`http://${HOST}:${API_PORT}/api/config`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(currentCfg)
                });

                // 2. Save Hardware config
                const hwGet = await fetch(`http://${HOST}:${API_PORT}/api/config/hardware`);
                const hwGetJson = await hwGet.json();
                const currentHw = hwGetJson.config || {};
                
                if (!currentHw.vision_activa) currentHw.vision_activa = {};
                currentHw.vision_activa.camara_activa = camaraActiva;
                currentHw.vision_activa.camara_index = camaraIndex;
                currentHw.vision_activa.camera_ip = cameraIp;

                if (!currentHw.oido_activo) currentHw.oido_activo = {};
                currentHw.oido_activo.input_device_index = inputDeviceIndex;
                currentHw.oido_activo.energy_threshold = energyThreshold;
                currentHw.oido_activo.dynamic_energy_threshold = true;
                currentHw.oido_activo.whisper_model = whisperModel;

                if (!currentHw.habla_activa) currentHw.habla_activa = {};
                currentHw.habla_activa.output_device_index = outputDeviceIndex;
                currentHw.habla_activa.tts_engine = ttsEngine;

                await fetch(`http://${HOST}:${API_PORT}/api/config/hardware`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(currentHw)
                });

                // 3. Save Arranque config
                const arrGet = await fetch(`http://${HOST}:${API_PORT}/api/config/arranque`);
                const arrGetJson = await arrGet.json();
                const currentArr = arrGetJson.config || {};
                if (!currentArr.modos_mock) currentArr.modos_mock = {};
                currentArr.modos_mock.oido_parietal = mockOidoVal;
                currentArr.modos_mock.habla_parietal = mockHablaVal;

                await fetch(`http://${HOST}:${API_PORT}/api/config/arranque`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(currentArr)
                });

                addTerminalLog(`✅ Lóbulo Frontal y Hardware: Configuraciones actualizadas correctamente.`, "resp-success");
                settingsModal.classList.add("hidden");
                settingsForm.reset();
                flashMemoryCubes(0x39ff14);
            } catch (err) {
                addTerminalLog(`❌ Fallo de red al guardar la configuración: ${err}`, "resp-error");
            }
        });
    }

    // --- File Search ---
    const fileSearchInput = document.getElementById("file-search-input");
    const fileSearchResults = document.getElementById("file-search-results");

    if (fileSearchInput && fileSearchResults) {
        let debounceTimer;
        fileSearchInput.addEventListener("input", (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();
            if (!query) {
                fileSearchResults.classList.add("hidden");
                fileSearchResults.innerHTML = "";
                return;
            }
            debounceTimer = setTimeout(async () => {
                try {
                    const resp = await fetch(`http://${HOST}:${API_PORT}/api/archivos?q=${encodeURIComponent(query)}`);
                    const files = await resp.json();
                    if (files.length === 0) {
                        fileSearchResults.innerHTML = `<div style="color: #5d6f83; font-style: italic; text-align: center; padding: 4px;">Sin coincidencias</div>`;
                    } else {
                        fileSearchResults.innerHTML = files.map(f => `
                            <div class="search-result-item" style="border-bottom: 1px dashed rgba(0,243,255,0.1); padding: 4px 0; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                                <span style="color: #39ff14; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 160px;" title="${f.nombre}">${f.nombre}</span>
                                <span style="color: #8fa0b5; font-size: 9px; flex-shrink: 0;">${formatBytes(f.tamaño_bytes)}</span>
                            </div>
                        `).join("");
                    }
                    fileSearchResults.classList.remove("hidden");
                } catch (err) {
                    console.error("Error searching files: ", err);
                }
            }, 300);
        });
    }
}

// ===========================================================================
// 7. Drag and Drop File Ingestion
// ===========================================================================
function setupDragAndDrop() {
    const dropzone = document.getElementById("dropzone");
    if (!dropzone) return;

    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
        }, false);
    });

    dropzone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) handleFileUpload(files[0]);
    });
}

function handleFileUpload(file) {
    addTerminalLog(`📤 Subiendo archivo: ${file.name}...`, "system-msg");
    const formData = new FormData();
    formData.append("file", file);

    fetch(`http://${HOST}:${API_PORT}/upload_sensorial`, {
        method: "POST",
        body: formData
    })
    .then(resp => resp.json())
    .then(data => {
        if (data.status === "success") {
            addTerminalLog(`✅ Archivo recibido con éxito. Ruta local: ${data.file_path}`, "resp-success");
        } else {
            addTerminalLog(`⚠️ Error al procesar archivo en el servidor: ${data.message}`, "resp-error");
        }
    })
    .catch(err => {
        addTerminalLog(`❌ Fallo de red al subir archivo: ${err}`, "resp-error");
    });
}

// ===========================================================================
// 8. Fetch LanceDB Memory Nodes and Render in 3D
// ===========================================================================
async function updateMemoryNodes() {
    if (!graphInstance) return;

    try {
        const resp = await fetch(`http://${HOST}:${API_PORT}/api/memoria`);
        const nodes = await resp.json();

        if (!nodes || nodes.length === 0) {
            const placeholderNodes = [
                { id: "core-node", texto: "Núcleo de Memoria Activa", x: 0, y: 0, z: 0 },
                { id: "sample-1", texto: "Opera GX es un navegador gamer", x: 1.0, y: 0.5, z: -0.2 },
                { id: "sample-2", texto: "Protocolo de Intriga: anomalía radeon", x: -0.8, y: 1.2, z: 0.6 }
            ];
            const placeholderLinks = [
                { source: "core-node", target: "sample-1" },
                { source: "core-node", target: "sample-2" }
            ];
            graphInstance.graphData({ nodes: placeholderNodes, links: placeholderLinks });
            return;
        }

        const links = [];
        const threshold = 1.6;
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dz = nodes[i].z - nodes[j].z;
                const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
                if (dist < threshold) {
                    links.push({
                        source: nodes[i].id,
                        target: nodes[j].id,
                        distance: dist
                    });
                }
            }
        }

        graphInstance.graphData({ nodes, links });
    } catch (err) {
        console.error("Failed to query memory coordinates: ", err);
    }
}

// ===========================================================================
// 9. Helper UI Actions
// ===========================================================================
let logIdCounter = 0;
const logRegistry = {};

function inspectLog(logId) {
    const inspector = document.getElementById("inspector-logs");
    if (!inspector) return;
    
    const fullText = logRegistry[logId];
    if (!fullText) return;
    
    // Replace markdown double asterisks and single asterisks with HTML
    let formattedText = fullText
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");
        
    // Format newlines
    formattedText = formattedText.replace(/\n/g, "<br>");
    
    inspector.innerHTML = `
        <div style="display: flex; justify-content: space-between; font-size: 8px; color: #5d6f83; border-bottom: 1px dashed rgba(0, 243, 255, 0.2); padding-bottom: 4px; margin-bottom: 8px; font-family: 'Share Tech Mono', monospace;">
            <span>LOG ID: ${logId}</span>
            <span>DETALLE ACTIVO</span>
        </div>
        <div class="inspector-content-text" style="font-family: 'Share Tech Mono', monospace; word-break: break-word; color: #e0e5eb;">${formattedText}</div>
    `;
    inspector.scrollTop = 0;
}

function addTerminalLog(text, className) {
    const logBox = document.getElementById("terminal-logs");
    if (!logBox) return;

    const line = document.createElement("div");
    line.className = `log-line ${className}`;
    
    const id = `log-${++logIdCounter}`;
    logRegistry[id] = text;
    line.dataset.logId = id;

    // Check if the message is too long and needs truncation
    const maxLen = 160;
    if (text.length > maxLen) {
        const truncated = text.substring(0, maxLen - 25) + "...";
        line.textContent = truncated;
        
        const btn = document.createElement("span");
        btn.className = "inspect-btn";
        btn.style.color = "#00f3ff";
        btn.style.cursor = "pointer";
        btn.style.textDecoration = "underline";
        btn.style.fontWeight = "bold";
        btn.style.marginLeft = "6px";
        btn.textContent = "[ver detalles]";
        
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            inspectLog(id);
        });
        
        line.appendChild(btn);
    } else {
        line.textContent = text;
    }

    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;

    // Auto-inspect the latest message
    inspectLog(id);

    while (logBox.children.length > 100) {
        const first = logBox.firstChild;
        if (first && first.dataset && first.dataset.logId) {
            delete logRegistry[first.dataset.logId];
        }
        logBox.removeChild(first);
    }
}

function setMicStatus(text, className) {
    const el = document.getElementById("mic-status");
    if (!el) return;
    el.textContent = text;
    el.className = className;
}

function createHITLTicket(ticketId, messageHtml, approveCallback, rejectCallback) {
    const area = document.getElementById("ticket-area");
    if (!area) return;

    const emptyMsg = area.querySelector(".no-tickets");
    if (emptyMsg) emptyMsg.remove();

    const card = document.createElement("div");
    card.id = `ticket-${ticketId}`;
    card.className = "ticket-card";

    card.innerHTML = `
        <div class="ticket-title">AUTORIZACIÓN PENDIENTE // ID: ${escapeHtml(String(ticketId))}</div>
        <div class="ticket-msg">${messageHtml}</div>
        <div class="ticket-actions">
            <button class="btn-approve">APROBAR</button>
            <button class="btn-reject">RECHAZAR</button>
        </div>
    `;

    card.querySelector(".btn-approve").addEventListener("click", () => {
        approveCallback();
        card.remove();
        checkEmptyTickets();
    });

    card.querySelector(".btn-reject").addEventListener("click", () => {
        rejectCallback();
        card.remove();
        checkEmptyTickets();
    });

    area.appendChild(card);

    // Update ticket count badge
    updateTicketCount();
}

function checkEmptyTickets() {
    const area = document.getElementById("ticket-area");
    if (!area) return;

    const tickets = area.querySelectorAll(".ticket-card");
    if (tickets.length === 0) {
        const noTickets = document.createElement("div");
        noTickets.className = "no-tickets";
        noTickets.textContent = "No hay solicitudes pendientes en este ciclo.";
        area.appendChild(noTickets);
    }

    updateTicketCount();
}

function updateTicketCount() {
    const area = document.getElementById("ticket-area");
    const badge = document.getElementById("ticket-count-header");
    if (!area || !badge) return;
    const count = area.querySelectorAll(".ticket-card").length;
    badge.textContent = count;
}

function showOccipitalImage(url, caption) {
    const modal = document.getElementById("image-modal");
    const modalImg = document.getElementById("modal-image");
    const modalCaption = document.getElementById("image-caption");

    if (modal && modalImg && modalCaption) {
        modalImg.src = url;
        modalCaption.textContent = caption;
        modal.classList.remove("hidden");
    }
}

function sendWebSocketMessage(topic, data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            "action": "publish",
            "topic": topic,
            "data": data
        }));
    }
}

// ===========================================================================
// Visual Helpers
// ===========================================================================
function flashMemoryCubes(hexColor) {
    const container = document.getElementById("canvas-container");
    if (!container) return;
    const colorStr = "#" + hexColor.toString(16).padStart(6, '0');
    container.style.boxShadow = `inset 0 0 30px ${colorStr}`;
    setTimeout(() => { container.style.boxShadow = ""; }, 500);
}

function pulseMemoryCubes(hexColor) {
    const container = document.getElementById("canvas-container");
    if (!container) return;
    const colorStr = "#" + hexColor.toString(16).padStart(6, '0');
    container.style.boxShadow = `inset 0 0 45px ${colorStr}`;
    setTimeout(() => { container.style.boxShadow = ""; }, 800);
}

function formatUptime(seconds) {
    if (!seconds || seconds < 0) return "0s";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ===========================================================================
// Chat Loading Spinner (Braille characters)
// ===========================================================================
function startThinkingSpinner() {
    if (spinnerInterval) return;

    const logBox = document.getElementById("terminal-logs");
    if (!logBox) return;

    spinnerElement = document.createElement("div");
    spinnerElement.className = "log-line system-msg";
    spinnerElement.style.display = "flex";
    spinnerElement.style.gap = "8px";
    spinnerElement.style.alignItems = "center";
    spinnerElement.style.margin = "4px 0";

    const spinnerChar = document.createElement("span");
    spinnerChar.style.color = "#00f3ff";
    spinnerChar.style.fontWeight = "bold";
    spinnerChar.style.fontFamily = "monospace";
    spinnerChar.textContent = "⠋";

    const spinnerLabel = document.createElement("span");
    spinnerLabel.textContent = "Visión está pensando ";
    spinnerLabel.style.color = "#8fa0b5";

    spinnerElement.appendChild(spinnerChar);
    spinnerElement.appendChild(spinnerLabel);
    logBox.appendChild(spinnerElement);
    logBox.scrollTop = logBox.scrollHeight;

    const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    let idx = 0;
    spinnerInterval = setInterval(() => {
        if (spinnerChar) {
            spinnerChar.textContent = frames[idx];
            idx = (idx + 1) % frames.length;
        }
    }, 40);
}

function stopThinkingSpinner(success = true, modelName = "") {
    if (spinnerInterval) {
        clearInterval(spinnerInterval);
        spinnerInterval = null;
    }
    if (spinnerElement) {
        const spinnerChar = spinnerElement.querySelector("span");
        if (spinnerChar) {
            if (success) spinnerChar.innerHTML = `<span style="color: #39ff14; font-weight: bold;">✓</span>`;
            else spinnerChar.innerHTML = `<span style="color: #ff3333; font-weight: bold;">✗</span>`;
        }
        spinnerElement = null;
    }
}

// ===========================================================================
// 10. SPA Router — History API View Switching
// ===========================================================================
function activateView(viewName) {
    // Hide all views
    document.querySelectorAll(".spa-view").forEach(el => el.classList.remove("active"));
    // Deactivate all nav buttons
    document.querySelectorAll(".spa-nav-btn").forEach(el => el.classList.remove("active"));

    // Activate target
    const view = document.querySelector(`.spa-view[data-view="${viewName}"]`);
    if (view) view.classList.add("active");

    const btn = document.querySelector(`.spa-nav-btn[data-view="${viewName}"]`);
    if (btn) btn.classList.add("active");

    // Update URL hash without triggering popstate
    if (window.location.hash !== `#${viewName}`) {
        history.pushState({ view: viewName }, "", `#${viewName}`);
    }

    // Fetch models when switching to modelos view
    if (viewName === "modelos") {
        fetchAndRenderModels();
    }
}

function setupSPARouter() {
    // Nav button clicks
    document.querySelectorAll(".spa-nav-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const view = btn.dataset.view;
            if (view) activateView(view);
        });
    });

    // Browser back/forward
    window.addEventListener("popstate", (e) => {
        const state = e.state;
        const view = (state && state.view) || window.location.hash.replace("#", "") || "sistema";
        // Direct DOM toggle without pushState (popstate already navigated)
        document.querySelectorAll(".spa-view").forEach(el => el.classList.remove("active"));
        document.querySelectorAll(".spa-nav-btn").forEach(el => el.classList.remove("active"));

        const targetView = document.querySelector(`.spa-view[data-view="${view}"]`);
        if (targetView) targetView.classList.add("active");

        const targetBtn = document.querySelector(`.spa-nav-btn[data-view="${view}"]`);
        if (targetBtn) targetBtn.classList.add("active");

        if (view === "modelos") fetchAndRenderModels();
    });
}

// ===========================================================================
// 11. Hardware Toggles — Mic, Vision, Intriga, Perfil
// ===========================================================================
function setupHardwareToggles() {
    // Mic toggle (pause/resume oido)
    const micToggle = document.getElementById("toggle-mic");
    const micStatus = document.getElementById("toggle-mic-status");
    if (micToggle) {
        // Load initial state from health endpoint
        fetch(`http://${HOST}:${API_PORT}/api/health`)
            .then(r => r.json())
            .then(data => {
                const oidoSvc = data.services && data.services.oido;
                // If oido is running, assume active (the backend handles paused state)
                // We'll use stored state from session
            })
            .catch(() => {});

        micToggle.addEventListener("click", () => {
            const nowActive = micToggle.classList.toggle("active");
            // Green (active class) = mic ON = ACTIVO
            const action = nowActive ? "reanudar" : "pausar";
            if (micStatus) micStatus.textContent = nowActive ? "ACTIVO" : "PAUSADO";

            sendWebSocketMessage("canal.sistema.comando", {
                "comando": "oido",
                "accion": action
            });

            addTerminalLog(`👂 Oído: ${action === "pausar" ? "PAUSADO" : "REANUDADO"} por comando de usuario.`, "system-msg");
        });
    }

    // Vision toggle (pause/resume vision)
    const visionToggle = document.getElementById("toggle-vision");
    const visionStatus = document.getElementById("toggle-vision-status");
    if (visionToggle) {
        visionToggle.addEventListener("click", () => {
            const nowActive = visionToggle.classList.toggle("active");
            const action = nowActive ? "reanudar" : "pausar";
            if (visionStatus) visionStatus.textContent = nowActive ? "ACTIVO" : "PAUSADO";

            sendWebSocketMessage("canal.sistema.comando", {
                "comando": "vision",
                "accion": action
            });

            addTerminalLog(`👁️ Visión: ${action === "pausar" ? "PAUSADA" : "REANUDADA"} por comando de usuario.`, "system-msg");
        });
    }

    // Vision frequency slider
    const visionFreq = document.getElementById("slider-vision-freq");
    const visionFreqVal = document.getElementById("slider-vision-freq-val");
    if (visionFreq && visionFreqVal) {
        visionFreq.addEventListener("input", () => {
            const val = parseInt(visionFreq.value);
            visionFreqVal.textContent = `${val}s`;
        });
        visionFreq.addEventListener("change", () => {
            const val = parseInt(visionFreq.value);
            sendWebSocketMessage("canal.sistema.comando", {
                "comando": "vision",
                "accion": "frecuencia",
                "valor": val
            });
            addTerminalLog(`👁️ Visión: frecuencia de captura cambiada a ${val}s.`, "system-msg");
        });
    }

    // Intrigue sensitivity slider
    const intrigaSens = document.getElementById("slider-intriga-sens");
    const intrigaSensVal = document.getElementById("slider-intriga-sens-val");
    if (intrigaSens && intrigaSensVal) {
        intrigaSens.addEventListener("input", () => {
            intrigaSensVal.textContent = intrigaSens.value;
        });
        intrigaSens.addEventListener("change", () => {
            const val = parseInt(intrigaSens.value);
            sendWebSocketMessage("canal.sistema.comando", {
                "comando": "intriga",
                "accion": "sensibilidad",
                "valor": val
            });
            addTerminalLog(`🔍 Intriga: sensibilidad cambiada a ${val}.`, "system-msg");
        });
    }

    // Nervous profile select
    const profileSelect = document.getElementById("select-perfil");
    if (profileSelect) {
        profileSelect.addEventListener("change", () => {
            const val = profileSelect.value;
            sendWebSocketMessage("canal.sistema.comando", {
                "comando": "perfil",
                "accion": "cambiar",
                "valor": val
            });
            addTerminalLog(`🧬 Perfil nervioso cambiado a: ${val}.`, "system-msg");
        });
    }

    // Terminal toggle (real/mock terminal execution)
    const terminalToggle = document.getElementById("toggle-terminal");
    const terminalStatus = document.getElementById("toggle-terminal-status");
    if (terminalToggle) {
        // Load initial state
        fetch(`http://${HOST}:${API_PORT}/api/config/arranque`)
            .then(r => r.json())
            .then(data => {
                if (data.status === "success" && data.config) {
                    const isMock = data.config.modos_mock && data.config.modos_mock.ejecutor_izquierdo;
                    const nowActive = !isMock; // Real active = not mock
                    if (nowActive) {
                        terminalToggle.classList.add("active");
                        if (terminalStatus) terminalStatus.textContent = "ACTIVO (REAL)";
                    } else {
                        terminalToggle.classList.remove("active");
                        if (terminalStatus) terminalStatus.textContent = "MOCK (SIMULADO)";
                    }
                }
            })
            .catch(() => {});

        terminalToggle.addEventListener("click", async () => {
            const nowActive = terminalToggle.classList.toggle("active");
            if (terminalStatus) terminalStatus.textContent = nowActive ? "ACTIVO (REAL)" : "MOCK (SIMULADO)";

            try {
                // Fetch current config first
                const r = await fetch(`http://${HOST}:${API_PORT}/api/config/arranque`);
                const res = await r.json();
                if (res.status === "success" && res.config) {
                    const cfg = res.config;
                    if (!cfg.modos_mock) cfg.modos_mock = {};
                    cfg.modos_mock.ejecutor_izquierdo = !nowActive; // Mock = not active
                    
                    // Save updated config
                    await fetch(`http://${HOST}:${API_PORT}/api/config/arranque`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(cfg)
                    });
                    
                    addTerminalLog(`💻 Ejecutor Terminal: cambiado a modo ${nowActive ? "REAL" : "SIMULADO"}.`, "system-msg");
                }
            } catch (err) {
                addTerminalLog(`❌ Error al actualizar configuración de arranque: ${err}`, "resp-error");
            }
        });
    }
}

// ===========================================================================
// 12. Credential Saving — POST to /api/config/credenciales
// ===========================================================================
function setupCredentialSaving() {
    // Load existing credentials into inputs
    fetch(`http://${HOST}:${API_PORT}/api/config/credenciales`)
        .then(r => r.json())
        .then(data => {
            if (data.credenciales) {
                Object.entries(data.credenciales).forEach(([key, value]) => {
                    const inputMap = {
                        "OPENROUTER_API_KEY": "cred-openrouter",
                        "OPENAI_API_KEY": "cred-openai",
                        "ANTHROPIC_API_KEY": "cred-anthropic",
                        "LMSTUDIO_API_KEY": "cred-lmstudio",
                        "TAVILY_API_KEY": "cred-tavily"
                    };
                    const inputId = inputMap[key];
                    if (inputId && value) {
                        const input = document.getElementById(inputId);
                        if (input) input.placeholder = `Configurada (${value})`;
                    }
                });
            }
        })
        .catch(() => {});

    // Save buttons
    document.querySelectorAll(".cred-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const key = btn.dataset.key;
            const inputId = btn.dataset.input;
            const input = document.getElementById(inputId);
            if (!key || !input) return;

            const value = input.value.trim();
            if (!value) {
                addTerminalLog(`⚠️ Ingresá un valor para ${key}.`, "resp-error");
                return;
            }

            try {
                const resp = await fetch(`http://${HOST}:${API_PORT}/api/config/credenciales`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ clave: key, valor: value })
                });
                const result = await resp.json();
                if (result.status === "success") {
                    addTerminalLog(`✅ Credencial ${key} guardada en el servidor.`, "resp-success");
                } else {
                    addTerminalLog(`⚠️ Error al guardar ${key}: ${result.message}`, "resp-error");
                }
            } catch (err) {
                addTerminalLog(`❌ Error de red al guardar credencial: ${err}`, "resp-error");
            }
        });
    });
}

// ===========================================================================
// 13. Dynamic Model Fetch — Query mapper endpoints
// ===========================================================================
async function fetchAndRenderModels() {
    const container = document.getElementById("modelos-list");
    if (!container) return;

    const loading = document.getElementById("modelos-loading");
    if (loading) loading.style.display = "block";

    try {
        // Fetch from all mapper endpoints in parallel
        const [openrouterResp, lmstudioResp, ollamaResp, configResp] = await Promise.allSettled([
            fetch(`http://${HOST}:${API_PORT}/api/modelos/openrouter`).then(r => r.json()).catch(() => null),
            fetch(`http://${HOST}:${API_PORT}/api/modelos/lmstudio`).then(r => r.json()).catch(() => null),
            fetch(`http://${HOST}:${API_PORT}/api/modelos/ollama`).then(r => r.json()).catch(() => null),
            fetch(`http://${HOST}:${API_PORT}/api/config`).then(r => r.json()).catch(() => null)
        ]);

        // Remove loading indicator
        if (loading) loading.style.display = "none";

        let html = "";

        // OpenRouter provider card
        const orData = openrouterResp.status === "fulfilled" && openrouterResp.value ? openrouterResp.value : null;
        if (orData && ((orData.gratuitos && orData.gratuitos.length > 0) || (orData.pago && orData.pago.length > 0))) {
            html += `<div class="provider-card">
                <h4>🌐 OpenRouter (Modelos)</h4>
                <div style="display:flex;flex-direction:column;gap:6px;">`;
            
            if (orData.gratuitos && orData.gratuitos.length > 0) {
                html += `<div><strong style="font-size: 10px; color: #39ff14;">Gratuitos:</strong></div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">`;
                orData.gratuitos.forEach(m => {
                    html += `<span class="provider-model" title="Contexto: ${m.context_length}"><code>${escapeHtml(m.id)}</code></span>`;
                });
                html += `</div>`;
            }
            
            if (orData.pago && orData.pago.length > 0) {
                html += `<div style="margin-top:4px;"><strong style="font-size: 10px; color: #00f3ff;">Pago/Destacados:</strong></div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">`;
                // Show first 25 paid models to avoid cluttering
                orData.pago.slice(0, 25).forEach(m => {
                    html += `<span class="provider-model" title="Contexto: ${m.context_length}"><code>${escapeHtml(m.id)}</code></span>`;
                });
                if (orData.pago.length > 25) {
                    html += `<span style="color:#5d6f83;font-size:9px;align-self:center;margin-left:4px;">(+${orData.pago.length - 25} más)</span>`;
                }
                html += `</div>`;
            }
            
            html += `</div></div>`;
        }

        // LMStudio provider card
        const lmData = lmstudioResp.status === "fulfilled" && lmstudioResp.value ? lmstudioResp.value : null;
        if (lmData && lmData.modelos && lmData.modelos.length > 0) {
            html += `<div class="provider-card">
                <h4>💻 LM Studio</h4>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">`;
            lmData.modelos.forEach(m => {
                html += `<span class="provider-model"><code>${escapeHtml(m)}</code></span>`;
            });
            html += `</div></div>`;
        }

        // Ollama provider card
        const olData = ollamaResp.status === "fulfilled" && ollamaResp.value ? ollamaResp.value : null;
        if (olData && olData.modelos && olData.modelos.length > 0) {
            html += `<div class="provider-card">
                <h4>🦙 Ollama (Locales)</h4>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">`;
            olData.modelos.forEach(m => {
                html += `<span class="provider-model"><code>${escapeHtml(m.id)}</code></span>`;
            });
            html += `</div></div>`;
        } else if (olData && olData.status === "offline") {
            html += `<div class="provider-card">
                <h4>🦙 Ollama (Locales)</h4>
                <div style="color: #ff4d4d; font-size: 11px;">⚠️ Offline: ${escapeHtml(olData.error)}</div>
            </div>`;
        }

        // Registered models from config
        const cfgData = configResp.status === "fulfilled" && configResp.value ? configResp.value : null;
        if (cfgData && cfgData.strategies) {
            Object.entries(cfgData.strategies).forEach(([strategy, levels]) => {
                html += `<div class="provider-card">
                    <h4>📋 Estrategia: ${escapeHtml(strategy)}</h4>
                    <div style="display:flex;flex-direction:column;gap:2px;">`;
                Object.entries(levels).forEach(([level, modelInfo]) => {
                    const modelName = modelInfo.model || modelInfo.modelo || "—";
                    html += `<span class="provider-model">${escapeHtml(level)}: <code>${escapeHtml(modelName)}</code></span>`;
                });
                html += `</div></div>`;
            });
        }

        if (!html) {
            html = `<div style="color:#5d6f83;text-align:center;padding:10px;font-style:italic;">No se pudieron obtener modelos de ningún proveedor. Verificá que el servidor esté corriendo.</div>`;
        }

        container.innerHTML = html;
    } catch (err) {
        if (loading) loading.style.display = "none";
        container.innerHTML = `<div style="color:#ff3333;text-align:center;padding:10px;">Error al cargar modelos: ${escapeHtml(err.message || err)}</div>`;
        console.error("Error fetching models:", err);
    }
}

// Bind Ollama pull button
document.addEventListener("DOMContentLoaded", () => {
    const btnPull = document.getElementById("btn-pull-model");
    const inputPull = document.getElementById("input-pull-model");
    const statusPull = document.getElementById("pull-status");

    if (btnPull && inputPull && statusPull) {
        btnPull.addEventListener("click", async () => {
            const modelName = inputPull.value.trim();
            if (!modelName) {
                addTerminalLog("⚠️ Por favor ingresá un tag de modelo válido (ej: llama3.2:latest).", "resp-error");
                return;
            }

            btnPull.disabled = true;
            statusPull.style.display = "block";
            statusPull.style.color = "#39ff14";
            statusPull.textContent = `Descargando ${modelName}... por favor espera, esto puede tomar unos minutos.`;
            addTerminalLog(`📥 Iniciando descarga de Ollama: ${modelName}`, "system-msg");

            try {
                const resp = await fetch(`http://${HOST}:${API_PORT}/api/modelos/ollama/pull`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ modelo: modelName })
                });
                const data = await resp.json();
                if (data.status === "success") {
                    addTerminalLog(`✅ Modelo ${modelName} descargado e instalado con éxito en Ollama.`, "resp-success");
                    statusPull.textContent = `✅ ¡Descargado! ${modelName}`;
                    inputPull.value = "";
                    fetchAndRenderModels(); // Refresh list
                } else {
                    addTerminalLog(`❌ Falló la descarga de ${modelName}: ${data.message}`, "resp-error");
                    statusPull.style.color = "#ff3333";
                    statusPull.textContent = `❌ Falló la descarga: ${data.message}`;
                }
            } catch (err) {
                addTerminalLog(`❌ Error de conexión al descargar modelo: ${err}`, "resp-error");
                statusPull.style.color = "#ff3333";
                statusPull.textContent = `❌ Error de conexión.`;
            } finally {
                btnPull.disabled = false;
            }
        });
    }
});
