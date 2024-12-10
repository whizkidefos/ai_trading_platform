// Global variables
let updateTimeout;
let stocksChart, performanceChart, priceChart;
let isTrading = false;
let currentAsset = 'AAPL'; // Default to AAPL if no form
let currentAssets = ['AAPL']; // Default to AAPL if no form
let isAutomatedTradingActive = false;

// Rate limiting variables for asset info
let assetInfoRetryCount = 0;
const MAX_RETRY_COUNT = 3;
const RETRY_DELAY = 5000; // 5 seconds

// Initialize Charts
function initializeCharts() {
    console.log('Initializing charts...');
    const stocksCtx = document.getElementById('stocksChart');
    const performanceCtx = document.getElementById('performanceChart');
    const priceCtx = document.getElementById('priceChart');
    
    if (stocksCtx) {
        stocksChart = new Chart(stocksCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Stock Price',
                    data: [],
                    borderColor: '#4f46e5',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#ffffff'
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    }
                }
            }
        });
    }
    
    if (performanceCtx) {
        performanceChart = new Chart(performanceCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Account Performance',
                    data: [],
                    borderColor: '#10b981',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#ffffff'
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    }
                }
            }
        });
    }
    
    if (priceCtx) {
        priceChart = new Chart(priceCtx, {
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
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#ffffff'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#ffffff'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    y: {
                        ticks: {
                            color: '#ffffff',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                }
            }
        });
    }
}

// Update Charts
function updateCharts(data) {
    if (stocksChart && data.price_history) {
        stocksChart.data.labels = data.price_history.map(p => new Date(p.timestamp));
        stocksChart.data.datasets[0].data = data.price_history.map(p => p.price);
        stocksChart.update();
    }
    
    if (performanceChart && data.performance_history) {
        performanceChart.data.labels = data.performance_history.map(p => new Date(p.timestamp));
        performanceChart.data.datasets[0].data = data.performance_history.map(p => p.value);
        performanceChart.update();
    }
    
    if (priceChart && data.price_history) {
        console.log('Updating chart with new data:', data.price_history);
        
        const labels = data.price_history.map(item => {
            const date = new Date(item.time);
            return date.toLocaleTimeString();
        });
        
        const prices = data.price_history.map(item => item.price);
        
        priceChart.data.labels = labels;
        priceChart.data.datasets[0].data = prices;
        priceChart.update();
    }
}

// Get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Update trading status and controls
function updateTradingStatus() {
    console.log('Updating trading status...');
    fetch('/trading/api/v1/trading/status/')
    .then(response => response.json())
    .then(data => {
        if (!data.error) {
            // Update trading status display
            const autoSwitch = document.getElementById('autoTradingSwitch');
            if (autoSwitch) {
                autoSwitch.checked = data.is_trading;
            }
            
            // Update trading form visibility
            const tradingForm = document.getElementById('tradingParametersForm');
            if (tradingForm) {
                tradingForm.style.display = data.is_trading ? 'block' : 'none';
            }
            
            // Update trading status
            const statusText = document.getElementById('statusText');
            if (statusText) {
                statusText.textContent = data.is_trading ? 'Active' : 'Inactive';
                statusText.className = `badge ${data.is_trading ? 'bg-success' : 'bg-secondary'}`;
            }
            
            // Update statistics
            const activeTrades = document.getElementById('activeTrades');
            if (activeTrades) {
                activeTrades.textContent = data.active_trades;
            }
            
            const totalProfit = document.getElementById('totalProfit');
            if (totalProfit) {
                totalProfit.textContent = `$${data.total_profit.toFixed(2)}`;
            }
            
            const winRate = document.getElementById('winRate');
            if (winRate) {
                winRate.textContent = `${data.win_rate.toFixed(1)}%`;
            }
            
            // Update last trade time
            const lastUpdate = document.getElementById('lastUpdateTime');
            if (lastUpdate && data.last_trade_time) {
                const lastTradeDate = new Date(data.last_trade_time);
                lastUpdate.textContent = lastTradeDate.toLocaleString();
            }
            
            // Show trading status section
            const tradingStatus = document.getElementById('tradingStatus');
            if (tradingStatus) {
                tradingStatus.style.display = 'block';
            }
        } else {
            console.error('Error fetching trading status:', data.error);
        }
    })
    .catch(error => {
        console.error('Error updating trading status:', error);
    });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    const autoSwitch = document.getElementById('autoTradingSwitch');
    const tradingForm = document.getElementById('tradingParametersForm');
    const tradingStatus = document.getElementById('tradingStatus');

    // Track if trading is active
    let isTrading = false;

    if (autoSwitch) {
        autoSwitch.addEventListener('change', function() {
            if (this.checked) {
                // Only show the form initially when switch is turned on
                if (tradingForm) tradingForm.style.display = 'block';
                if (tradingStatus) tradingStatus.style.display = 'block';
            } else {
                // When switch is turned off, stop trading and hide controls
                stopTrading();
                if (tradingForm) tradingForm.style.display = 'none';
                if (tradingStatus) tradingStatus.style.display = 'none';
                isTrading = false;
            }
        });
    }

    // Handle trading parameters form submission
    if (tradingForm) {
        tradingForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!isTrading) {
                // Start trading with the provided parameters
                const success = await startTrading();
                if (success) {
                    isTrading = true;
                } else {
                    // If starting fails, reset the switch
                    if (autoSwitch) autoSwitch.checked = false;
                    if (tradingForm) tradingForm.style.display = 'none';
                    if (tradingStatus) tradingStatus.style.display = 'none';
                }
            } else {
                // Just update parameters if already trading
                updateTradingParameters();
            }
        });
    }

    // Initial status update
    updateTradingStatus();
    
    // Update status periodically
    setInterval(updateTradingStatus, 30000); // Update every 30 seconds
});

// Start automated trading with parameters
async function startTrading() {
    const tradeAmount = document.getElementById('tradeAmount');
    const minPrice = document.getElementById('minPrice');
    const maxPrice = document.getElementById('maxPrice');
    
    // Validate trading parameters
    if (!tradeAmount || !minPrice || !maxPrice) {
        showNotification('Please set trading parameters first', 'error');
        return false;
    }

    if (parseFloat(tradeAmount.value) <= 0) {
        showNotification('Trade amount must be greater than 0', 'error');
        return false;
    }

    if (parseFloat(minPrice.value) >= parseFloat(maxPrice.value)) {
        showNotification('Minimum price must be less than maximum price', 'error');
        return false;
    }

    try {
        const response = await fetch('/trading/api/v1/trading/start/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                trade_amount: parseFloat(tradeAmount.value),
                min_price: parseFloat(minPrice.value),
                max_price: parseFloat(maxPrice.value)
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification('Automated trading started successfully', 'success');
            updateTradingStatus();
            return true;
        } else {
            showNotification(data.message || 'Error starting automated trading', 'error');
            return false;
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error starting automated trading', 'error');
        return false;
    }
}

// Stop automated trading
async function stopTrading() {
    try {
        const response = await fetch('/trading/api/v1/trading/stop/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification('Automated trading stopped successfully', 'success');
            updateTradingStatus();
        } else {
            showNotification(data.message || 'Error stopping automated trading', 'error');
            
            // Reset switch if failed
            const autoSwitch = document.getElementById('autoTradingSwitch');
            if (autoSwitch) {
                autoSwitch.checked = true;
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error stopping automated trading', 'error');
        
        // Reset switch on error
        const autoSwitch = document.getElementById('autoTradingSwitch');
        if (autoSwitch) {
            autoSwitch.checked = true;
        }
    }
}

// Update trading parameters
async function updateTradingParameters() {
    const tradeAmount = document.getElementById('tradeAmount');
    const minPrice = document.getElementById('minPrice');
    const maxPrice = document.getElementById('maxPrice');
    
    if (!tradeAmount || !minPrice || !maxPrice) {
        showNotification('Trading parameters form fields not found', 'error');
        return;
    }

    // Validate input values
    if (parseFloat(minPrice.value) >= parseFloat(maxPrice.value)) {
        showNotification('Minimum price must be less than maximum price', 'error');
        return;
    }

    if (parseFloat(tradeAmount.value) <= 0) {
        showNotification('Trade amount must be greater than 0', 'error');
        return;
    }
    
    try {
        const response = await fetch('/trading/api/v1/trading/update-parameters/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                trade_amount: parseFloat(tradeAmount.value),
                min_price: parseFloat(minPrice.value),
                max_price: parseFloat(maxPrice.value)
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification('Trading parameters updated successfully', 'success');
            updateTradingStatus();
        } else {
            showNotification(data.message || 'Error updating trading parameters', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error updating trading parameters', 'error');
    }
}

// Update trading statistics display
function updateTradingStats(data) {
    const activeTrades = document.getElementById('activeTrades');
    if (activeTrades) {
        activeTrades.textContent = data.active_trades;
    }
    
    const totalProfit = document.getElementById('totalProfit');
    if (totalProfit) {
        totalProfit.textContent = '$' + data.total_profit.toFixed(2);
        totalProfit.className = data.total_profit >= 0 ? 'text-success' : 'text-danger';
    }
    
    const winRate = document.getElementById('winRate');
    if (winRate) {
        winRate.textContent = data.win_rate.toFixed(1) + '%';
    }
    
    const lastTrade = document.getElementById('lastTrade');
    if (lastTrade && data.last_trade_time) {
        const date = new Date(data.last_trade_time);
        lastTrade.textContent = date.toLocaleString();
    }
}

// Notification helper
function showNotification(message, type) {
    console.log('Showing notification:', message, type);
    const notification = document.getElementById('notification');
    if (notification) {
        notification.className = `alert alert-${type}`;
        notification.textContent = message;
        notification.style.display = 'block';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 5000);
    }
}

// Deposit handling
async function handleDeposit(event) {
    event.preventDefault();
    console.log('Handling deposit...');

    const form = document.getElementById('depositForm');
    const amount = document.getElementById('depositAmount').value;
    const method = document.getElementById('depositMethod').value;

    try {
        const response = await fetch('/trading/deposit/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                amount: amount,
                method: method
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification('Deposit initiated successfully!', 'success');
            $('#depositModal').modal('hide');
            form.reset();
            
            // If PayPal, redirect to PayPal
            if (method === 'paypal' && data.redirect_url) {
                window.location.href = data.redirect_url;
            }
        } else {
            showNotification(data.error || 'Failed to process deposit', 'error');
        }
    } catch (error) {
        console.error('Deposit error:', error);
        showNotification('Error processing deposit', 'error');
    }
}

// Withdrawal handling
async function handleWithdrawal(event) {
    event.preventDefault();
    console.log('Handling withdrawal...');

    const form = document.getElementById('withdrawForm');
    const amount = document.getElementById('withdrawAmount').value;
    const method = document.getElementById('withdrawMethod').value;
    const address = document.getElementById('withdrawAddress').value;

    try {
        const response = await fetch('/trading/withdraw/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                amount: amount,
                method: method,
                address: address
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            showNotification('Withdrawal request submitted successfully!', 'success');
            $('#withdrawModal').modal('hide');
            form.reset();
        } else {
            showNotification(data.error || 'Failed to process withdrawal', 'error');
        }
    } catch (error) {
        console.error('Withdrawal error:', error);
        showNotification('Error processing withdrawal', 'error');
    }
}