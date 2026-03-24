async function apiPost(endpoint, body) {
            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                const data = await res.json();
                if (!res.ok) {
                    alert('Error: ' + (data.error || 'API request failed'));
                    return null;
                }
                return data;
            const origin = document.getElementById('origin').value;
            const depth = parseInt(document.getElementById('depth').value);
            const max_urls = parseInt(document.getElementById('max_urls').value);
            const queue_cap = parseInt(document.getElementById('queue_capacity').value);
            const hit_rate = parseFloat(document.getElementById('hit_rate').value);

            if (!origin) return alert("Origin URL is req.");
            
            await apiPost('/api/crawl', { 
                origin, 
                max_depth: depth, 
                max_urls_to_visit: max_urls, 
                queue_capacity: queue_cap,
                hit_rate: hit_rate
            });
            fetchData(); 
        }

        async function controlState(id, action) {
            await apiPost(`/api/state/${id}`, { action });
            fetchData(); 
        }

        const terminalIntervals = {};
        const openTerminals = new Set();

        function toggleTerminal(crawlerId) {
            const tr = document.getElementById(`term-row-${crawlerId}`);
            if (openTerminals.has(crawlerId)) {
                openTerminals.delete(crawlerId);
                tr.style.display = 'none';
                clearInterval(terminalIntervals[crawlerId]);
                delete terminalIntervals[crawlerId];
            } else {
                openTerminals.add(crawlerId);
                tr.style.display = 'table-row';
                fetchLogs(crawlerId); // Initial fetch
                terminalIntervals[crawlerId] = setInterval(() => fetchLogs(crawlerId), 1000);
            }
        }

        async function fetchLogs(crawlerId) {
            try {
                const res = await fetch(`/api/logs/${crawlerId}`);
                const logs = await res.json();
                const termDiv = document.getElementById(`term-${crawlerId}`);
                if (termDiv) {
                    const isScrolledToBottom = termDiv.scrollHeight - termDiv.clientHeight <= termDiv.scrollTop + 10;
                    termDiv.innerText = logs.length > 0 ? logs.join('\n') : "No logs available yet.";
                    if (isScrolledToBottom) {
                        termDiv.scrollTop = termDiv.scrollHeight;
                    }
                }
            } catch (err) {
                console.error("Error fetching logs", err);
            }
        }

        async function fetchData() {
            try {
                const metRes = await fetch('/api/metrics');
                const metData = await metRes.json();
                document.getElementById('total_words').innerText = metData.total_words_in_db || 0;
                document.getElementById('total_urls').innerText = metData.total_visited_urls || 0;
            } catch(e) {}

            try {
                const res = await fetch('/api/crawlers');
                const data = await res.json();
                const tbody = document.getElementById('crawlers_body');
                
                if (data.length === 0) {
                      tbody.innerHTML = `<tr class="no-crawlers-row"><td colspan="6" style="text-align: center; color: var(--text-muted);">No crawlers active. Launch one!</td></tr>`;
                      return;
                }

                // Remove the "no crawlers active" row if data exists
                const emptyRow = tbody.querySelector('.no-crawlers-row');
                if (emptyRow) {
                    emptyRow.remove();
                }

                const currentIds = new Set(data.map(c => c.id));
                // Remove obsolete rows
                Array.from(tbody.children).forEach(tr => {
                    if (tr.id && tr.id.startsWith('row-') && !currentIds.has(tr.id.replace('row-', ''))) {
                        tr.remove();
                        const termRow = document.getElementById(`term-row-${tr.id.replace('row-', '')}`);
                        if (termRow) termRow.remove();
                    }
                });

                data.forEach(c => {
                    let tr = document.getElementById(`row-${c.id}`);
                    if (!tr) {
                        // Create new rows
                        tbody.insertAdjacentHTML('beforeend', `
                        <tr id="row-${c.id}">
                            <td style="color: var(--accent-purple); font-family: monospace;">${c.id}</td>
                            <td style="max-width: 250px;">${c.origin_url}</td>
                            <td id="status-${c.id}"><span class="status-badge status-${c.status}">${c.status}</span></td>
                            <td id="visited-${c.id}" style="font-weight: bold;">${c.visited_count}</td>
                            <td style="color: var(--text-muted); font-size: 0.9em;">${c.created_at || 'N/A'}</td>
                            <td style="min-width: 140px;" id="actions-${c.id}">
                                <!-- Actions injected below -->
                            </td>
                        </tr>
                        <tr id="term-row-${c.id}" style="display: ${openTerminals.has(c.id) ? 'table-row' : 'none'};">
                            <td colspan="6" style="padding: 0 10px; border-bottom: none;">
                                <div id="term-${c.id}" class="terminal">Loading logs...</div>
                            </td>
                        </tr>`);
                        tr = document.getElementById(`row-${c.id}`);
                    }
                    
                    // Update dynamic parts
                    document.getElementById(`status-${c.id}`).innerHTML = `<span class="status-badge status-${c.status}">${c.status}</span>`;
                    document.getElementById(`visited-${c.id}`).innerText = c.visited_count;
                    
                    document.getElementById(`actions-${c.id}`).innerHTML = `
                        <button class="${c.status === 'Paused' ? 'primary' : 'secondary'} small-btn" onclick="controlState('${c.id}', '${c.status === 'Paused' ? 'resume' : 'pause'}')" ${c.status === 'Stopped' ? 'disabled style="opacity:0.3"' : ''}>${c.status === 'Paused' ? 'Resume' : 'Pause'}</button>
                        <button class="danger small-btn" onclick="controlState('${c.id}', 'stop')" ${c.status === 'Stopped' ? 'disabled style="opacity:0.3"' : ''}>Stop</button>
                        <button class="small-btn" style="background-color: #333; color: #0f0; border: 1px solid #0f0; margin-top: 5px;" onclick="toggleTerminal('${c.id}')">Terminal</button>
                    `;
                });
            } catch(e) {}
        }

        setInterval(fetchData, 1500);
        fetchData();