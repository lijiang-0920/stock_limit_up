// assets/js/analysis.js - 异动解析页面功能

let currentAnalysisData = null;

document.addEventListener('DOMContentLoaded', function() {
    initAnalysisPage();
});

async function initAnalysisPage() {
    await loadAnalysisDateOptions();
    setupAnalysisEventListeners();
}

// 加载日期选项
async function loadAnalysisDateOptions() {
    try {
        const response = await fetch('analysis/index.json');
        if (!response.ok) throw new Error('无法加载异动解析日期数据');
        
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
            await loadAnalysisData(dates[0]);
        }
    } catch (error) {
        console.error('加载异动解析日期选项失败:', error);
        const container = document.getElementById('analysisContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupAnalysisEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadAnalysisData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterAnalysisStocks, 300));
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyAnalysisData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewAnalysisJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载异动解析数据
async function loadAnalysisData(date) {
    const container = document.getElementById('analysisContainer');
    const dataInfo = document.getElementById('dataInfo');
    
    if (!container) {
        console.error('analysisContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    
    try {
        const response = await fetch('analysis/' + date + '.json');
        if (!response.ok) throw new Error('异动解析数据加载失败');
        
        currentAnalysisData = await response.json();
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const categoryCountEl = document.getElementById('categoryCount');
        const stockCountEl = document.getElementById('stockCount');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentAnalysisData.update_time;
        }
        if (categoryCountEl) {
            categoryCountEl.textContent = currentAnalysisData.category_count + '个';
        }
        if (stockCountEl) {
            stockCountEl.textContent = currentAnalysisData.total_stocks + '只';
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 渲染异动解析数据
        renderAnalysisData(currentAnalysisData.categories);
        
    } catch (error) {
        console.error('加载异动解析数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染异动解析数据
function renderAnalysisData(categories) {
    const container = document.getElementById('analysisContainer');
    
    if (!container) {
        console.error('analysisContainer元素未找到');
        return;
    }
    
    if (!categories || categories.length === 0) {
        container.innerHTML = '<div class="loading">暂无异动解析数据</div>';
        return;
    }
    
    const categoriesHtml = categories.map(category => {
        const reasonHtml = category.reason ? '<div class="category-reason">' + category.reason + '</div>' : '';
        const stocksHtml = category.stocks.map(stock => {
            const limitTimeHtml = stock.limit_time ? '<div class="limit-time">涨停时间: ' + stock.limit_time + '</div>' : '';
            const analysisHtml = stock.analysis ? '<div class="stock-analysis">' + stock.analysis + '</div>' : '';
            return '<div class="analysis-stock-card" data-code="' + stock.code + '" data-name="' + stock.name + '">' +
                   '<div class="stock-info">' +
                   '<div class="stock-basic">' +
                   '<span class="stock-code-analysis">' + stock.code + '</span>' +
                   '<span class="stock-name-analysis">' + stock.name + '</span>' +
                   '</div>' +
                   limitTimeHtml +
                   '</div>' +
                   analysisHtml +
                   '</div>';
        }).join('');
        
        return '<div class="category-card" data-category="' + category.name + '">' +
               '<div class="category-header">' +
               '<div class="category-title">' + category.name + '</div>' +
               reasonHtml +
               '<div class="category-stats">涉及股票: ' + category.stock_count + ' 只</div>' +
               '</div>' +
               '<div class="stocks-list">' +
               stocksHtml +
               '</div>' +
               '</div>';
    }).join('');
    
    container.innerHTML = categoriesHtml;
}

// 筛选股票
function filterAnalysisStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const categoryCards = document.querySelectorAll('.category-card');
    
    categoryCards.forEach(categoryCard => {
        const stockCards = categoryCard.querySelectorAll('.analysis-stock-card');
        let hasVisibleStocks = false;
        
        stockCards.forEach(stockCard => {
            const code = stockCard.dataset.code.toLowerCase();
            const name = stockCard.dataset.name.toLowerCase();
            
            if (code.includes(searchTerm) || name.includes(searchTerm)) {
                stockCard.style.display = 'block';
                hasVisibleStocks = true;
            } else {
                stockCard.style.display = 'none';
            }
        });
        
        // 如果板块下没有匹配的股票，隐藏整个板块
        if (searchTerm && !hasVisibleStocks) {
            categoryCard.style.display = 'none';
        } else {
            categoryCard.style.display = 'block';
        }
    });
}

// 复制异动解析数据
function copyAnalysisData() {
    if (!currentAnalysisData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    let textData = '韭研公社异动解析 - ' + currentAnalysisData.date + '\n';
    textData += '更新时间: ' + currentAnalysisData.update_time + '\n';
    textData += '板块数量: ' + currentAnalysisData.category_count + ' 个\n';
    textData += '股票数量: ' + currentAnalysisData.total_stocks + ' 只\n';
    textData += "=" + "=".repeat(80) + "\n\n";
    
    currentAnalysisData.categories.forEach(category => {
        textData += '=== ' + category.name + ' ===\n';
        if (category.reason) {
            textData += '板块异动解析: ' + category.reason + '\n';
        }
        textData += '涉及股票: ' + category.stock_count + ' 只\n\n';
        
        category.stocks.forEach(stock => {
            textData += stock.name + '（' + stock.code + '）\n';
            if (stock.limit_time) {
                textData += '涨停时间: ' + stock.limit_time + '\n';
            }
            textData += '个股异动解析: ' + stock.analysis + '\n';
            textData += "\n" + "-".repeat(80) + "\n\n";
        });
    });
    
    copyToClipboard(textData);
}

// 查看JSON数据
function viewAnalysisJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open('json_viewer.html?type=analysis&date=' + date, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 导出Excel格式数据
function exportAnalysisToExcel() {
    if (!currentAnalysisData) {
        showToast('暂无数据可导出', 'error');
        return;
    }
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "板块名称,板块解析,股票代码,股票名称,涨停时间,个股解析\n";
    
    currentAnalysisData.categories.forEach(category => {
        category.stocks.forEach(stock => {
            const categoryName = category.name || "";
            const categoryReason = category.reason || "";
            const stockCode = stock.code || "";
            const stockName = stock.name || "";
            const limitTime = stock.limit_time || "";
            const analysis = stock.analysis || "";
            
            csvContent += '"' + categoryName + '","' + categoryReason + '","' + stockCode + '","' + stockName + '","' + limitTime + '","' + analysis + '"\n';
        });
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', '异动解析_' + currentAnalysisData.date + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('数据导出成功！');
}

// 获取异动解析统计信息
function getAnalysisStats() {
    if (!currentAnalysisData) return null;
    
    const stats = {
        totalCategories: currentAnalysisData.category_count,
        totalStocks: currentAnalysisData.total_stocks,
        categoriesWithReason: 0,
        stocksWithLimitTime: 0,
        avgStocksPerCategory: 0
    };
    
    currentAnalysisData.categories.forEach(category => {
        if (category.reason) {
            stats.categoriesWithReason++;
        }
        
        category.stocks.forEach(stock => {
            if (stock.limit_time) {
                stats.stocksWithLimitTime++;
            }
        });
    });
    
    stats.avgStocksPerCategory = (stats.totalStocks / stats.totalCategories).toFixed(1);
    
    return stats;
}

// 显示统计信息
function showAnalysisStats() {
    const stats = getAnalysisStats();
    if (!stats) {
        showToast('暂无统计数据', 'error');
        return;
    }
    
    const statsContent = '<div style="padding: 20px;">' +
        '<h3>📊 异动解析统计</h3>' +
        '<div style="margin: 20px 0;">' +
        '<p><strong>总板块数:</strong> ' + stats.totalCategories + ' 个</p>' +
        '<p><strong>总股票数:</strong> ' + stats.totalStocks + ' 只</p>' +
        '<p><strong>有解析的板块:</strong> ' + stats.categoriesWithReason + ' 个</p>' +
        '<p><strong>有涨停时间的股票:</strong> ' + stats.stocksWithLimitTime + ' 只</p>' +
        '<p><strong>平均每板块股票数:</strong> ' + stats.avgStocksPerCategory + ' 只</p>' +
        '</div>' +
        '<p style="color: #999; font-size: 0.9rem;">' +
        '数据更新时间: ' + currentAnalysisData.update_time +
        '</p>' +
        '</div>';
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = '<div class="modal-content" style="max-width: 400px;">' +
        '<div class="modal-header">' +
        '<span class="close" onclick="this.closest(\'.modal\').remove()">&times;</span>' +
        '<h2>统计信息</h2>' +
        '</div>' +
        '<div class="modal-body">' +
        statsContent +
        '</div>' +
        '</div>';
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}