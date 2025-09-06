// assets/js/dragon_tiger.js - 龙虎榜页面功能

let currentDragonTigerData = null;
let currentDetailStock = null;

document.addEventListener('DOMContentLoaded', function() {
    initDragonTigerPage();
});

async function initDragonTigerPage() {
    await loadDragonTigerDateOptions();
    setupDragonTigerEventListeners();
}

// 加载日期选项
async function loadDragonTigerDateOptions() {
    try {
        const response = await fetch('dragon_tiger/index.json');
        if (!response.ok) throw new Error('无法加载龙虎榜日期数据');
        
        const indexData = await response.json();
        const dates = Object.keys(indexData).sort().reverse();
        const dateFilter = document.getElementById('dateFilter');
        
        if (!dateFilter) {
            console.error('dateFilter元素未找到');
            return;
        }
        
        dateFilter.innerHTML = '<option value="">选择日期</option>';
        dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateFilter.appendChild(option);
        });
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            await loadDragonTigerData(dates[0]);
        }
    } catch (error) {
        console.error('加载龙虎榜日期选项失败:', error);
        const container = document.getElementById('dragonTigerContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupDragonTigerEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadDragonTigerData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterDragonTigerStocks, 300));
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyDragonTigerData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewDragonTigerJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载龙虎榜数据
async function loadDragonTigerData(date) {
    const container = document.getElementById('dragonTigerContainer');
    const dataInfo = document.getElementById('dataInfo');
    const marketStats = document.getElementById('marketStats');
    
    if (!container) {
        console.error('dragonTigerContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    if (marketStats) {
        marketStats.style.display = 'none';
    }
    
    try {
        const response = await fetch(`dragon_tiger/${date}.json`);
        if (!response.ok) throw new Error('龙虎榜数据加载失败');
        
        currentDragonTigerData = await response.json();
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const stockCountEl = document.getElementById('stockCount');
        const successRateEl = document.getElementById('successRate');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentDragonTigerData.update_time;
        }
        if (stockCountEl) {
            stockCountEl.textContent = currentDragonTigerData.total_count + '只';
        }
        if (successRateEl) {
            const successRate = (currentDragonTigerData.statistics.success_count / currentDragonTigerData.total_count * 100).toFixed(1);
            successRateEl.textContent = successRate + '%';
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 显示市场分布
        renderMarketStats(currentDragonTigerData.overview.stocks);
        
        // 渲染股票列表
        renderDragonTigerStocks(currentDragonTigerData.details);
        
    } catch (error) {
        console.error('加载龙虎榜数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染市场分布统计
function renderMarketStats(stocks) {
    const marketStats = document.getElementById('marketStats');
    const marketStatsGrid = document.getElementById('marketStatsGrid');
    
    if (!marketStats || !marketStatsGrid) return;
    
    // 统计市场分布
    const marketCounts = {};
    stocks.forEach(stock => {
        const market = stock.market_name;
        marketCounts[market] = (marketCounts[market] || 0) + 1;
    });
    
    const statsHtml = Object.entries(marketCounts).map(([market, count]) => 
        '<div class="stat-item"><span class="stat-label">' + market + '</span><span class="stat-value">' + count + '只</span></div>'
    ).join('');
    
    marketStatsGrid.innerHTML = statsHtml;
    marketStats.style.display = 'block';
}

// 渲染龙虎榜股票列表
function renderDragonTigerStocks(details) {
    const container = document.getElementById('dragonTigerContainer');
    
    if (!container) {
        console.error('dragonTigerContainer元素未找到');
        return;
    }
    
    // 只显示查询成功的股票
    const successfulStocks = Object.entries(details).filter(([code, data]) => 
        data.status === 'success'
    );
    
    if (successfulStocks.length === 0) {
        container.innerHTML = '<div class="loading">暂无成功查询的龙虎榜数据</div>';
        return;
    }
    
    const stocksHtml = successfulStocks.map(([code, data]) => {
        const lhbInfo = data.lhb_info || {};
        const capitalFlow = data.capital_flow || {};
        const changePercent = lhbInfo.change_percent || 0;
        const changeClass = changePercent >= 0 ? 'positive' : 'negative';
        const changeSign = changePercent >= 0 ? '+' : '';
        const closePrice = lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00';
        
        const capitalFlowHtml = capitalFlow.net_inflow !== undefined ? 
            '<div class="capital-flow-summary">' +
                '<div class="flow-item">' +
                    '<span class="flow-label">买入合计</span>' +
                    '<span class="flow-value">' + formatAmount(capitalFlow.buy_total) + '万</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">卖出合计</span>' +
                    '<span class="flow-value">' + formatAmount(capitalFlow.sell_total) + '万</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">净流入</span>' +
                    '<span class="flow-value ' + (capitalFlow.net_inflow >= 0 ? 'positive' : 'negative') + '">' +
                        (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万' +
                    '</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">主力席位</span>' +
                    '<span class="flow-value">' + ((data.buy_seats ? data.buy_seats.length : 0) + (data.sell_seats ? data.sell_seats.length : 0)) + '个</span>' +
                '</div>' +
            '</div>' : '';
        
        return '<div class="dragon-tiger-card" data-code="' + code + '" data-name="' + data.name + '">' +
            '<div class="dragon-tiger-header">' +
                '<div class="stock-basic-info">' +
                    '<div class="stock-code-dt">' + code + '</div>' +
                    '<div class="stock-name-dt">' + data.name + '</div>' +
                    '<div class="stock-market">🏢 ' + data.market_name + '</div>' +
                '</div>' +
                '<div class="stock-price-info">' +
                    '<div class="stock-price-dt">¥' + closePrice + '</div>' +
                    '<div class="stock-change-dt ' + changeClass + '">' + changeSign + changePercent.toFixed(2) + '%</div>' +
                '</div>' +
            '</div>' +
            '<div class="dragon-tiger-details">' +
                '<div class="detail-item">' +
                    '<span class="detail-label">上榜原因:</span>' +
                    '<span class="detail-value">' + (lhbInfo.list_reason || 'N/A') + '</span>' +
                '</div>' +
                '<div class="detail-item">' +
                    '<span class="detail-label">成交额:</span>' +
                    '<span class="detail-value">' + formatAmount(lhbInfo.amount) + '万元</span>' +
                '</div>' +
                '<div class="detail-item">' +
                    '<span class="detail-label">成交量:</span>' +
                    '<span class="detail-value">' + formatAmount(lhbInfo.volume) + '万股</span>' +
                '</div>' +
            '</div>' +
            capitalFlowHtml +
            '<div class="dragon-tiger-actions">' +
                '<button class="dt-btn primary" onclick="viewDragonTigerDetail(\'' + code + '\')">📖 查看详情</button>' +
                '<button class="dt-btn" onclick="copyStockData(\'' + code + '\')">📋 复制数据</button>' +
                '<button class="dt-btn" onclick="exportStockData(\'' + code + '\')">💾 导出</button>' +
            '</div>' +
        '</div>';
    }).join('');
    
    container.innerHTML = stocksHtml;
}

// 格式化金额
function formatAmount(amount) {
    if (!amount && amount !== 0) return '0.00';
    return parseFloat(amount).toFixed(2);
}

// 筛选股票
function filterDragonTigerStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const stockCards = document.querySelectorAll('.dragon-tiger-card');
    
    stockCards.forEach(card => {
        const code = card.dataset.code.toLowerCase();
        const name = card.dataset.name.toLowerCase();
        
        if (code.includes(searchTerm) || name.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// 复制龙虎榜数据
function copyDragonTigerData() {
    if (!currentDragonTigerData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    // 生成表格格式数据
    const successfulStocks = Object.entries(currentDragonTigerData.details).filter(([code, data]) => 
        data.status === 'success'
    );
    
    let textData = '股票代码\t股票名称\t市场\t收盘价\t涨跌幅\t上榜原因\t成交额(万元)\t成交量(万股)\t净流入(万元)\n';
    
    successfulStocks.forEach(([code, data]) => {
        const lhbInfo = data.lhb_info || {};
        const capitalFlow = data.capital_flow || {};
        
        textData += code + '\t';
        textData += data.name + '\t';
        textData += data.market_name + '\t';
        textData += (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '\t';
        textData += (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%\t';
        textData += (lhbInfo.list_reason || 'N/A') + '\t';
        textData += formatAmount(lhbInfo.amount) + '\t';
        textData += formatAmount(lhbInfo.volume) + '\t';
        textData += formatAmount(capitalFlow.net_inflow || 0) + '\n';
    });
    
    copyToClipboard(textData);
}

// 查看股票详情
function viewDragonTigerDetail(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    currentDetailStock = stockData;
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const detailContent = document.getElementById('detailContent');
    const modal = document.getElementById('detailModal');
    
    if (!modalTitle || !detailContent || !modal) {
        console.error('详情模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = stockCode + ' ' + stockData.name + ' - 龙虎榜详情';
    
    // 生成详情内容
    const detailHtml = generateDetailContent(stockData);
    detailContent.innerHTML = detailHtml;
    
    // 显示模态框
    modal.style.display = 'block';
}

// 生成详情内容
function generateDetailContent(stockData) {
    const lhbInfo = stockData.lhb_info || {};
    const capitalFlow = stockData.capital_flow || {};
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let html = '<div class="basic-info-section">' +
        '<h4>📊 基本信息</h4>' +
        '<div class="basic-info-grid">' +
            '<div class="info-pair"><span>交易日期:</span><span>' + stockData.query_date + '</span></div>' +
            '<div class="info-pair"><span>收盘价:</span><span>¥' + (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '</span></div>' +
            '<div class="info-pair"><span>涨跌幅:</span><span class="' + ((lhbInfo.change_percent || 0) >= 0 ? 'positive' : 'negative') + '">' +
                ((lhbInfo.change_percent || 0) >= 0 ? '+' : '') + (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%</span></div>' +
            '<div class="info-pair"><span>市场:</span><span>' + stockData.market_name + '</span></div>' +
            '<div class="info-pair"><span>上榜原因:</span><span>' + (lhbInfo.list_reason || 'N/A') + '</span></div>' +
            '<div class="info-pair"><span>成交额:</span><span>' + formatAmount(lhbInfo.amount) + '万元</span></div>' +
            '<div class="info-pair"><span>成交量:</span><span>' + formatAmount(lhbInfo.volume) + '万股</span></div>' +
        '</div>' +
    '</div>';
    
    // 资金流向
    if (capitalFlow.net_inflow !== undefined) {
        html += '<div class="capital-flow-summary">' +
            '<div class="flow-item"><span class="flow-label">💹 总买入</span><span class="flow-value">' + formatAmount(capitalFlow.buy_total) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">💸 总卖出</span><span class="flow-value">' + formatAmount(capitalFlow.sell_total) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">📈 净流入</span><span class="flow-value ' + (capitalFlow.net_inflow >= 0 ? 'positive' : 'negative') + '">' +
                (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">📊 净流入占比</span><span class="flow-value">' +
                ((capitalFlow.net_inflow / lhbInfo.amount) * 100).toFixed(1) + '%</span></div>' +
        '</div>';
    }
    
    // 买入席位
    if (buySeats.length > 0) {
        html += '<div class="seats-section">' +
            '<h4>🔴 买入席位 TOP' + Math.min(buySeats.length, 5) + '</h4>' +
            '<table class="seats-table">' +
                '<thead><tr><th>排名</th><th>营业部名称</th><th>买入金额(万元)</th><th>占比(%)</th><th>标签</th></tr></thead>' +
                '<tbody>';
        
        buySeats.slice(0, 5).forEach(seat => {
            html += '<tr>' +
                '<td class="seat-rank">' + seat.rank + '</td>' +
                '<td>' + seat.department_name + '</td>' +
                '<td class="seat-amount">' + formatAmount(seat.buy_amount) + '</td>' +
                '<td class="seat-amount">' + seat.amount_ratio + '%</td>' +
                '<td>' + (seat.label ? '<span class="seat-label ' + getSeatLabelClass(seat.label) + '">' + seat.label + '</span>' : '') + '</td>' +
            '</tr>';
        });
        
        html += '</tbody></table></div>';
    }
    
    // 卖出席位
    if (sellSeats.length > 0) {
        html += '<div class="seats-section">' +
            '<h4>🟢 卖出席位 TOP' + Math.min(sellSeats.length, 5) + '</h4>' +
            '<table class="seats-table">' +
                '<thead><tr><th>排名</th><th>营业部名称</th><th>卖出金额(万元)</th><th>占比(%)</th><th>标签</th></tr></thead>' +
                '<tbody>';
        
        sellSeats.slice(0, 5).forEach(seat => {
            html += '<tr>' +
                '<td class="seat-rank">' + seat.rank + '</td>' +
                '<td>' + seat.department_name + '</td>' +
                '<td class="seat-amount">' + formatAmount(seat.sell_amount) + '</td>' +
                '<td class="seat-amount">' + seat.amount_ratio + '%</td>' +
                '<td>' + (seat.label ? '<span class="seat-label ' + getSeatLabelClass(seat.label) + '">' + seat.label + '</span>' : '') + '</td>' +
            '</tr>';
        });
        
        html += '</tbody></table></div>';
    }
    
    return html;
}

// 获取席位标签样式类
function getSeatLabelClass(label) {
    if (label.includes('机构')) return 'institution';
    if (label.includes('游资')) return 'hot-money';
    return '';
}

// 关闭详情模态框
function closeDetailModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentDetailStock = null;
}

// 复制详情内容
function copyDetailContent(type) {
    if (!currentDetailStock) {
        showToast('未选择股票', 'error');
        return;
    }
    
    let content = '';
    
    switch (type) {
        case 'full':
            content = generateDetailTextContent(currentDetailStock);
            break;
        case 'seats':
            content = generateSeatsTextContent(currentDetailStock);
            break;
        default:
            content = generateDetailTextContent(currentDetailStock);
    }
    
    copyToClipboard(content);
}

// 生成详情文本内容
function generateDetailTextContent(stockData) {
    const lhbInfo = stockData.lhb_info || {};
    const capitalFlow = stockData.capital_flow || {};
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let content = stockData.code + ' ' + stockData.name + ' - 龙虎榜详情\n\n';
    content += '交易日期: ' + stockData.query_date + '\n';
    content += '收盘价: ¥' + (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '\n';
    content += '涨跌幅: ' + ((lhbInfo.change_percent || 0) >= 0 ? '+' : '') + (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%\n';
    content += '市场: ' + stockData.market_name + '\n';
    content += '上榜原因: ' + (lhbInfo.list_reason || 'N/A') + '\n';
    content += '成交额: ' + formatAmount(lhbInfo.amount) + '万元\n';
    content += '成交量: ' + formatAmount(lhbInfo.volume) + '万股\n\n';
    
    // 资金流向
    if (capitalFlow.net_inflow !== undefined) {
        content += '=== 资金流向 ===\n';
        content += '总买入: ' + formatAmount(capitalFlow.buy_total) + '万元\n';
        content += '总卖出: ' + formatAmount(capitalFlow.sell_total) + '万元\n';
        content += '净流入: ' + (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万元\n';
        content += '净流入占比: ' + ((capitalFlow.net_inflow / lhbInfo.amount) * 100).toFixed(1) + '%\n\n';
    }
    
    // 买入席位
    if (buySeats.length > 0) {
        content += '=== 买入席位 TOP5 ===\n';
        buySeats.slice(0, 5).forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\n';
            content += '   买入: ' + formatAmount(seat.buy_amount) + '万元  占比: ' + seat.amount_ratio + '%';
            if (seat.label) content += '  ' + seat.label;
            content += '\n';
        });
        content += '\n';
    }
    
    // 卖出席位
    if (sellSeats.length > 0) {
        content += '=== 卖出席位 TOP5 ===\n';
        sellSeats.slice(0, 5).forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\n';
            content += '   卖出: ' + formatAmount(seat.sell_amount) + '万元  占比: ' + seat.amount_ratio + '%';
            if (seat.label) content += '  ' + seat.label;
            content += '\n';
        });
    }
    
    return content;
}

// 生成席位文本内容
function generateSeatsTextContent(stockData) {
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let content = stockData.code + ' ' + stockData.name + ' - 席位信息\n\n';
    
    if (buySeats.length > 0) {
        content += '买入席位:\n';
        buySeats.forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\t' + formatAmount(seat.buy_amount) + '万元\t' + seat.amount_ratio + '%';
            if (seat.label) content += '\t' + seat.label;
            content += '\n';
        });
        content += '\n';
    }
    
    if (sellSeats.length > 0) {
        content += '卖出席位:\n';
        sellSeats.forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\t' + formatAmount(seat.sell_amount) + '万元\t' + seat.amount_ratio + '%';
            if (seat.label) content += '\t' + seat.label;
            content += '\n';
        });
    }
    
    return content;
}

// 下载详情
function downloadDetail() {
    if (!currentDetailStock) {
        showToast('未选择股票', 'error');
        return;
    }
    
    const content = generateDetailTextContent(currentDetailStock);
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '龙虎榜详情_' + currentDetailStock.code + '_' + currentDetailStock.name + '_' + currentDetailStock.query_date + '.txt';
    link.click();
    URL.revokeObjectURL(url);
    showToast('详情下载中...');
}

// 复制单只股票数据
function copyStockData(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    const content = generateDetailTextContent(stockData);
    copyToClipboard(content);
}

// 导出单只股票数据
function exportStockData(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    const content = generateDetailTextContent(stockData);
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '龙虎榜_' + stockCode + '_' + stockData.name + '_' + stockData.query_date + '.txt';
    link.click();
    URL.revokeObjectURL(url);
    showToast('数据导出中...');
}

// 查看JSON数据
function viewDragonTigerJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open('json_viewer.html?type=dragon_tiger&date=' + date, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 模态框外部点击关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('detailModal');
    if (modal && e.target === modal) {
        closeDetailModal();
    }
});

// 键盘事件
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('detailModal');
    if (modal && modal.style.display === 'block' && e.key === 'Escape') {
        closeDetailModal();
    }
});
