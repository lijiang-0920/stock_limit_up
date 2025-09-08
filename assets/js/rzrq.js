// assets/js/rzrq.js - 融资融券页面功能

let currentRzrqData = null;
let currentDetailData = null;

document.addEventListener('DOMContentLoaded', function() {
    initRzrqPage();
});

async function initRzrqPage() {
    await loadRzrqDateOptions();
    setupRzrqEventListeners();
}

// 加载日期选项
async function loadRzrqDateOptions() {
    try {
        const response = await fetch('tdx_rztq/index.json');
        if (!response.ok) throw new Error('无法加载融资融券日期数据');
        
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
            await loadRzrqData(dates[0]);
        }
    } catch (error) {
        console.error('加载融资融券日期选项失败:', error);
        const industryTableBody = document.getElementById('industryTableBody');
        const stockTableBody = document.getElementById('stockTableBody');
        if (industryTableBody) {
            industryTableBody.innerHTML = '<tr><td colspan="11" class="loading">加载日期数据失败</td></tr>';
        }
        if (stockTableBody) {
            stockTableBody.innerHTML = '<tr><td colspan="16" class="loading">加载日期数据失败</td></tr>';
        }
    }
}

// 设置事件监听器
function setupRzrqEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const marketFilter = document.getElementById('marketFilter');
    const industrySearchInput = document.getElementById('industrySearchInput');
    const industrySortSelect = document.getElementById('industrySortSelect');
    const stockSortSelect = document.getElementById('stockSortSelect');
    const marketTabs = document.querySelectorAll('.market-tab');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadRzrqData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterStocks, 300));
    }
    
    if (marketFilter) {
        marketFilter.addEventListener('change', filterStocks);
    }
    
    if (industrySearchInput) {
        industrySearchInput.addEventListener('input', debounce(filterIndustries, 300));
    }
    
    if (industrySortSelect) {
        industrySortSelect.addEventListener('change', sortIndustries);
    }
    
    if (stockSortSelect) {
        stockSortSelect.addEventListener('change', sortStocks);
    }
    
    marketTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            // 移除所有active类
            marketTabs.forEach(t => t.classList.remove('active'));
            // 添加active类到当前tab
            e.target.classList.add('active');
            // 过滤股票
            filterStocks();
        });
    });
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyRzrqData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewRzrqJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载融资融券数据
async function loadRzrqData(date) {
    const industryTableBody = document.getElementById('industryTableBody');
    const stockTableBody = document.getElementById('stockTableBody');
    const dataInfo = document.getElementById('dataInfo');
    const marketOverview = document.getElementById('marketOverview');
    const industrySection = document.getElementById('industrySection');
    const stockSection = document.getElementById('stockSection');
    
    if (!industryTableBody || !stockTableBody) {
        console.error('表格元素未找到');
        return;
    }
    
    industryTableBody.innerHTML = '<tr><td colspan="11" class="loading">加载中...</td></tr>';
    stockTableBody.innerHTML = '<tr><td colspan="16" class="loading">加载中...</td></tr>';
    
    // 隐藏所有区域
    [dataInfo, marketOverview, industrySection, stockSection].forEach(el => {
        if (el) el.style.display = 'none';
    });
    
    try {
        // 构建文件路径
        const yearMonth = date.substring(0, 7);
        const response = await fetch(`tdx_rztq/${yearMonth}/${date}.json`);
        if (!response.ok) throw new Error('融资融券数据加载失败');
        
        currentRzrqData = await response.json();
        
        // 更新数据信息
        updateDataInfo(currentRzrqData);
        
        // 渲染市场总览
        renderMarketOverview(currentRzrqData.market_data);
        
        // 渲染行业数据
        renderIndustryData(currentRzrqData.industry_data);
        
        // 渲染个股数据
        renderStockData(currentRzrqData.stock_data);
        
        // 显示所有区域
        [dataInfo, marketOverview, industrySection, stockSection].forEach(el => {
            if (el) el.style.display = 'block';
        });
        
    } catch (error) {
        console.error('加载融资融券数据失败:', error);
        industryTableBody.innerHTML = '<tr><td colspan="11" class="loading">加载数据失败</td></tr>';
        stockTableBody.innerHTML = '<tr><td colspan="16" class="loading">加载数据失败</td></tr>';
    }
}

// 更新数据信息
function updateDataInfo(data) {
    const updateTimeEl = document.getElementById('updateTime');
    const industryCountEl = document.getElementById('industryCount');
    const stockCountEl = document.getElementById('stockCount');
    const dataStatusEl = document.getElementById('dataStatus');
    
    if (updateTimeEl) {
        updateTimeEl.textContent = data.update_time || '--';
    }
    if (industryCountEl) {
        industryCountEl.textContent = data.industry_data.length + '个';
    }
    if (stockCountEl) {
        const totalStocks = Object.values(data.stock_data).reduce((sum, stocks) => sum + stocks.length, 0);
        stockCountEl.textContent = totalStocks + '只';
    }
    if (dataStatusEl) {
        const status = data.data_status;
        const statusText = [];
        if (status.market_data) statusText.push('✅市场');
        if (status.industry_data) statusText.push('✅行业');
        if (status.stock_data) statusText.push('✅个股');
        dataStatusEl.innerHTML = statusText.join(' ') || '❌无数据';
        dataStatusEl.className = 'status-text';
    }
}

// 渲染市场总览
function renderMarketOverview(marketData) {
    const marketStatsGrid = document.getElementById('marketStatsGrid');
    if (!marketStatsGrid || !marketData) return;
    
    // 计算合计
    let totalBalance = 0;
    let totalBuy = 0;
    let totalShort = 0;
    let totalTotal = 0;
    
    const marketCards = [];
    
    Object.entries(marketData).forEach(([market, data]) => {
        const balance = typeof data.融资余额 === 'number' ? data.融资余额 : 0;
        const buy = typeof data.融资买入额 === 'number' ? data.融资买入额 : 0;
        const short = typeof data.融券余量金额 === 'number' ? data.融券余量金额 : 0;
        const total = typeof data.融资融券余额 === 'number' ? data.融资融券余额 : 0;
        
        totalBalance += balance;
        totalBuy += buy;
        totalShort += short;
        totalTotal += total;
        
        marketCards.push(`
            <div class="market-card">
                <div class="market-name">${market}</div>
                <div class="market-value">${formatAmount(balance)}</div>
                <div class="market-label">融资余额(亿元)</div>
                <div class="market-details">
                    <div>买入: ${formatAmount(buy)}亿</div>
                    <div>融券: ${formatAmount(short)}亿</div>
                    <div>总额: ${formatAmount(total)}亿</div>
                </div>
            </div>
        `);
    });
    
    // 添加合计卡片
    marketCards.push(`
        <div class="market-card total-card">
            <div class="market-name">合计</div>
            <div class="market-value">${formatAmount(totalBalance)}</div>
            <div class="market-label">融资余额(亿元)</div>
            <div class="market-details">
                <div>买入: ${formatAmount(totalBuy)}亿</div>
                <div>融券: ${formatAmount(totalShort)}亿</div>
                <div>总额: ${formatAmount(totalTotal)}亿</div>
            </div>
        </div>
    `);
    
    marketStatsGrid.innerHTML = marketCards.join('');
}

// 渲染行业数据为表格
function renderIndustryData(industryData) {
    const tableBody = document.getElementById('industryTableBody');
    if (!tableBody || !industryData || industryData.length === 0) {
        if (tableBody) {
            tableBody.innerHTML = '<tr><td colspan="11" class="loading">暂无行业数据</td></tr>';
        }
        return;
    }
    
    const industryHtml = industryData.map((industry, index) => `
        <tr class="industry-row" data-name="${industry.行业名称}">
            <td class="rank-cell">${index + 1}</td>
            <td class="industry-name-cell">${industry.行业名称}</td>
            <td class="amount-cell">${formatAmount(industry['融资余额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融资买入额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融资偿还额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券余额(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券余量(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券卖出量(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券偿还量(万)'])}</td>
            <td class="amount-cell ${industry['融资融券差值(亿)'] >= 0 ? 'positive' : 'negative'}">
                ${industry['融资融券差值(亿)'] >= 0 ? '+' : ''}${formatAmount(industry['融资融券差值(亿)'])}
            </td>
            <td class="actions-cell">
                <button onclick="viewIndustryDetail('${industry.行业名称}')" class="action-btn-sm">📖 详情</button>
                <button onclick="copyIndustryData('${industry.行业名称}')" class="action-btn-sm">📋 复制</button>
            </td>
        </tr>
    `).join('');
    
    tableBody.innerHTML = industryHtml;
}

// 渲染个股数据为表格
function renderStockData(stockData) {
    const tableBody = document.getElementById('stockTableBody');
    if (!tableBody || !stockData) {
        if (tableBody) {
            tableBody.innerHTML = '<tr><td colspan="16" class="loading">暂无个股数据</td></tr>';
        }
        return;
    }
    
    // 合并所有市场的股票数据
    const allStocks = [];
    Object.entries(stockData).forEach(([market, stocks]) => {
        stocks.forEach(stock => {
            allStocks.push({...stock, market: market});
        });
    });
    
    if (allStocks.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="16" class="loading">暂无个股数据</td></tr>';
        return;
    }
    
    const stockHtml = allStocks.map(stock => `
        <tr class="stock-row" data-code="${stock.股票代码}" data-name="${stock.股票名称}" data-market="${stock.market}">
            <td class="code-cell">${stock.股票代码}</td>
            <td class="name-cell">${stock.股票名称}</td>
            <td class="market-cell">${stock.market}</td>
            <td class="amount-cell">${formatAmount(stock['融资余额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融资买入额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融资偿还额(万元)'])}</td>
            <td class="amount-cell ${stock['融资净买入(万元)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融资净买入(万元)'] >= 0 ? '+' : ''}${formatAmount(stock['融资净买入(万元)'])}
            </td>
            <td class="percent-cell">${formatAmount(stock['融资占流通市值比(%)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券余额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券余量(万股)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券卖出量(万股)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券偿还量(万股)'])}</td>
            <td class="amount-cell ${stock['融券净卖出(万股)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融券净卖出(万股)'] >= 0 ? '+' : ''}${formatAmount(stock['融券净卖出(万股)'])}
            <td class="percent-cell">${formatAmount(stock['融券占流通市值比(%)'])}</td>
            <td class="amount-cell ${stock['融资融券差值(万元)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融资融券差值(万元)'] >= 0 ? '+' : ''}${formatAmount(stock['融资融券差值(万元)'])}
            </td>
            <td class="actions-cell">
                <button onclick="viewStockDetail('${stock.股票代码}')" class="action-btn-sm primary">📖 详情</button>
                <button onclick="copyStockData('${stock.股票代码}')" class="action-btn-sm">📋 复制</button>
            </td>
        </tr>
    `).join('');
    
    tableBody.innerHTML = stockHtml;
}

// 格式化金额
function formatAmount(amount) {
    if (!amount && amount !== 0) return '0.00';
    if (typeof amount === 'string') return amount;
    return parseFloat(amount).toFixed(2);
}

// 筛选行业
function filterIndustries() {
    const searchInput = document.getElementById('industrySearchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const industryRows = document.querySelectorAll('.industry-row');
    
    industryRows.forEach(row => {
        const name = row.dataset.name.toLowerCase();
        
        if (name.includes(searchTerm)) {
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
}

// 筛选股票
function filterStocks() {
    const searchInput = document.getElementById('searchInput');
    const marketFilter = document.getElementById('marketFilter');
    const activeTab = document.querySelector('.market-tab.active');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const marketValue = marketFilter ? marketFilter.value : '';
    const tabMarket = activeTab ? activeTab.dataset.market : 'all';
    
    const stockRows = document.querySelectorAll('.stock-row');
    
    stockRows.forEach(row => {
        const code = row.dataset.code.toLowerCase();
        const name = row.dataset.name.toLowerCase();
        const market = row.dataset.market;
        
        const matchesSearch = !searchTerm || code.includes(searchTerm) || name.includes(searchTerm);
        const matchesMarketFilter = !marketValue || market === marketValue;
        const matchesTab = tabMarket === 'all' || market === tabMarket;
        
        if (matchesSearch && matchesMarketFilter && matchesTab) {
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
}

// 排序行业
function sortIndustries() {
    const sortSelect = document.getElementById('industrySortSelect');
    const tableBody = document.getElementById('industryTableBody');
    
    if (!sortSelect || !tableBody || !currentRzrqData) return;
    
    const sortKey = sortSelect.value;
    const industryData = [...currentRzrqData.industry_data];
    
    if (sortKey === '行业名称') {
        industryData.sort((a, b) => a.行业名称.localeCompare(b.行业名称));
    } else {
        industryData.sort((a, b) => {
            const aVal = parseFloat(a[sortKey]) || 0;
            const bVal = parseFloat(b[sortKey]) || 0;
            return bVal - aVal; // 降序
        });
    }
    
    renderIndustryDataSorted(industryData);
}

// 排序股票
function sortStocks() {
    const sortSelect = document.getElementById('stockSortSelect');
    const tableBody = document.getElementById('stockTableBody');
    
    if (!sortSelect || !tableBody || !currentRzrqData) return;
    
    const sortKey = sortSelect.value;
    
    // 合并所有市场的股票数据
    const allStocks = [];
    Object.entries(currentRzrqData.stock_data).forEach(([market, stocks]) => {
        stocks.forEach(stock => {
            allStocks.push({...stock, market: market});
        });
    });
    
    // 排序
    allStocks.sort((a, b) => {
        const aVal = parseFloat(a[sortKey]) || 0;
        const bVal = parseFloat(b[sortKey]) || 0;
        return bVal - aVal; // 降序
    });
    
    renderStockDataSorted(allStocks);
}

// 渲染排序后的行业数据
function renderIndustryDataSorted(industryData) {
    const tableBody = document.getElementById('industryTableBody');
    if (!tableBody) return;
    
    const industryHtml = industryData.map((industry, index) => `
        <tr class="industry-row" data-name="${industry.行业名称}">
            <td class="rank-cell">${index + 1}</td>
            <td class="industry-name-cell">${industry.行业名称}</td>
            <td class="amount-cell">${formatAmount(industry['融资余额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融资买入额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融资偿还额(亿)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券余额(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券余量(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券卖出量(万)'])}</td>
            <td class="amount-cell">${formatAmount(industry['融券偿还量(万)'])}</td>
            <td class="amount-cell ${industry['融资融券差值(亿)'] >= 0 ? 'positive' : 'negative'}">
                ${industry['融资融券差值(亿)'] >= 0 ? '+' : ''}${formatAmount(industry['融资融券差值(亿)'])}
            </td>
            <td class="actions-cell">
                <button onclick="viewIndustryDetail('${industry.行业名称}')" class="action-btn-sm">📖 详情</button>
                <button onclick="copyIndustryData('${industry.行业名称}')" class="action-btn-sm">📋 复制</button>
            </td>
        </tr>
    `).join('');
    
    tableBody.innerHTML = industryHtml;
}

// 渲染排序后的股票数据
function renderStockDataSorted(stockData) {
    const tableBody = document.getElementById('stockTableBody');
    if (!tableBody) return;
    
    const stockHtml = stockData.map(stock => `
        <tr class="stock-row" data-code="${stock.股票代码}" data-name="${stock.股票名称}" data-market="${stock.market}">
            <td class="code-cell">${stock.股票代码}</td>
            <td class="name-cell">${stock.股票名称}</td>
            <td class="market-cell">${stock.market}</td>
            <td class="amount-cell">${formatAmount(stock['融资余额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融资买入额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融资偿还额(万元)'])}</td>
            <td class="amount-cell ${stock['融资净买入(万元)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融资净买入(万元)'] >= 0 ? '+' : ''}${formatAmount(stock['融资净买入(万元)'])}
            </td>
            <td class="percent-cell">${formatAmount(stock['融资占流通市值比(%)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券余额(万元)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券余量(万股)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券卖出量(万股)'])}</td>
            <td class="amount-cell">${formatAmount(stock['融券偿还量(万股)'])}</td>
            <td class="amount-cell ${stock['融券净卖出(万股)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融券净卖出(万股)'] >= 0 ? '+' : ''}${formatAmount(stock['融券净卖出(万股)'])}
            </td>
            <td class="percent-cell">${formatAmount(stock['融券占流通市值比(%)'])}</td>
            <td class="amount-cell ${stock['融资融券差值(万元)'] >= 0 ? 'positive' : 'negative'}">
                ${stock['融资融券差值(万元)'] >= 0 ? '+' : ''}${formatAmount(stock['融资融券差值(万元)'])}
            </td>
            <td class="actions-cell">
                <button onclick="viewStockDetail('${stock.股票代码}')" class="action-btn-sm primary">📖 详情</button>
                <button onclick="copyStockData('${stock.股票代码}')" class="action-btn-sm">📋 复制</button>
            </td>
        </tr>
    `).join('');
    
    tableBody.innerHTML = stockHtml;
}

// 查看股票详情
function viewStockDetail(stockCode) {
    if (!currentRzrqData) {
        showToast('数据未加载', 'error');
        return;
    }
    
    // 查找股票数据
    let stockData = null;
    let market = '';
    
    Object.entries(currentRzrqData.stock_data).forEach(([marketName, stocks]) => {
        const found = stocks.find(stock => stock.股票代码 === stockCode);
        if (found) {
            stockData = found;
            market = marketName;
        }
    });
    
    if (!stockData) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    currentDetailData = {type: 'stock', data: stockData, market: market};
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const detailContent = document.getElementById('detailContent');
    const modal = document.getElementById('detailModal');
    
    if (!modalTitle || !detailContent || !modal) {
        console.error('详情模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = `${stockCode} ${stockData.股票名称} - 融资融券详情`;
    
    // 生成详情内容
    const detailHtml = generateStockDetailContent(stockData, market);
    detailContent.innerHTML = detailHtml;
    
    // 显示模态框
    modal.style.display = 'block';
}

// 生成股票详情内容
function generateStockDetailContent(stockData, market) {
    return `
        <div class="detail-section">
            <h4>📊 基本信息</h4>
            <div class="detail-info-grid">
                <div class="info-pair"><span>股票代码:</span><span>${stockData.股票代码}</span></div>
                <div class="info-pair"><span>股票名称:</span><span>${stockData.股票名称}</span></div>
                <div class="info-pair"><span>所属市场:</span><span>${market}</span></div>
                <div class="info-pair"><span>交易日期:</span><span>${currentRzrqData.date}</span></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>💰 融资数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融资余额:</span>
                    <span class="highlight">${formatAmount(stockData['融资余额(万元)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融资买入额:</span>
                    <span>${formatAmount(stockData['融资买入额(万元)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融资偿还额:</span>
                    <span>${formatAmount(stockData['融资偿还额(万元)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融资净买入:</span>
                    <span class="${stockData['融资净买入(万元)'] >= 0 ? 'positive' : 'negative'}">
                        ${stockData['融资净买入(万元)'] >= 0 ? '+' : ''}${formatAmount(stockData['融资净买入(万元)'])}万元
                    </span>
                </div>
                <div class="info-pair">
                    <span>融资占流通市值比:</span>
                    <span>${formatAmount(stockData['融资占流通市值比(%)'])}%</span>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>📊 融券数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融券余额:</span>
                    <span class="highlight">${formatAmount(stockData['融券余额(万元)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融券余量:</span>
                    <span>${formatAmount(stockData['融券余量(万股)'])}万股</span>
                </div>
                <div class="info-pair">
                    <span>融券卖出量:</span>
                    <span>${formatAmount(stockData['融券卖出量(万股)'])}万股</span>
                </div>
                <div class="info-pair">
                    <span>融券偿还量:</span>
                    <span>${formatAmount(stockData['融券偿还量(万股)'])}万股</span>
                </div>
                <div class="info-pair">
                    <span>融券净卖出:</span>
                    <span class="${stockData['融券净卖出(万股)'] >= 0 ? 'positive' : 'negative'}">
                        ${stockData['融券净卖出(万股)'] >= 0 ? '+' : ''}${formatAmount(stockData['融券净卖出(万股)'])}万股
                    </span>
                </div>
                <div class="info-pair">
                    <span>融券占流通市值比:</span>
                    <span>${formatAmount(stockData['融券占流通市值比(%)'])}%</span>
                <div class="info-pair">
                    <span>融券占流通市值比:</span>
                    <span>${formatAmount(stockData['融券占流通市值比(%)'])}%</span>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>⚖️ 综合数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融资融券差值:</span>
                    <span class="${stockData['融资融券差值(万元)'] >= 0 ? 'positive' : 'negative'}">
                        ${stockData['融资融券差值(万元)'] >= 0 ? '+' : ''}${formatAmount(stockData['融资融券差值(万元)'])}万元
                    </span>
                </div>
            </div>
        </div>
    `;
}

// 查看行业详情
function viewIndustryDetail(industryName) {
    if (!currentRzrqData) {
        showToast('数据未加载', 'error');
        return;
    }
    
    const industryData = currentRzrqData.industry_data.find(industry => industry.行业名称 === industryName);
    if (!industryData) {
        showToast('行业数据未找到', 'error');
        return;
    }
    
    currentDetailData = {type: 'industry', data: industryData};
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const detailContent = document.getElementById('detailContent');
    const modal = document.getElementById('detailModal');
    
    if (!modalTitle || !detailContent || !modal) {
        console.error('详情模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = `${industryName} - 行业融资融券详情`;
    
    // 生成详情内容
    const detailHtml = generateIndustryDetailContent(industryData);
    detailContent.innerHTML = detailHtml;
    
    // 显示模态框
    modal.style.display = 'block';
}

// 生成行业详情内容
function generateIndustryDetailContent(industryData) {
    return `
        <div class="detail-section">
            <h4>🏭 行业信息</h4>
            <div class="detail-info-grid">
                <div class="info-pair"><span>行业名称:</span><span>${industryData.行业名称}</span></div>
                <div class="info-pair"><span>交易日期:</span><span>${currentRzrqData.date}</span></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>💰 融资数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融资余额:</span>
                    <span class="highlight">${formatAmount(industryData['融资余额(亿)'])}亿元</span>
                </div>
                <div class="info-pair">
                    <span>融资买入额:</span>
                    <span>${formatAmount(industryData['融资买入额(亿)'])}亿元</span>
                </div>
                <div class="info-pair">
                    <span>融资偿还额:</span>
                    <span>${formatAmount(industryData['融资偿还额(亿)'])}亿元</span>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>📊 融券数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融券余额:</span>
                    <span>${formatAmount(industryData['融券余额(万)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融券余量:</span>
                    <span>${formatAmount(industryData['融券余量(万)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融券卖出量:</span>
                    <span>${formatAmount(industryData['融券卖出量(万)'])}万元</span>
                </div>
                <div class="info-pair">
                    <span>融券偿还量:</span>
                    <span>${formatAmount(industryData['融券偿还量(万)'])}万元</span>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h4>⚖️ 综合数据</h4>
            <div class="detail-info-grid">
                <div class="info-pair">
                    <span>融资融券差值:</span>
                    <span class="${industryData['融资融券差值(亿)'] >= 0 ? 'positive' : 'negative'}">
                        ${industryData['融资融券差值(亿)'] >= 0 ? '+' : ''}${formatAmount(industryData['融资融券差值(亿)'])}亿元
                    </span>
                </div>
            </div>
        </div>
    `;
}

// 关闭详情模态框
function closeDetailModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentDetailData = null;
}

// 复制详情内容
function copyDetailContent(type) {
    if (!currentDetailData) {
        showToast('未选择数据', 'error');
        return;
    }
    
    let content = '';
    
    if (currentDetailData.type === 'stock') {
        switch (type) {
            case 'full':
                content = generateStockTextContent(currentDetailData.data, currentDetailData.market);
                break;
            case 'basic':
                content = generateBasicStockTextContent(currentDetailData.data);
                break;
            default:
                content = generateStockTextContent(currentDetailData.data, currentDetailData.market);
        }
    } else if (currentDetailData.type === 'industry') {
        switch (type) {
            case 'full':
                content = generateIndustryTextContent(currentDetailData.data);
                break;
            case 'basic':
                content = generateBasicIndustryTextContent(currentDetailData.data);
                break;
            default:
                content = generateIndustryTextContent(currentDetailData.data);
        }
    }
    
    copyToClipboard(content);
}

// 生成股票文本内容
function generateStockTextContent(stockData, market) {
    let content = `${stockData.股票代码} ${stockData.股票名称} - 融资融券详情\n\n`;
    content += `所属市场: ${market}\n`;
    content += `交易日期: ${currentRzrqData.date}\n\n`;
    
    content += `=== 融资数据 ===\n`;
    content += `融资余额: ${formatAmount(stockData['融资余额(万元)'])}万元\n`;
    content += `融资买入额: ${formatAmount(stockData['融资买入额(万元)'])}万元\n`;
    content += `融资偿还额: ${formatAmount(stockData['融资偿还额(万元)'])}万元\n`;
    content += `融资净买入: ${stockData['融资净买入(万元)'] >= 0 ? '+' : ''}${formatAmount(stockData['融资净买入(万元)'])}万元\n`;
    content += `融资占流通市值比: ${formatAmount(stockData['融资占流通市值比(%)'])}%\n\n`;
    
    content += `=== 融券数据 ===\n`;
    content += `融券余额: ${formatAmount(stockData['融券余额(万元)'])}万元\n`;
    content += `融券余量: ${formatAmount(stockData['融券余量(万股)'])}万股\n`;
    content += `融券卖出量: ${formatAmount(stockData['融券卖出量(万股)'])}万股\n`;
    content += `融券偿还量: ${formatAmount(stockData['融券偿还量(万股)'])}万股\n`;
    content += `融券净卖出: ${stockData['融券净卖出(万股)'] >= 0 ? '+' : ''}${formatAmount(stockData['融券净卖出(万股)'])}万股\n`;
    content += `融券占流通市值比: ${formatAmount(stockData['融券占流通市值比(%)'])}%\n\n`;
    
    content += `=== 综合数据 ===\n`;
    content += `融资融券差值: ${stockData['融资融券差值(万元)'] >= 0 ? '+' : ''}${formatAmount(stockData['融资融券差值(万元)'])}万元\n`;
    
    return content;
}

// 生成基本股票文本内容
function generateBasicStockTextContent(stockData) {
    return `${stockData.股票代码} ${stockData.股票名称}\n` +
           `融资余额: ${formatAmount(stockData['融资余额(万元)'])}万元\n` +
           `融资净买入: ${stockData['融资净买入(万元)'] >= 0 ? '+' : ''}${formatAmount(stockData['融资净买入(万元)'])}万元\n` +
           `融券余量: ${formatAmount(stockData['融券余量(万股)'])}万股\n` +
           `融券净卖出: ${stockData['融券净卖出(万股)'] >= 0 ? '+' : ''}${formatAmount(stockData['融券净卖出(万股)'])}万股`;
}

// 生成行业文本内容
function generateIndustryTextContent(industryData) {
    let content = `${industryData.行业名称} - 行业融资融券详情\n\n`;
    content += `交易日期: ${currentRzrqData.date}\n\n`;
    
    content += `=== 融资数据 ===\n`;
    content += `融资余额: ${formatAmount(industryData['融资余额(亿)'])}亿元\n`;
    content += `融资买入额: ${formatAmount(industryData['融资买入额(亿)'])}亿元\n`;
    content += `融资偿还额: ${formatAmount(industryData['融资偿还额(亿)'])}亿元\n\n`;
    
    content += `=== 融券数据 ===\n`;
    content += `融券余额: ${formatAmount(industryData['融券余额(万)'])}万元\n`;
    content += `融券余量: ${formatAmount(industryData['融券余量(万)'])}万元\n`;
    content += `融券卖出量: ${formatAmount(industryData['融券卖出量(万)'])}万元\n`;
    content += `融券偿还量: ${formatAmount(industryData['融券偿还量(万)'])}万元\n\n`;
    
    content += `=== 综合数据 ===\n`;
    content += `融资融券差值: ${industryData['融资融券差值(亿)'] >= 0 ? '+' : ''}${formatAmount(industryData['融资融券差值(亿)'])}亿元\n`;
    
    return content;
}

// 生成基本行业文本内容
function generateBasicIndustryTextContent(industryData) {
    return `${industryData.行业名称}\n` +
           `融资余额: ${formatAmount(industryData['融资余额(亿)'])}亿元\n` +
           `融资买入额: ${formatAmount(industryData['融资买入额(亿)'])}亿元\n` +
           `融券余额: ${formatAmount(industryData['融券余额(万)'])}万元\n` +
           `融资融券差值: ${industryData['融资融券差值(亿)'] >= 0 ? '+' : ''}${formatAmount(industryData['融资融券差值(亿)'])}亿元`;
}

// 下载详情
function downloadDetail() {
    if (!currentDetailData) {
        showToast('未选择数据', 'error');
        return;
    }
    
    let content = '';
    let filename = '';
    
    if (currentDetailData.type === 'stock') {
        content = generateStockTextContent(currentDetailData.data, currentDetailData.market);
        filename = `融资融券详情_${currentDetailData.data.股票代码}_${currentDetailData.data.股票名称}_${currentRzrqData.date}.txt`;
    } else if (currentDetailData.type === 'industry') {
        content = generateIndustryTextContent(currentDetailData.data);
        filename = `融资融券详情_${currentDetailData.data.行业名称}_${currentRzrqData.date}.txt`;
    }
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    showToast('详情下载中...');
}

// 复制单个股票数据
function copyStockData(stockCode) {
    if (!currentRzrqData) {
        showToast('数据未加载', 'error');
        return;
    }
    
    let stockData = null;
    let market = '';
    
    Object.entries(currentRzrqData.stock_data).forEach(([marketName, stocks]) => {
        const found = stocks.find(stock => stock.股票代码 === stockCode);
        if (found) {
            stockData = found;
            market = marketName;
        }
    });
    
    if (!stockData) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const content = generateBasicStockTextContent(stockData);
    copyToClipboard(content);
}

// 复制单个行业数据
function copyIndustryData(industryName) {
    if (!currentRzrqData) {
        showToast('数据未加载', 'error');
        return;
    }
    
    const industryData = currentRzrqData.industry_data.find(industry => industry.行业名称 === industryName);
    if (!industryData) {
        showToast('行业数据未找到', 'error');
        return;
    }
    
    const content = generateBasicIndustryTextContent(industryData);
    copyToClipboard(content);
}

// 复制融资融券数据
function copyRzrqData() {
    if (!currentRzrqData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    // 生成表格格式数据
    let textData = `融资融券数据汇总 - ${currentRzrqData.date}\n\n`;
    
    // 市场数据
    textData += '=== 市场数据 ===\n';
    textData += '市场\t融资余额(亿)\t融资买入额(亿)\t融券余量金额(亿)\t融资融券余额(亿)\n';
    
    Object.entries(currentRzrqData.market_data).forEach(([market, data]) => {
        textData += `${market}\t`;
        textData += `${formatAmount(data.融资余额)}\t`;
        textData += `${formatAmount(data.融资买入额)}\t`;
        textData += `${formatAmount(data.融券余量金额)}\t`;
        textData += `${formatAmount(data.融资融券余额)}\n`;
    });
    
    // 行业数据
    textData += '\n=== 行业数据 ===\n';
    textData += '排名\t行业名称\t融资余额(亿)\t融资买入额(亿)\t融资偿还额(亿)\t融券余额(万)\t融券余量(万)\t融券卖出量(万)\t融券偿还量(万)\t融资融券差值(亿)\n';
    
    currentRzrqData.industry_data.forEach((industry, index) => {
        textData += `${index + 1}\t`;
        textData += `${industry.行业名称}\t`;
        textData += `${formatAmount(industry['融资余额(亿)'])}\t`;
        textData += `${formatAmount(industry['融资买入额(亿)'])}\t`;
        textData += `${formatAmount(industry['融资偿还额(亿)'])}\t`;
        textData += `${formatAmount(industry['融券余额(万)'])}\t`;
        textData += `${formatAmount(industry['融券余量(万)'])}\t`;
        textData += `${formatAmount(industry['融券卖出量(万)'])}\t`;
        textData += `${formatAmount(industry['融券偿还量(万)'])}\t`;
        textData += `${formatAmount(industry['融资融券差值(亿)'])}\n`;
    });
    
    // 个股数据（全部数据，按融资余额排序）
    const allStocks = [];
    Object.entries(currentRzrqData.stock_data).forEach(([market, stocks]) => {
        stocks.forEach(stock => {
            allStocks.push({...stock, market: market});
        });
    });
    
    // 移除 .slice(0, 20) 限制，显示所有数据
    const sortedStocks = allStocks.sort((a, b) => (b['融资余额(万元)'] || 0) - (a['融资余额(万元)'] || 0));
    
    textData += `\n=== 个股数据（共${sortedStocks.length}只） ===\n`;
    textData += '股票代码\t股票名称\t市场\t融资余额(万元)\t融资买入额(万元)\t融资净买入(万元)\t融券余量(万股)\t融券净卖出(万股)\t融资融券差值(万元)\n';
    
    sortedStocks.forEach(stock => {
        textData += `${stock.股票代码}\t`;
        textData += `${stock.股票名称}\t`;
        textData += `${stock.market}\t`;
        textData += `${formatAmount(stock['融资余额(万元)'])}\t`;
        textData += `${formatAmount(stock['融资买入额(万元)'])}\t`;
        textData += `${formatAmount(stock['融资净买入(万元)'])}\t`;
        textData += `${formatAmount(stock['融券余量(万股)'])}\t`;
        textData += `${formatAmount(stock['融券净卖出(万股)'])}\t`;
        textData += `${formatAmount(stock['融资融券差值(万元)'])}\n`;
    });
    
    copyToClipboard(textData);
}

// 查看JSON数据
function viewRzrqJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open(`json_viewer.html?type=rzrq&date=${date}`, '_blank');
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
