// Asset Selection Chart
let updateTimeout;

function updateAssetInfo() {
    const form = document.getElementById('asset-form');
    const formData = new FormData(form);
    
    // Show loading state
    document.getElementById('asset-price').textContent = 'Loading...';
    document.getElementById('asset-volume').textContent = 'Loading...';
    document.getElementById('trading-signal').textContent = 'Loading...';
    document.getElementById('rsi-value').textContent = 'Loading...';
    document.getElementById('macd-value').textContent = 'Loading...';
    document.getElementById('sma5-value').textContent = 'Loading...';
    document.getElementById('sma20-value').textContent = 'Loading...';
    document.getElementById('last-update').textContent = 'Loading...';

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': formData.get('csrfmiddlewaretoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.error(data.error);
            return;
        }
        
        // Update asset information
        document.getElementById('asset-price').textContent = `$${data.last_price.toFixed(2)}`;
        document.getElementById('asset-volume').textContent = data.volume.toLocaleString();
        
        // Update trading signal with emoji and color
        const signalElement = document.getElementById('trading-signal');
        if (data.signal === 1) {
            signalElement.textContent = '🔥 Strong Buy';
            signalElement.className = 'text-success';
        } else if (data.signal === -1) {
            signalElement.textContent = '❄️ Strong Sell';
            signalElement.className = 'text-danger';
        } else {
            signalElement.textContent = '⚪ Hold';
            signalElement.className = 'text-warning';
        }
        
        // Update technical indicators
        document.getElementById('rsi-value').textContent = data.technical_indicators.rsi.toFixed(2);
        document.getElementById('macd-value').textContent = data.technical_indicators.macd.toFixed(2);
        document.getElementById('sma5-value').textContent = data.technical_indicators.sma5.toFixed(2);
        document.getElementById('sma20-value').textContent = data.technical_indicators.sma20.toFixed(2);
        
        document.getElementById('last-update').textContent = data.timestamp;
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Update on asset selection change with debounce
document.getElementById('asset').addEventListener('change', function() {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(updateAssetInfo, 300); // 300ms debounce
});

// Initial load with default asset (AAPL)
document.addEventListener('DOMContentLoaded', updateAssetInfo);

// Auto-refresh every 60 seconds
setInterval(updateAssetInfo, 60000);

// Initialize all charts
function initializeCharts() {
    // Price Chart
    const priceCtx = document.getElementById('priceChart').getContext('2d');
    window.priceChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Price',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            scales: {
                y: {
                    beginAtZero: false
                }
            }
        }
    });

    // Volume Chart
    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    window.volumeChart = new Chart(volumeCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Volume',
                data: [],
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgb(54, 162, 235)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    // Technical Indicators Chart
    const technicalCtx = document.getElementById('technicalChart').getContext('2d');
    window.technicalChart = new Chart(technicalCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'RSI',
                    data: [],
                    borderColor: 'rgb(255, 99, 132)',
                    tension: 0.1,
                    yAxisID: 'rsi'
                },
                {
                    label: 'MACD',
                    data: [],
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1,
                    yAxisID: 'macd'
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                rsi: {
                    type: 'linear',
                    position: 'left',
                    min: 0,
                    max: 100
                },
                macd: {
                    type: 'linear',
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });

    // Profit/Loss Chart
    const plCtx = document.getElementById('profitLossChart').getContext('2d');
    window.profitLossChart = new Chart(plCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Profit/Loss',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: function(context) {
                    const value = context.raw;
                    return value >= 0 ? 'rgba(75, 192, 192, 0.2)' : 'rgba(255, 99, 132, 0.2)';
                },
                fill: true
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Update charts with new data
function updateCharts(data) {
    const timestamp = new Date().toLocaleTimeString();

    // Update Price Chart
    if (data.price) {
        priceChart.data.labels.push(timestamp);
        priceChart.data.datasets[0].data.push(data.price);
        if (priceChart.data.labels.length > 50) {
            priceChart.data.labels.shift();
            priceChart.data.datasets[0].data.shift();
        }
        priceChart.update();
    }

    // Update Volume Chart
    if (data.volume) {
        volumeChart.data.labels.push(timestamp);
        volumeChart.data.datasets[0].data.push(data.volume);
        if (volumeChart.data.labels.length > 20) {
            volumeChart.data.labels.shift();
            volumeChart.data.datasets[0].data.shift();
        }
        volumeChart.update();
    }

    // Update Technical Indicators Chart
    if (data.technical) {
        technicalChart.data.labels.push(timestamp);
        technicalChart.data.datasets[0].data.push(data.technical.rsi);
        technicalChart.data.datasets[1].data.push(data.technical.macd);
        if (technicalChart.data.labels.length > 50) {
            technicalChart.data.labels.shift();
            technicalChart.data.datasets[0].data.shift();
            technicalChart.data.datasets[1].data.shift();
        }
        technicalChart.update();
    }

    // Update Profit/Loss Chart
    if (data.profitLoss !== undefined) {
        profitLossChart.data.labels.push(timestamp);
        profitLossChart.data.datasets[0].data.push(data.profitLoss);
        if (profitLossChart.data.labels.length > 50) {
            profitLossChart.data.labels.shift();
            profitLossChart.data.datasets[0].data.shift();
        }
        profitLossChart.update();
    }
}

// Initialize charts when the page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeCharts();
    updateAutomatedTradingStatus();
});

// Update WebSocket message handler to update charts
autoTradingSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    handleAutoTradingUpdate(data);
    updateCharts(data);
};