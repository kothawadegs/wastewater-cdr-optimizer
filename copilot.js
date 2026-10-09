// CDR Siting Copilot: a browser-only tool-calling agent for the dashboard.
// Each visitor supplies their own Hugging Face token; it is sent only to the
// Hugging Face Inference Providers router and never leaves their browser otherwise.
// Tools mirror agent/app.py so both agents give the same answers.

(() => {
    const ROUTER_URL = 'https://router.huggingface.co/v1/chat/completions';
    const DEFAULT_MODEL = 'Qwen/Qwen3-235B-A22B-Instruct-2507';
    const MAX_STEPS = 6;

    // Model constants (mirror src/spatial_ops.py and agent/app.py)
    const GROSS_CO2_PER_MGD = 60;
    const LIMESTONE_PER_MGD = 138;
    const TRUCK_CAPACITY_TONS = 20;
    const EMISSION_FACTOR_KG_PER_MILE = 1.45;
    const EARTH_RADIUS_MILES = 3958.8;

    const SYSTEM_PROMPT =
        'You are the CDR Siting Copilot, a techno-economic analysis assistant for ' +
        'Wastewater Alkalinity Enhancement (WAE) in California. Ground every answer in ' +
        'the tools: use list_ranked_facilities and get_facility_profile for plants in ' +
        'the dataset, find_nearest_quarry for new coordinates, and calculate_net_co2 ' +
        'to report net-negative viability. Always state the net CO2 yield and carbon ' +
        'efficiency clearly, and note that the dataset is a demonstration sample. ' +
        'Answer in plain text without markdown tables.';

    // --- Storage (per-viewer convenience only; may be unavailable) -------------
    const store = {
        get(k) { try { return localStorage.getItem(k); } catch { return null; } },
        set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
        del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
    };

    // --- Data --------------------------------------------------------------------
    let facilities = [];
    let quarries = [];

    const dataReady = Promise.all([
        fetch('ca_wwtp_cdr_viability.geojson').then(r => r.json()),
        fetch('data/california_usgs_mrds_limestone.csv').then(r => r.text()),
    ]).then(([geo, csv]) => {
        facilities = geo.features
            .map(f => f.properties)
            .map(p => ({
                facility_name: p.facility_name,
                flow_mgd: p.flow_mgd,
                latitude: p.Latitude_left,
                longitude: p.Longitude_left,
                nearest_quarry: p.site_name,
                haul_distance_miles: +p.haul_distance_miles.toFixed(2),
                est_co2_t_yr: p.est_co2_t_yr,
                viability_index: +p.viability_index.toFixed(3),
            }))
            .sort((a, b) => b.viability_index - a.viability_index)
            .map((f, i) => ({ rank: i + 1, ...f }));

        const [header, ...rows] = csv.trim().split(/\r?\n/).map(l => l.split(','));
        quarries = rows.map(cols => Object.fromEntries(header.map((h, i) => [h, cols[i]])))
            .map(q => ({ site_name: q.site_name, lat: +q.Latitude, lon: +q.Longitude }));
    });

    function haversineMiles(lat1, lon1, lat2, lon2) {
        const rad = d => d * Math.PI / 180;
        const dp = rad(lat2 - lat1), dl = rad(lon2 - lon1);
        const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
        return 2 * EARTH_RADIUS_MILES * Math.asin(Math.sqrt(a));
    }

    // Pans the dashboard map; a missing map (e.g. Leaflet failed to load) must not break the tool.
    function flyTo(lat, lon) {
        try { map.flyTo([lat, lon], 9, { duration: 1.2 }); } catch { /* map unavailable */ }
    }

    // --- Tools -------------------------------------------------------------------
    const TOOLS = {
        list_ranked_facilities: {
            description: 'Returns California wastewater treatment plants ranked by the pipeline Viability Index (flow_mgd / (haul_distance_miles + 0.1)), highest first.',
            parameters: {
                type: 'object',
                properties: { top_n: { type: 'integer', description: 'Maximum number of facilities to return.' } },
            },
            run: ({ top_n = 10 }) => JSON.stringify(facilities.slice(0, Math.max(1, top_n))),
        },
        get_facility_profile: {
            description: 'Looks up one wastewater treatment plant and returns its flow, coordinates, nearest limestone quarry, haul distance, estimated gross CO2 yield, Viability Index and rank. Case-insensitive partial match.',
            parameters: {
                type: 'object',
                properties: { facility_name: { type: 'string', description: 'Full or partial facility name, e.g. "Hyperion".' } },
                required: ['facility_name'],
            },
            run: ({ facility_name = '' }) => {
                const q = String(facility_name).toLowerCase();
                const matches = facilities.filter(f => f.facility_name.toLowerCase().includes(q));
                if (!matches.length) {
                    return `No facility matching '${facility_name}'. Known facilities: ${facilities.map(f => f.facility_name).join(', ')}`;
                }
                flyTo(matches[0].latitude, matches[0].longitude);
                return JSON.stringify(matches);
            },
        },
        find_nearest_quarry: {
            description: 'Finds the closest limestone quarry (USGS MRDS) to a point and returns its great-circle distance in miles. Use for sites not in the dataset.',
            parameters: {
                type: 'object',
                properties: {
                    latitude: { type: 'number', description: 'Latitude in decimal degrees (WGS84).' },
                    longitude: { type: 'number', description: 'Longitude in decimal degrees (WGS84).' },
                },
                required: ['latitude', 'longitude'],
            },
            run: ({ latitude, longitude }) => {
                const best = quarries
                    .map(q => ({ ...q, miles: haversineMiles(+latitude, +longitude, q.lat, q.lon) }))
                    .sort((a, b) => a.miles - b.miles)[0];
                flyTo(+latitude, +longitude);
                return `Nearest quarry: ${best.site_name} (${best.lat}, ${best.lon}), ${best.miles.toFixed(2)} miles away`;
            },
        },
        calculate_net_co2: {
            description: 'Calculates net CO2 sequestered by a WWTP after subtracting Scope 3 round-trip trucking emissions for hauling limestone (20 t trucks, 1.45 kg CO2 per mile).',
            parameters: {
                type: 'object',
                properties: {
                    facility_name: { type: 'string', description: 'Facility name, used only to label the result.' },
                    flow_mgd: { type: 'number', description: 'Average plant flow in million gallons per day (MGD).' },
                    distance_miles: { type: 'number', description: 'One-way haul distance from quarry to plant in miles.' },
                },
                required: ['facility_name', 'flow_mgd', 'distance_miles'],
            },
            run: ({ facility_name, flow_mgd, distance_miles }) => {
                const flow = +flow_mgd, dist = +distance_miles;
                const gross = flow * GROSS_CO2_PER_MGD;
                const limestone = flow * LIMESTONE_PER_MGD;
                const trips = limestone / TRUCK_CAPACITY_TONS;
                const haul = trips * dist * 2 * EMISSION_FACTOR_KG_PER_MILE / 1000;
                const net = gross - haul;
                const eff = gross ? (net / gross) * 100 : 0;
                const fmt = (n, d = 1) => n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
                return [
                    `Facility: ${facility_name}`,
                    `Limestone required: ${fmt(limestone, 0)} t/yr (${fmt(trips, 0)} truck trips)`,
                    `Gross CO2 sequestered: ${fmt(gross)} t/yr`,
                    `Scope 3 haul emissions: ${fmt(haul)} t/yr (distance: ${dist} mi one-way)`,
                    `Net CO2 yield: ${fmt(net)} t/yr`,
                    `Carbon efficiency: ${eff.toFixed(1)}%`,
                ].join('\n');
            },
        },
    };

    const TOOL_SPECS = Object.entries(TOOLS).map(([name, t]) => ({
        type: 'function',
        function: { name, description: t.description, parameters: t.parameters },
    }));

    // --- Agent loop ----------------------------------------------------------------
    const history = [{ role: 'system', content: SYSTEM_PROMPT }];

    async function callModel(token, model) {
        const res = await fetch(ROUTER_URL, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, messages: history, tools: TOOL_SPECS, tool_choice: 'auto', temperature: 0.1 }),
        });
        if (!res.ok) {
            const body = await res.text();
            throw new Error(`Hugging Face returned ${res.status}: ${body.slice(0, 300)}`);
        }
        return (await res.json()).choices[0].message;
    }

    async function runAgent(userText, token, model, onTool) {
        await dataReady;
        history.push({ role: 'user', content: userText });
        for (let step = 0; step < MAX_STEPS; step++) {
            const msg = await callModel(token, model);
            history.push(msg);
            if (!msg.tool_calls || !msg.tool_calls.length) return msg.content || '(no answer)';
            for (const call of msg.tool_calls) {
                const tool = TOOLS[call.function.name];
                let result;
                try {
                    const args = JSON.parse(call.function.arguments || '{}');
                    onTool(call.function.name, args);
                    result = tool ? tool.run(args) : `Unknown tool: ${call.function.name}`;
                } catch (e) {
                    result = `Tool error: ${e.message}`;
                }
                history.push({ role: 'tool', tool_call_id: call.id, content: result });
            }
        }
        return 'Stopped after too many steps. Try a more specific question.';
    }

    // --- UI ------------------------------------------------------------------------
    const $ = id => document.getElementById(id);
    const panel = $('copilot-panel');
    const log = $('copilot-log');
    const form = $('copilot-form');
    const input = $('copilot-input');
    const tokenInput = $('copilot-token');
    const remember = $('copilot-remember');
    const modelInput = $('copilot-model');

    tokenInput.value = store.get('cdr-copilot-token') || '';
    remember.checked = !!tokenInput.value;
    modelInput.value = store.get('cdr-copilot-model') || DEFAULT_MODEL;

    $('copilot-toggle').addEventListener('click', () => {
        panel.classList.toggle('hidden');
        if (!panel.classList.contains('hidden')) (tokenInput.value ? input : tokenInput).focus();
    });
    $('copilot-close').addEventListener('click', () => panel.classList.add('hidden'));

    function addBubble(text, kind) {
        const el = document.createElement('div');
        const styles = {
            user: 'self-end bg-cyan-900/60 border-cyan-800 text-cyan-50',
            bot: 'self-start bg-slate-800 border-slate-700 text-slate-100',
            tool: 'self-start bg-transparent border-slate-700 text-slate-400 font-mono text-[11px]',
            error: 'self-start bg-red-950/60 border-red-800 text-red-200',
        };
        el.className = `max-w-[90%] whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm ${styles[kind]}`;
        el.textContent = text;
        log.appendChild(el);
        log.scrollTop = log.scrollHeight;
        return el;
    }

    document.querySelectorAll('[data-copilot-example]').forEach(btn =>
        btn.addEventListener('click', () => { input.value = btn.textContent.trim(); input.focus(); })
    );

    form.addEventListener('submit', async e => {
        e.preventDefault();
        const text = input.value.trim();
        const token = tokenInput.value.trim();
        const model = modelInput.value.trim() || DEFAULT_MODEL;
        if (!text) return;
        if (!token) {
            addBubble('Add your Hugging Face token under Settings first.', 'error');
            $('copilot-settings').open = true;
            tokenInput.focus();
            return;
        }
        if (remember.checked) store.set('cdr-copilot-token', token); else store.del('cdr-copilot-token');
        store.set('cdr-copilot-model', model);

        addBubble(text, 'user');
        input.value = '';
        const button = form.querySelector('button[type=submit]');
        button.disabled = true;
        const thinking = addBubble('Thinking…', 'tool');
        const mark = history.length;
        try {
            const answer = await runAgent(text, token, model, (name, args) =>
                log.insertBefore(addBubble(`🔧 ${name}(${JSON.stringify(args)})`, 'tool'), thinking)
            );
            thinking.remove();
            addBubble(answer, 'bot');
        } catch (err) {
            thinking.remove();
            history.length = mark; // drop the failed turn so the next try starts clean
            addBubble(err.message.includes('Failed to fetch')
                ? 'Could not reach Hugging Face. Check your connection and try again.'
                : err.message, 'error');
        } finally {
            button.disabled = false;
            input.focus();
        }
    });
})();
