/* =====================================================
   Gooaye Stock Analyzer Dashboard - JavaScript
   ===================================================== */

// --- State ---
let currentChart = null;
let pinnedStocks = JSON.parse(localStorage.getItem('gooaye_watchlist') || '[]');
let githubApiToken = localStorage.getItem('gooaye_github_token') || '';
let watchlistSha = null;

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    // Detect static mode
    const isStatic = window.location.protocol === 'file:' || window.location.hostname.includes('github.io');
    window._isStatic = isStatic;
    
    if (isStatic) {
        // Load data.json once
        fetch('./data.json')
            .then(res => res.json())
            .then(data => {
                window._staticData = data;
                // If token exists, try to sync first before loading dashboard
                if (githubApiToken) {
                    syncWatchlistFromGitHub().then(() => loadDashboard());
                } else {
                    loadDashboard();
                }
            })
            .catch(err => {
                console.error('Failed to load static data.json', err);
                document.getElementById('latestReport').innerHTML = '<div class="empty-state"><h3>無法載入靜態資料</h3></div>';
            });
    } else {
        if (githubApiToken) {
            syncWatchlistFromGitHub().then(() => loadDashboard());
        } else {
            loadDashboard();
        }
    }
});

async function loadDashboard() {
    try {
        await Promise.all([
            loadSummary(),
            loadLatestReport(),
            loadTracking(),
            loadWatchlist(),
            loadHistory(),
        ]);
        document.getElementById('lastUpdate').textContent =
            `最後更新: ${new Date().toLocaleString('zh-TW')}`;
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

// --- Tab Switching ---
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Load sector charts when switching to that tab
    if (tabName === 'sectors') {
        loadSectorCharts();
    }
}

// --- Summary Cards ---
async function loadSummary() {
    try {
        let data;
        if (window._isStatic) {
            data = window._staticData.summary;
        } else {
            const res = await fetch('/api/dashboard-summary');
            data = await res.json();
        }

        document.getElementById('totalVideos').textContent = data.total_videos || 0;
        document.getElementById('totalRecs').textContent = data.total_recommendations || 0;

        const avgPerf = data.avg_performance || 0;
        const avgEl = document.getElementById('avgPerformance');
        avgEl.textContent = `${avgPerf >= 0 ? '+' : ''}${avgPerf}%`;
        avgEl.style.color = avgPerf >= 0 ? 'var(--green)' : 'var(--red)';

        const bestEl = document.getElementById('bestPerformer');
        if (data.best_performer) {
            bestEl.innerHTML = `
                <span style="font-size:16px">${data.best_performer.name}</span><br>
                <span style="font-size:14px;color:var(--green)">+${data.best_performer.change}%</span>
            `;
        } else {
            bestEl.textContent = '-';
        }

        // Store sector/sentiment data for charts
        window._dashboardData = data;
    } catch (err) {
        console.error('Summary load error:', err);
    }
}

// --- Latest Report ---
async function loadLatestReport() {
    try {
        let videos;
        if (window._isStatic) {
            videos = window._staticData.reports;
        } else {
            const res = await fetch('/api/reports');
            videos = await res.json();
        }

        const container = document.getElementById('latestReport');

        if (!videos || videos.length === 0) {
            return; // Keep empty state
        }

        const latest = videos[0];
        let detail;
        if (window._isStatic) {
            detail = window._staticData.details[latest.video_id] || {};
        } else {
            const detailRes = await fetch(`/api/report/${latest.video_id}`);
            detail = await detailRes.json();
        }

        const summaryItems = (latest.summary || '').split('\n').filter(s => s.trim());
        const recs = detail.recommendations || [];

        container.innerHTML = `
            <div class="card report-card">
                <div class="report-header">
                    <div>
                        <div class="report-title">${escHtml(latest.title)}</div>
                        <div class="report-meta">
                            <span>📅 ${formatDate(latest.published_at)}</span>
                            <span>📊 ${recs.length} 檔推薦標的</span>
                        </div>
                    </div>
                    <a href="${latest.url}" target="_blank" class="report-link">
                        🔗 觀看原始影片
                    </a>
                </div>

                ${summaryItems.length > 0 ? `
                    <h3 style="font-size:15px;font-weight:600;margin-bottom:10px;color:var(--accent-primary-light)">
                        📝 節目摘要
                    </h3>
                    <ul class="summary-list">
                        ${summaryItems.map(s => `<li>${escHtml(s)}</li>`).join('')}
                    </ul>
                ` : ''}

                ${recs.length > 0 ? `
                    <h3 style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent-primary-light)">
                        📊 推薦標的分析
                    </h3>
                    <div class="stock-cards">
                        ${recs.map(rec => renderStockCard(rec)).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    } catch (err) {
        console.error('Latest report load error:', err);
    }
}

function renderStockCard(rec) {
    const sentiment = rec.sentiment || 'neutral';
    const sentimentLabel = { bullish: '看多', bearish: '看空', neutral: '中性' }[sentiment] || '中性';
    const cardId = `stock-${rec.id}`;

    return `
        <div class="card stock-card ${sentiment}" onclick="toggleStockDetail('${cardId}')">
            <div class="stock-card-header">
                <div>
                    <span class="stock-name">${escHtml(rec.stock_name || rec.stock_symbol)}</span>
                    <span class="stock-symbol">${escHtml(rec.stock_symbol)}</span>
                </div>
                <span class="sentiment-badge ${sentiment}">${sentimentLabel}</span>
            </div>
            
            <div class="stock-opinion">${escHtml(rec.gooaye_opinion || '無觀點資料')}</div>
            
            <div class="stock-prices">
                <div class="price-item">
                    <div class="price-label">目前股價</div>
                    <div class="price-value">${formatPrice(rec.price_at_mention)}</div>
                </div>
                <div class="price-item">
                    <div class="price-label">目標價</div>
                    <div class="price-value green">${formatPrice(rec.target_price)}</div>
                </div>
                <div class="price-item">
                    <div class="price-label">停損價</div>
                    <div class="price-value red">${formatPrice(rec.stop_loss)}</div>
                </div>
            </div>
            
            <div class="stock-detail" id="${cardId}">
                <div class="stock-prices" style="margin-bottom:16px">
                    <div class="price-item">
                        <div class="price-label">建議買入</div>
                        <div class="price-value yellow">${formatPrice(rec.buy_price)}</div>
                    </div>
                    <div class="price-item">
                        <div class="price-label">最新價格</div>
                        <div class="price-value ${getChangeClass(rec.latest_change_pct)}">${formatPrice(rec.latest_price)}</div>
                    </div>
                    <div class="price-item">
                        <div class="price-label">績效</div>
                        <div class="price-value ${getChangeClass(rec.latest_change_pct)}">${formatChange(rec.latest_change_pct)}</div>
                    </div>
                </div>

                ${rec.short_term_advice ? `
                    <div class="advice-section">
                        <div class="advice-title">⚡ 短期建議（1-3個月）</div>
                        <div class="advice-text">${escHtml(rec.short_term_advice)}</div>
                    </div>
                ` : ''}
                ${rec.mid_term_advice ? `
                    <div class="advice-section">
                        <div class="advice-title">📊 中期建議（3-12個月）</div>
                        <div class="advice-text">${escHtml(rec.mid_term_advice)}</div>
                    </div>
                ` : ''}
                ${rec.long_term_advice ? `
                    <div class="advice-section">
                        <div class="advice-title">🏗️ 長期建議（1年以上）</div>
                        <div class="advice-text">${escHtml(rec.long_term_advice)}</div>
                    </div>
                ` : ''}
                ${rec.analysis_detail ? `
                    <div class="advice-section">
                        <div class="advice-title">📋 完整分析</div>
                        <div class="analysis-full">${escHtml(rec.analysis_detail)}</div>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function toggleStockDetail(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('show');
    }
}

// --- Tracking Table ---
async function loadTracking() {
    try {
        let recs;
        if (window._isStatic) {
            recs = window._staticData.recommendations;
        } else {
            const res = await fetch('/api/recommendations');
            recs = await res.json();
        }

        const container = document.getElementById('trackingTable');

        if (!recs || recs.length === 0) {
            return; // Keep empty state
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="tracking-table">
                    <thead>
                        <tr>
                            <th>標的</th>
                            <th>市場</th>
                            <th>推薦來源</th>
                            <th>推薦時股價</th>
                            <th>最新股價</th>
                            <th>漲跌幅</th>
                            <th>情緒</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${recs.map(rec => `
                            <tr onclick="showPerformanceChart(${rec.id}, '${escAttr(rec.stock_name || rec.stock_symbol)}')">
                                <td>
                                    <div style="display:flex; align-items:center; gap:8px">
                                        <button class="btn-pin ${pinnedStocks.includes(rec.stock_symbol) ? 'pinned' : ''}" 
                                                onclick="event.stopPropagation(); togglePinStatus('${escAttr(rec.stock_symbol)}')">
                                            📌
                                        </button>
                                        <div>
                                            <strong>${escHtml(rec.stock_name || '')}</strong>
                                            <div style="font-size:12px;color:var(--text-muted)">${escHtml(rec.stock_symbol)}</div>
                                        </div>
                                    </div>
                                </td>
                                <td>${rec.market === 'TW' ? '🇹🇼 台股' : '🇺🇸 美股'}</td>
                                <td style="font-size:13px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(rec.video_title || '')}</td>
                                <td>${formatPrice(rec.price_at_mention)}</td>
                                <td>${formatPrice(rec.latest_price)}</td>
                                <td class="${getChangeClass(rec.latest_change_pct)}">${formatChange(rec.latest_change_pct)}</td>
                                <td><span class="sentiment-badge ${rec.sentiment || 'neutral'}">${{ bullish: '看多', bearish: '看空', neutral: '中性' }[rec.sentiment] || '中性'}</span></td>
                                <td><button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();showPerformanceChart(${rec.id}, '${escAttr(rec.stock_name || rec.stock_symbol)}')">📈 走勢</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        console.error('Tracking load error:', err);
    }
}

// --- Watchlist ---
let syncTimeout = null;

function togglePinStatus(symbol) {
    if (pinnedStocks.includes(symbol)) {
        pinnedStocks = pinnedStocks.filter(s => s !== symbol);
        showToast(`已取消追蹤 ${symbol}`);
    } else {
        pinnedStocks.push(symbol);
        showToast(`已將 ${symbol} 加入追蹤清單`, 'success');
    }
    localStorage.setItem('gooaye_watchlist', JSON.stringify(pinnedStocks));
    
    // Refresh tables
    loadTracking();
    loadWatchlist();

    // Auto-sync to GitHub if token exists (with debounce)
    if (githubApiToken) {
        if (syncTimeout) clearTimeout(syncTimeout);
        syncTimeout = setTimeout(() => {
            syncWatchlistToGitHub();
        }, 1500);
    }
}

async function loadWatchlist() {
    try {
        let recs;
        if (window._isStatic) {
            recs = window._staticData.recommendations;
        } else {
            const res = await fetch('/api/recommendations');
            recs = await res.json();
        }

        const container = document.getElementById('watchlistTable');
        
        // Filter out only the most recent recommendation for each pinned stock symbol
        const pinnedRecsMap = new Map();
        if (recs && recs.length > 0) {
            recs.forEach(rec => {
                if (pinnedStocks.includes(rec.stock_symbol)) {
                    // Because they are sorted by date descending, the first one we encounter is the latest
                    if (!pinnedRecsMap.has(rec.stock_symbol)) {
                        pinnedRecsMap.set(rec.stock_symbol, rec);
                    }
                }
            });
        }
        
        const pinnedRecs = Array.from(pinnedRecsMap.values());

        if (pinnedRecs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📌</div>
                    <h3>尚未釘選任何標的</h3>
                    <p>請到「標的追蹤」中點擊圖示加入追蹤</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="stock-cards">
                ${pinnedRecs.map(rec => renderStockCard(rec)).join('')}
            </div>
        `;
        
        updateSyncStatusUI();
    } catch (err) {
        console.error('Watchlist load error:', err);
    }
}

// --- GitHub Sync Settings ---
function openSettingsModal() {
    document.getElementById('githubTokenInput').value = githubApiToken;
    document.getElementById('settingsModal').style.display = 'flex';
}

function closeSettingsModal() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    const token = document.getElementById('githubTokenInput').value.trim();
    if (token) {
        githubApiToken = token;
        localStorage.setItem('gooaye_github_token', githubApiToken);
        showToast('設定已儲存，正在同步中...', 'info');
        closeSettingsModal();
        syncWatchlistFromGitHub().then(() => {
            loadTracking();
            loadWatchlist();
        });
    } else {
        showToast('請輸入 Token', 'error');
    }
}

function clearSettings() {
    githubApiToken = '';
    watchlistSha = null;
    localStorage.removeItem('gooaye_github_token');
    document.getElementById('githubTokenInput').value = '';
    updateSyncStatusUI();
    showToast('同步設定已清除', 'info');
    closeSettingsModal();
}

function updateSyncStatusUI() {
    const badge = document.getElementById('syncStatusBadge');
    if (!badge) return;
    
    if (githubApiToken) {
        badge.className = 'sentiment-badge bullish';
        badge.innerHTML = '🟢 雲端同步中';
    } else {
        badge.className = 'sentiment-badge neutral';
        badge.innerHTML = '本機模式';
    }
}

async function syncWatchlistFromGitHub() {
    if (!githubApiToken) return;
    
    try {
        const url = 'https://api.github.com/repos/fc861117-sketch/goodeyestocktracking/contents/docs/watchlist.json';
        const res = await fetch(url, {
            headers: {
                'Authorization': `token ${githubApiToken}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });
        
        if (res.ok) {
            const data = await res.json();
            watchlistSha = data.sha;
            
            // Decode base64 content
            const content = decodeURIComponent(escape(atob(data.content)));
            const remoteStocks = JSON.parse(content || '[]');
            
            // Merge remote and local (simple union)
            const merged = [...new Set([...pinnedStocks, ...remoteStocks])];
            if (merged.length !== pinnedStocks.length || JSON.stringify(merged) !== JSON.stringify(pinnedStocks)) {
                pinnedStocks = merged;
                localStorage.setItem('gooaye_watchlist', JSON.stringify(pinnedStocks));
                showToast('已從雲端載入最新追蹤清單', 'success');
            }
            
            // Auto-heal: If our local merged state has more items than the remote, push it back
            if (JSON.stringify(merged) !== JSON.stringify(remoteStocks)) {
                setTimeout(() => syncWatchlistToGitHub(), 2000); // Wait a bit to avoid immediate conflicts
            }
        } else if (res.status === 404) {
            // File doesn't exist yet, push current local state to create it
            await syncWatchlistToGitHub();
        } else {
            console.error('GitHub API returned status:', res.status);
            showToast('雲端同步失敗，請檢查 Token 權限', 'error');
        }
    } catch (err) {
        console.error('Failed to sync from GitHub', err);
    }
}

async function syncWatchlistToGitHub() {
    if (!githubApiToken) return;
    
    try {
        const url = 'https://api.github.com/repos/fc861117-sketch/goodeyestocktracking/contents/docs/watchlist.json';
        
        // Encode content to base64
        const contentStr = JSON.stringify(pinnedStocks, null, 2);
        const encodedContent = btoa(unescape(encodeURIComponent(contentStr)));
        
        const body = {
            message: 'sync: Update watchlist from dashboard',
            content: encodedContent,
            branch: 'main'
        };
        
        if (watchlistSha) {
            body.sha = watchlistSha;
        }
        
        const res = await fetch(url, {
            method: 'PUT',
            headers: {
                'Authorization': `token ${githubApiToken}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });
        
        if (res.ok) {
            const data = await res.json();
            watchlistSha = data.content.sha;
            console.log('Successfully synced to GitHub');
        } else if (res.status === 409) {
            // Conflict (sha mismatch). We should re-fetch and merge
            console.warn('Conflict syncing to GitHub, retrying...');
            await syncWatchlistFromGitHub();
            await syncWatchlistToGitHub(); // Retry after fetching latest sha
        } else {
            console.error('Failed to sync to GitHub:', await res.text());
            showToast('雲端同步失敗，請確認 Token 權限是否有勾選 repo', 'error');
        }
    } catch (err) {
        console.error('Failed to sync to GitHub', err);
        showToast('雲端同步發生錯誤', 'error');
    }
}

// --- Performance Chart Modal ---
async function showPerformanceChart(recId, name) {
    try {
        let data;
        if (window._isStatic) {
            data = window._staticData.performance[recId] || {};
        } else {
            const res = await fetch(`/api/performance/${recId}`);
            data = await res.json();
        }

        const modal = document.getElementById('chartModal');
        const titleEl = document.getElementById('chartTitle');
        const detailEl = document.getElementById('modalDetail');

        titleEl.textContent = `📈 ${name} 績效走勢`;
        modal.style.display = 'flex';

        const rec = data.recommendation || {};
        const history = data.history || [];

        // Render chart
        const ctx = document.getElementById('performanceChart').getContext('2d');

        if (currentChart) {
            currentChart.destroy();
        }

        if (history.length > 0) {
            const labels = history.map(h => h.tracked_date);
            const prices = history.map(h => h.current_price);
            const changes = history.map(h => h.price_change_pct);

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '股價',
                            data: prices,
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            borderWidth: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            labels: { color: '#94a3b8', font: { family: 'Inter' } }
                        },
                        tooltip: {
                            callbacks: {
                                afterLabel: function(context) {
                                    const idx = context.dataIndex;
                                    return `漲跌: ${formatChange(changes[idx])}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#64748b', font: { size: 11 } },
                            grid: { color: 'rgba(255,255,255,0.04)' },
                        },
                        y: {
                            ticks: { color: '#64748b', font: { size: 11 } },
                            grid: { color: 'rgba(255,255,255,0.04)' },
                        },
                    },
                },
            });
        }

        // Detail info
        detailEl.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:8px">
                <div class="price-item">
                    <div class="price-label">推薦時股價</div>
                    <div class="price-value">${formatPrice(rec.price_at_mention)}</div>
                </div>
                <div class="price-item">
                    <div class="price-label">目標價</div>
                    <div class="price-value green">${formatPrice(rec.target_price)}</div>
                </div>
                <div class="price-item">
                    <div class="price-label">停損價</div>
                    <div class="price-value red">${formatPrice(rec.stop_loss)}</div>
                </div>
            </div>
            ${rec.gooaye_opinion ? `<p style="margin-top:16px"><strong>股癌觀點：</strong>${escHtml(rec.gooaye_opinion)}</p>` : ''}
        `;
    } catch (err) {
        console.error('Chart load error:', err);
        showToast('載入走勢圖失敗', 'error');
    }
}

function closeChartModal() {
    document.getElementById('chartModal').style.display = 'none';
    if (currentChart) {
        currentChart.destroy();
        currentChart = null;
    }
}

// Close modals on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        if (e.target.id === 'chartModal') closeChartModal();
        if (e.target.id === 'settingsModal') closeSettingsModal();
    }
});

// Close modals on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeChartModal();
        closeSettingsModal();
    }
});

// --- History ---
async function loadHistory() {
    try {
        let videos;
        if (window._isStatic) {
            videos = window._staticData.reports;
        } else {
            const res = await fetch('/api/reports');
            videos = await res.json();
        }

        const container = document.getElementById('historyList');

        if (!videos || videos.length === 0) {
            return;
        }

        container.innerHTML = videos.map(v => `
            <div class="card history-item" onclick="toggleHistoryDetail('history-${v.video_id}', '${v.video_id}')">
                <div class="history-item-header">
                    <div class="history-title">${escHtml(v.title)}</div>
                    <div class="history-date">${formatDate(v.published_at)}</div>
                </div>
                <div class="history-badges">
                    <span class="history-badge">📊 ${v.recommendation_count || 0} 檔標的</span>
                    <span class="history-badge">📅 ${formatDate(v.processed_at)}</span>
                </div>
                <div class="history-detail" id="history-${v.video_id}"></div>
            </div>
        `).join('');
    } catch (err) {
        console.error('History load error:', err);
    }
}

async function toggleHistoryDetail(elementId, videoId) {
    const el = document.getElementById(elementId);
    if (!el) return;

    if (el.classList.contains('show')) {
        el.classList.remove('show');
        return;
    }

    // Load detail if not loaded
    if (!el.dataset.loaded) {
        try {
            let data;
            if (window._isStatic) {
                data = window._staticData.details[videoId] || {};
            } else {
                const res = await fetch(`/api/report/${videoId}`);
                data = await res.json();
            }
            
            const recs = data.recommendations || [];
            const video = data.video || {};
            const summaryItems = (video.summary || '').split('\n').filter(s => s.trim());

            el.innerHTML = `
                ${summaryItems.length > 0 ? `
                    <h4 style="font-size:14px;font-weight:600;margin-bottom:8px;color:var(--accent-primary-light)">📝 節目摘要</h4>
                    <ul class="summary-list">
                        ${summaryItems.map(s => `<li>${escHtml(s)}</li>`).join('')}
                    </ul>
                ` : ''}
                ${recs.length > 0 ? `
                    <h4 style="font-size:14px;font-weight:600;margin:12px 0 8px;color:var(--accent-primary-light)">📊 推薦標的</h4>
                    <div class="stock-cards">
                        ${recs.map(rec => renderStockCard(rec)).join('')}
                    </div>
                ` : '<p style="color:var(--text-muted)">未識別到推薦標的</p>'}
            `;
            el.dataset.loaded = 'true';
        } catch (err) {
            el.innerHTML = '<p style="color:var(--red)">載入失敗</p>';
        }
    }

    el.classList.add('show');
}

// --- Sector Charts ---
async function loadSectorCharts() {
    const data = window._dashboardData;
    if (!data) return;

    // Sector distribution pie chart
    const sectors = data.sectors || [];
    if (sectors.length > 0) {
        const sectorCtx = document.getElementById('sectorChart').getContext('2d');
        new Chart(sectorCtx, {
            type: 'doughnut',
            data: {
                labels: sectors.map(s => s.sector),
                datasets: [{
                    data: sectors.map(s => s.count),
                    backgroundColor: [
                        '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
                        '#f59e0b', '#10b981', '#3b82f6', '#06b6d4',
                        '#84cc16', '#d946ef',
                    ],
                    borderColor: 'transparent',
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { family: 'Inter', size: 12 },
                            padding: 16,
                        },
                    },
                },
            },
        });
    }

    // Sentiment distribution
    const sentiments = data.sentiments || [];
    if (sentiments.length > 0) {
        const sentCtx = document.getElementById('sentimentChart').getContext('2d');
        const sentColors = { bullish: '#10b981', bearish: '#ef4444', neutral: '#f59e0b' };
        const sentLabels = { bullish: '看多', bearish: '看空', neutral: '中性' };

        new Chart(sentCtx, {
            type: 'doughnut',
            data: {
                labels: sentiments.map(s => sentLabels[s.sentiment] || s.sentiment),
                datasets: [{
                    data: sentiments.map(s => s.count),
                    backgroundColor: sentiments.map(s => sentColors[s.sentiment] || '#64748b'),
                    borderColor: 'transparent',
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            font: { family: 'Inter', size: 12 },
                            padding: 16,
                        },
                    },
                },
            },
        });
    }

    // Sector Trend Chart (族群輪動圖表)
    const recs = window._isStatic ? window._staticData.recommendations : null;
    const trendCtx = document.getElementById('sectorTrendChart');
    if (trendCtx && recs && recs.length > 0) {
        // Group by date and sector
        const dates = [...new Set(recs.map(r => r.published_at.split('T')[0]))].sort();
        const sectorNames = [...new Set(recs.map(r => r.sector).filter(s => s))];
        
        const datasets = sectorNames.map((sector, i) => {
            const colorIndex = i % 10;
            const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#10b981', '#3b82f6', '#06b6d4', '#84cc16', '#d946ef'];
            
            const dataCounts = dates.map(date => {
                return recs.filter(r => r.sector === sector && r.published_at.startsWith(date)).length;
            });
            
            return {
                label: sector,
                data: dataCounts,
                borderColor: colors[colorIndex],
                backgroundColor: colors[colorIndex] + '33', // 20% opacity
                fill: true,
                tension: 0.3
            };
        });

        new Chart(trendCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: dates,
                datasets: datasets
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '產業板塊熱度趨勢 (Sector Rotation)',
                        color: '#f8fafc',
                        font: { family: 'Inter', size: 14 }
                    },
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, color: '#64748b' },
                        grid: { color: 'rgba(255,255,255,0.04)' }
                    },
                    x: {
                        ticks: { color: '#64748b' },
                        grid: { color: 'rgba(255,255,255,0.04)' }
                    }
                }
            }
        });
    }
}

// --- Update Prices ---
async function updatePrices() {
    if (window._isStatic) {
        showToast('靜態網頁無法直接更新股價，請在本機執行腳本更新', 'info');
        return;
    }
    
    const btn = document.getElementById('btnUpdatePrices');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> 更新中...';

    try {
        const res = await fetch('/api/update-prices', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            showToast(`✅ 股價更新完成：${data.stats.updated} 筆成功`, 'success');
            // Reload data
            await loadDashboard();
        } else {
            showToast(`❌ 更新失敗：${data.error}`, 'error');
        }
    } catch (err) {
        showToast('❌ 更新請求失敗', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🔄</span> 更新股價';
    }
}

// --- Utilities ---
function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escAttr(str) {
    if (!str) return '';
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function formatPrice(price) {
    if (price === null || price === undefined) return '-';
    return Number(price).toLocaleString('zh-TW', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatChange(pct) {
    if (pct === null || pct === undefined) return '-';
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${Number(pct).toFixed(2)}%`;
}

function getChangeClass(pct) {
    if (pct === null || pct === undefined) return 'change-neutral';
    if (pct > 0) return 'change-positive';
    if (pct < 0) return 'change-negative';
    return 'change-neutral';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    } catch {
        return dateStr;
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}
