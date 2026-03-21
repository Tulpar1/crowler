async function search() {
            const q = document.getElementById('search_query').value.trim();
            if (!q) return;

            document.getElementById('search_container').style.paddingTop = '30px';
            document.getElementById('results_container').style.display = 'block';

            const tbody = document.getElementById('results_body');
            tbody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--accent-cyan);">Searching...</td></tr>`;

            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                
                tbody.innerHTML = ''; 

                if (data.results && data.results.length > 0) {
                    data.results.forEach(row => {
                        let snippetHtml = '';
                        if (row.context_snippet) {
                            // Highlight the query word in the snippet
                            const regex = new RegExp(`(${q})`, 'gi');
                            const highlightedSnippet = row.context_snippet.replace(regex, '<span style="color: var(--accent-cyan); font-weight: bold;">$1</span>');
                            snippetHtml = `<div style="font-size: 0.85em; font-style: italic; color: #A0A0A0; margin-top: 5px; margin-bottom: 5px;">${highlightedSnippet}</div>`;
                        }

                        tbody.innerHTML += `<tr>
                            <td>
                                <a href="${row.url}" target="_blank" style="color:var(--accent-cyan);text-decoration:none;font-size:1.1em;font-weight:bold;">${row.url}</a>
                                ${snippetHtml}
                                <span class="meta-info">Origin: ${row.origin_url} | Depth: ${row.depth}</span>
                            </td>
                            <td><span class="score-badge">${row.score}</span></td>
                        </tr>`;
                    });
                } else {
                    tbody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--danger);">No matches found for "${q}".</td></tr>`;
                }
            } catch (err) {
                console.error(err);
                tbody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--danger);">Error fulfilling search request.</td></tr>`;
            }
        }