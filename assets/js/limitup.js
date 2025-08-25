// assets/js/limitup.js - 涨停池页面功能

let currentLimitUpData = null;

document.addEventListener('DOMContentLoaded', function() {
    initLimitUpPage();
});

async function initLimitUpPage() {
    await loadDateOptions();
    setupEventListeners();
}

// 加载日期选项
async function loadDateOptions() {
    try {
        const response = await fetch('data/index.json');
        if (!response.ok) throw new Error('无法加载日期数据');
        
        const dates = await response.json();
        const dateSelect = document.getElementById('dateSelect');
        
        if (!dateSelect) {
            console.error('dateSelect元素未找到');
            return;
        }
        
        dateSelect.innerHTML = '<option value="">选择日期...</option>';
        dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateSelect.appendChild(option);
        });
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateSelect.value = dates[0];
            await loadLimitUpData(dates[0]);
        }
    } catch (error) {
        console.error('加载日期选项失败:', error);
        const container = document.getElementById('stocksContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupEventListeners() {
    const dateSelect = document.getElementById('dateSelect');
    const searchInput = document.getElementById('searchInput');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    
    if (dateSelect) {
        dateSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                loadLimitUpData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterStocks, 300));
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyLimitUpData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewJsonData);
    }
}

// 加载涨停池数据
async function loadLimitUpData(date) {
    const container = document.getElementById('stocksContainer');
    const dataInfo = document.getElementById('dataInfo');
    
    if (!container) {
        console.error('stocksContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    
    try {
        const response = await fetch(`data/${date}.json`);
        if (!response.ok) throw new Error('数据加载失败');
        
        currentLimitUpData = await response.json();
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const stockCountEl = document.getElementById('stockCount');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentLimitUpData.update_time;
        }
        if (stockCountEl) {
            stockCountEl.textContent = `${currentLimitUpData.count}只`;
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 渲染股票列表
        renderStocks(currentLimitUpData.stocks);
        
    } catch (error) {
        console.error('加载涨停池数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染股票列表
function renderStocks(stocks) {
    const container = document.getElementById('stocksContainer');
    
    if (!container) {
        console.error('stocksContainer元素未找到');
        return;
    }
    
    if (!stocks || stocks.length === 0) {
        container.innerHTML = '<div class="loading">暂无数据</div>';
        return;
    }
    
    const stocksHtml = stocks.map(stock => `
        <div class="stock-card" data-code="${stock.code}" data-name="${stock.name}">
            <div class="stock-header">
                <div>
                    <div class="stock-code">${stock.code}</div>
                    <div class="stock-name">${stock.name}</div>
                </div>
                <div>
                    <div class="stock-price">¥${stock.price}</div>
                    <div class="stock-change">${stock.change_percent}</div>
                </div>
            </div>
            <div class="stock-details">
                <div><strong>涨停时间:</strong> ${stock.limit_up_time}</div>
                <div><strong>涨停原因:</strong> ${stock.reason}</div>
                <div><strong>所属板块:</strong> ${stock.plates || '暂无'}</div>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = stocksHtml;
}

// 筛选股票
function filterStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const stockCards = document.querySelectorAll('.stock-card');
    
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

// 复制涨停池数据
function copyLimitUpData() {
    if (!currentLimitUpData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    const textData = currentLimitUpData.stocks.map(stock => 
        `${stock.code}\t${stock.name}\t${stock.price}\t${stock.change_percent}\t${stock.limit_up_time}\t${stock.reason}\t${stock.plates}`
    ).join('\n');
    
    const header = '股票代码\t股票名称\t最新价格\t涨幅\t涨停时间\t涨停原因\t所属板块\n';
    const fullText = header + textData;
    
    copyToClipboard(fullText);
}

// 查看JSON数据
function viewJsonData() {
    const dateSelect = document.getElementById('dateSelect');
    if (!dateSelect) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateSelect.value;
    if (date) {
        window.open(`json_viewer.html?type=limitup&date=${date}`, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 导出Excel格式数据
function exportToExcel() {
    if (!currentLimitUpData) {
        showToast('暂无数据可导出', 'error');
        return;
    }
    
    const csvContent = "data:text/csv;charset=utf-8," 
        + "股票代码,股票名称,最新价格,涨幅,涨停时间,涨停原因,所属板块\n"
        + currentLimitUpData.stocks.map(stock => 
            `${stock.code},${stock.name},${stock.price},${stock.change_percent},${stock.limit_up_time},"${stock.reason}","${stock.plates}"`
        ).join('\n');
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `涨停池数据_${currentLimitUpData.date}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('数据导出成功！');
}