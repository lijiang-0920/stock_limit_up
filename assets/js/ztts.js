// assets/js/ztts.js - 涨停透视页面功能

let currentZTTSData = null;

document.addEventListener('DOMContentLoaded', function() {
    initZTTSPage();
});

async function initZTTSPage() {
    await loadZTTSDateOptions();
    setupZTTSEventListeners();
}

// 加载日期选项
async function loadZTTSDateOptions() {
    try {
        const response = await fetch('dzh_ztts/index.json');
        if (!response.ok) throw new Error('无法加载涨停透视日期数据');
        
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
            await loadZTTSData(dates[0]);
        }
    } catch (error) {
        console.error('加载涨停透视日期选项失败:', error);
        const container = document.getElementById('zttsContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupZTTSEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadZTTSData(e.target.value);
            }
        });
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyZTTSData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewZTTSJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载涨停透视数据
async function loadZTTSData(date) {
    const container = document.getElementById('zttsContainer');
    const dataInfo = document.getElementById('dataInfo');
    const coreIndicators = document.getElementById('coreIndicators');
    const marketAnalysis = document.getElementById('marketAnalysis');
    const ladderDistribution = document.getElementById('ladderDistribution');
    const comparisonTable = document.getElementById('comparisonTable');
    const boardStatistics = document.getElementById('boardStatistics');
    
    if (!container) {
        console.error('zttsContainer元素未找到');
        return;
    }
    
    showLoading(container);
    
    // 隐藏所有数据区域
    [dataInfo, coreIndicators, marketAnalysis, ladderDistribution, comparisonTable, boardStatistics].forEach(el => {
        if (el) el.style.display = 'none';
    });
    
    try {
        // 构建文件路径
        const yearMonth = date.substring(0, 7); // 2025-01
        const response = await fetch(`dzh_ztts/${yearMonth}/${date}.json`);
        if (!response.ok) throw new Error('涨停透视数据加载失败');
        
        currentZTTSData = await response.json();
        
        // 更新数据信息
        updateDataInfo(currentZTTSData);
        
        // 更新核心指标
        updateCoreIndicators(currentZTTSData);
        
        // 更新市场分析
        updateMarketAnalysis(currentZTTSData);
        
        // 更新涨停梯队（暂时显示占位符）
        updateLadderDistribution(currentZTTSData);
        
        // 更新对比表格
        updateComparisonTable(currentZTTSData);
        
        // 更新连板统计
        updateBoardStatistics(currentZTTSData);
        
        // 显示所有数据区域
        [dataInfo, coreIndicators, marketAnalysis, ladderDistribution, comparisonTable, boardStatistics].forEach(el => {
            if (el) el.style.display = 'block';
        });
        
        container.innerHTML = '<div class="success-message">✅ 数据加载完成</div>';
        
    } catch (error) {
        console.error('加载涨停透视数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 更新数据信息
function updateDataInfo(data) {
    const dataDateEl = document.getElementById('dataDate');
    const updateTimeEl = document.getElementById('updateTime');
    
    if (dataDateEl && data.报告信息) {
        dataDateEl.textContent = data.报告信息.数据日期 || '--';
    }
    if (updateTimeEl && data.报告信息) {
        updateTimeEl.textContent = data.报告信息.更新时间 || '--';
    }
}

// 更新核心指标
function updateCoreIndicators(data) {
    const marketSentimentEl = document.getElementById('marketSentiment');
    const sealingRateEl = document.getElementById('sealingRate');
    const limitUpCountEl = document.getElementById('limitUpCount');
    const maxBoardsEl = document.getElementById('maxBoards');
    
    const coreData = data.核心指标 || {};
    
    if (marketSentimentEl) {
        marketSentimentEl.textContent = formatPercent(coreData.活跃资金情绪);
    }
    if (sealingRateEl) {
        sealingRateEl.textContent = formatPercent(coreData.封板率);
    }
    if (limitUpCountEl) {
        limitUpCountEl.textContent = formatNumber(coreData.涨停数量) + '只';
    }
    if (maxBoardsEl) {
        maxBoardsEl.textContent = formatNumber(coreData.最高板数) + '板';
    }
}

// 更新市场分析
function updateMarketAnalysis(data) {
    const analysisContentEl = document.getElementById('analysisContent');
    
    if (analysisContentEl && data.市场分析) {
        analysisContentEl.textContent = data.市场分析.分析文本 || '暂无分析数据';
    }
}

// 更新涨停梯队分布
function updateLadderDistribution(data) {
    const ladderContentEl = document.getElementById('ladderContent');
    
    if (!ladderContentEl) return;
    
    const ladderStocks = data.涨停梯队 || {};
    
    if (Object.keys(ladderStocks).length === 0) {
        ladderContentEl.innerHTML = '<div class="no-ladder-data">暂无涨停梯队数据</div>';
        return;
    }
    
    let ladderHTML = '';
    
    // 按板数从高到低排序
    const sortedBoards = Object.keys(ladderStocks).sort((a, b) => {
        const aNum = parseInt(a.replace('板', ''));
        const bNum = parseInt(b.replace('板', ''));
        return bNum - aNum;
    });
    
    sortedBoards.forEach(boardType => {
        const stocks = ladderStocks[boardType];
        if (stocks && stocks.length > 0) {
            ladderHTML += `
                <div class="ladder-board-section">
                    <div class="board-header">
                        <h4>${boardType}</h4>
                        <span class="stock-count">(${stocks.length}只)</span>
                    </div>
                    <div class="stocks-grid">
            `;
            
            stocks.forEach(stock => {
                ladderHTML += `
                    <div class="stock-item">
                        <div class="stock-name">${stock.name}</div>
                        <div class="stock-code">${stock.code}</div>
                        <div class="stock-label">${stock.board_label}</div>
                        <div class="stock-market">${stock.market}</div>
                    </div>
                `;
            });
            
            ladderHTML += `
                    </div>
                </div>
            `;
        }
    });
    
    ladderContentEl.innerHTML = ladderHTML;
}


// 更新对比表格
function updateComparisonTable(data) {
    const tableBodyEl = document.getElementById('comparisonTableBody');
    
    if (!tableBodyEl) return;
    
    const todayData = data.今日数据 || {};
    const yesterdayData = data.前日数据 || {};
    
    const comparisons = [
        {
            name: '涨停板数量',
            today: formatNumber(todayData.涨停数量) + '只',
            yesterday: formatNumber(yesterdayData.涨停数量) + '只',
            change: calculateChange(todayData.涨停数量, yesterdayData.涨停数量, '只')
        },
        {
            name: '涨停封板率',
            today: formatPercent(todayData.封板率),
            yesterday: formatPercent(yesterdayData.封板率),
            change: calculatePercentChange(todayData.封板率, yesterdayData.封板率)
        },
        {
            name: '涨停打开',
            today: formatNumber(todayData.涨停打开) + '只',
            yesterday: formatNumber(yesterdayData.涨停打开) + '只',
            change: calculateChange(todayData.涨停打开, yesterdayData.涨停打开, '只')
        },
        {
            name: '跌停板数量',
            today: formatNumber(todayData.跌停数量) + '只',
            yesterday: formatNumber(yesterdayData.跌停数量) + '只',
            change: calculateChange(todayData.跌停数量, yesterdayData.跌停数量, '只')
        },
        {
            name: '跌停封板率',
            today: formatPercent(todayData.跌停封板率),
            yesterday: formatPercent(yesterdayData.跌停封板率),
            change: calculatePercentChange(todayData.跌停封板率, yesterdayData.跌停封板率)
        },
        {
            name: '跌停打开',
            today: formatNumber(todayData.跌停打开) + '只',
            yesterday: formatNumber(yesterdayData.跌停打开) + '只',
            change: calculateChange(todayData.跌停打开, yesterdayData.跌停打开, '只')
        },
        {
            name: '活跃资金情绪',
            today: formatPercent(todayData.活跃资金情绪),
            yesterday: '--',
            change: '--'
        }
    ];
    
    const tableHTML = comparisons.map(item => `
        <tr>
            <td>${item.name}</td>
            <td>${item.today}</td>
            <td>${item.yesterday}</td>
            <td class="${getChangeClass(item.change)}">${item.change}</td>
        </tr>
    `).join('');
    
    tableBodyEl.innerHTML = tableHTML;
}

// 更新连板统计
function updateBoardStatistics(data) {
    const maxBoardsStatEl = document.getElementById('maxBoardsStat');
    const boardCountEl = document.getElementById('boardCount');
    const naturalBoardCountEl = document.getElementById('naturalBoardCount');
    const touchLimitUpEl = document.getElementById('touchLimitUp');
    
    const boardData = data.连板统计 || {};
    
    if (maxBoardsStatEl) {
        maxBoardsStatEl.textContent = formatNumber(boardData.最高板数) + '板';
    }
    if (boardCountEl) {
        boardCountEl.textContent = formatNumber(boardData.连板家数) + '家';
    }
    if (naturalBoardCountEl) {
        naturalBoardCountEl.textContent = formatNumber(boardData.自然板家数) + '家';
    }
    if (touchLimitUpEl) {
        touchLimitUpEl.textContent = formatNumber(boardData.触及涨停) + '只';
    }
}

// 格式化百分比
function formatPercent(value) {
    if (value === null || value === undefined) {
        return '--';
    }
    try {
        const num = parseFloat(value);
        if (isNaN(num)) return '--';
        
        // 如果数值大于1，假设已经是百分比形式
        if (num > 1) {
            return num.toFixed(2) + '%';
        } else {
            // 如果数值小于等于1，转换为百分比
            return (num * 100).toFixed(2) + '%';
        }
    } catch {
        return '--';
    }
}

// 格式化数字
function formatNumber(value) {
    if (value === null || value === undefined) {
        return '--';
    }
    try {
        const num = parseFloat(value);
        if (isNaN(num)) return '--';
        return Math.round(num).toString();
    } catch {
        return '--';
    }
}

// 计算变化
function calculateChange(today, yesterday, unit = '') {
    if (today === null || today === undefined || yesterday === null || yesterday === undefined) {
        return '--';
    }
    
    try {
        const todayNum = parseFloat(today);
        const yesterdayNum = parseFloat(yesterday);
        
        if (isNaN(todayNum) || isNaN(yesterdayNum)) return '--';
        
        const change = todayNum - yesterdayNum;
        const sign = change > 0 ? '↑' : change < 0 ? '↓' : '';
        
        return `${sign}${Math.abs(change)}${unit}`;
    } catch {
        return '--';
    }
}

// 计算百分比变化
function calculatePercentChange(today, yesterday) {
    if (today === null || today === undefined || yesterday === null || yesterday === undefined) {
        return '--';
    }
    
    try {
        const todayNum = parseFloat(today);
        const yesterdayNum = parseFloat(yesterday);
        
        if (isNaN(todayNum) || isNaN(yesterdayNum)) return '--';
        
        // 确保都转换为相同的单位（百分比）
        const todayPercent = todayNum > 1 ? todayNum : todayNum * 100;
        const yesterdayPercent = yesterdayNum > 1 ? yesterdayNum : yesterdayNum * 100;
        
        const change = todayPercent - yesterdayPercent;
        const sign = change > 0 ? '↑' : change < 0 ? '↓' : '';
        
        return `${sign}${Math.abs(change).toFixed(2)}%`;
    } catch {
        return '--';
    }
}

// 获取变化样式类
function getChangeClass(changeText) {
    if (changeText.includes('↑')) {
        return 'change-positive';
    } else if (changeText.includes('↓')) {
        return 'change-negative';
    }
    return 'change-neutral';
}

// 复制涨停透视数据
function copyZTTSData() {
    if (!currentZTTSData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    const coreData = currentZTTSData.核心指标 || {};
    const todayData = currentZTTSData.今日数据 || {};
    const boardData = currentZTTSData.连板统计 || {};
    
    let textData = '大智慧涨停透视数据\n';
    textData += `数据日期: ${currentZTTSData.报告信息?.数据日期}\n`;
    textData += `更新时间: ${currentZTTSData.报告信息?.更新时间}\n\n`;
    
    textData += '核心指标:\n';
    textData += `活跃资金情绪: ${formatPercent(coreData.活跃资金情绪)}\n`;
    textData += `封板率: ${formatPercent(coreData.封板率)}\n`;
    textData += `涨停数量: ${formatNumber(coreData.涨停数量)}只\n`;
    textData += `最高板数: ${formatNumber(coreData.最高板数)}板\n\n`;
    
    textData += '连板统计:\n';
    textData += `最高板数: ${formatNumber(boardData.最高板数)}板\n`;
    textData += `连板家数: ${formatNumber(boardData.连板家数)}家\n`;
    textData += `自然板家数: ${formatNumber(boardData.自然板家数)}家\n`;
    textData += `触及涨停: ${formatNumber(boardData.触及涨停)}只\n\n`;
    
    if (currentZTTSData.市场分析?.分析文本) {
        textData += '市场分析:\n';
        textData += currentZTTSData.市场分析.分析文本;
    }
    
    copyToClipboard(textData);
}

// 查看JSON数据
function viewZTTSJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open(`json_viewer.html?type=ztts&date=${date}`, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}
