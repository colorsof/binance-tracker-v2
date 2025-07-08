// Global state
let tableData = [];
let sortColumn = 'overall_performance';
let sortOrder = 'desc';
let filters = {
    minGrowth: 0,
    searchSymbol: '',
    correlation: '',
    consistentOnly: false
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
    document.getElementById('minGrowth').addEventListener('input', applyFilters);
    document.getElementById('searchSymbol').addEventListener('input', applyFilters);
    document.getElementById('corrFilter').addEventListener('change', applyFilters);
    document.getElementById('consistentFilter').addEventListener('change', applyFilters);
    
    // Set up table sorting
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => handleSort(th));
    });
    
    // Load initial data
    loadData();
    
    // Auto-refresh every 30 seconds
    setInterval(loadData, 30000);
});

async function loadData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        
        tableData = data.data || [];
        
        // Update stats
        document.getElementById('totalCoins').textContent = data.total_coins;
        document.getElementById('lastUpdate').textContent = 
            data.last_update ? new Date(data.last_update).toLocaleString() : 'Never';
        
        // Apply filters and render
        applyFilters();
        
    } catch (error) {
        console.error('Failed to load data:', error);
        showError('Failed to load data');
    }
}

async function refreshData() {
    const btn = document.getElementById('refreshBtn');
    btn.disabled = true;
    btn.textContent = '⟳ Refreshing...';
    
    try {
        const response = await fetch('/api/refresh', { method: 'POST' });
        const result = await response.json();
        
        if (result.status === 'success') {
            // Wait a bit then reload
            setTimeout(loadData, 2000);
        } else {
            showError(result.message);
        }
    } catch (error) {
        showError('Refresh failed');
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = '⟳ Refresh';
        }, 3000);
    }
}

function applyFilters() {
    // Get filter values
    filters.minGrowth = parseFloat(document.getElementById('minGrowth').value) || 0;
    filters.searchSymbol = document.getElementById('searchSymbol').value.toUpperCase();
    filters.correlation = document.getElementById('corrFilter').value;
    filters.consistentOnly = document.getElementById('consistentFilter').checked;
    
    // Filter data
    let filtered = tableData.filter(item => {
        // Symbol search
        if (filters.searchSymbol && !item.symbol.includes(filters.searchSymbol)) {
            return false;
        }
        
        // Minimum growth filter
        const hasMinGrowth = Object.values(item.growth_rates).some(rate => 
            rate !== null && rate >= filters.minGrowth
        );
        if (!hasMinGrowth) {
            return false;
        }
        
        // Correlation filter
        if (filters.correlation) {
            const corr = item.btc_correlation;
            if (corr === null) return false;
            
            if (filters.correlation === 'high' && corr < 70) return false;
            if (filters.correlation === 'medium' && (corr < 30 || corr > 70)) return false;
            if (filters.correlation === 'low' && corr > 30) return false;
        }
        
        // Consistent performer filter
        if (filters.consistentOnly && !item.consistency_score) {
            return false;
        }
        
        return true;
    });
    
    // Sort data
    sortData(filtered);
    
    // Render table
    renderTable(filtered);
}

function sortData(data) {
    data.sort((a, b) => {
        let aValue, bValue;
        
        if (sortColumn === 'symbol') {
            aValue = a.symbol;
            bValue = b.symbol;
        } else if (sortColumn === 'price') {
            aValue = a.price;
            bValue = b.price;
        } else if (sortColumn === 'consistency') {
            aValue = a.consistency_score || -999;
            bValue = b.consistency_score || -999;
        } else if (sortColumn === 'overall_performance') {
            aValue = a.overall_performance || -999;
            bValue = b.overall_performance || -999;
        } else if (sortColumn === 'btc_correlation') {
            aValue = a.btc_correlation || -999;
            bValue = b.btc_correlation || -999;
        } else {
            // Growth rate columns
            aValue = a.growth_rates[sortColumn] || -999;
            bValue = b.growth_rates[sortColumn] || -999;
        }
        
        if (sortOrder === 'asc') {
            return aValue > bValue ? 1 : -1;
        } else {
            return aValue < bValue ? 1 : -1;
        }
    });
}

function handleSort(th) {
    const column = th.dataset.column;
    
    // Update sort state
    if (column === sortColumn) {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortOrder = 'desc';
    }
    
    // Update UI
    document.querySelectorAll('.sortable').forEach(el => {
        el.classList.remove('active', 'asc', 'desc');
    });
    th.classList.add('active', sortOrder);
    
    // Re-render
    applyFilters();
}

function renderTable(data) {
    const tbody = document.getElementById('tableBody');
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="loading">No data found</td></tr>';
        return;
    }
    
    tbody.innerHTML = data.map(item => {
        const intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '7h', '12h'];
        const growthCells = intervals.map(interval => {
            const rate = item.growth_rates[interval];
            if (rate === null || rate === undefined) {
                return '<td class="growth-cell no-data">-</td>';
            }
            
            const absRate = Math.abs(rate);
            const isPositive = rate >= 0;
            const isHigh = absRate > 10;
            
            const classes = [
                'growth-cell',
                isPositive ? 'growth-positive' : 'growth-negative',
                isHigh ? 'high' : ''
            ].join(' ');
            
            return `<td class="${classes}">${rate >= 0 ? '+' : ''}${rate.toFixed(2)}%</td>`;
        }).join('');
        
        // Correlation cell
        let corrCell = '<td class="correlation-cell no-data">-</td>';
        if (item.btc_correlation !== null) {
            const corr = item.btc_correlation;
            let corrClass = 'correlation-low';
            if (corr > 70) corrClass = 'correlation-high';
            else if (corr > 30) corrClass = 'correlation-medium';
            
            corrCell = `<td class="correlation-cell ${corrClass}">${corr.toFixed(1)}%</td>`;
        }
        
        // Consistency cell
        let consistencyCell = '<td class="consistency-cell no-data">-</td>';
        if (item.consistency_score !== null && item.consistency_score !== undefined) {
            consistencyCell = `<td class="consistency-cell consistency-good">${item.consistency_score.toFixed(1)}%</td>`;
        }
        
        // Overall performance cell
        let overallCell = '<td class="overall-cell no-data">-</td>';
        if (item.overall_performance !== null && item.overall_performance !== undefined) {
            const overall = item.overall_performance;
            const overallClass = overall >= 10 ? 'overall-excellent' : overall >= 5 ? 'overall-good' : overall >= 0 ? 'overall-neutral' : 'overall-negative';
            overallCell = `<td class="overall-cell ${overallClass}">${overall >= 0 ? '+' : ''}${overall.toFixed(2)}%</td>`;
        }
        
        return `
            <tr>
                <td><strong>${item.symbol}</strong></td>
                ${consistencyCell}
                <td>$${item.price.toFixed(6)}</td>
                ${growthCells}
                ${overallCell}
                ${corrCell}
            </tr>
        `;
    }).join('');
}

function showError(message) {
    console.error(message);
    // You could add a toast notification here
}