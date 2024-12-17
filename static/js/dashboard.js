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

// Helper function to determine if we're in development
function isDevelopment() {
    return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

// Helper function to get the correct protocol
function getProtocol() {
    return isDevelopment() ? 'http:' : 'https:';
}

// Helper function to make API calls
async function makeApiCall(endpoint, method = 'GET', data = null) {
    const protocol = getProtocol();
    const baseUrl = `${protocol}//${window.location.host}`;
    const url = `${baseUrl}${endpoint}`;
    
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'same-origin'
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Function to update trading status
async function updateTradingStatus() {
    try {
        const data = await makeApiCall('/trading/api/v1/trading/status/');
        console.log('Trading status data:', data);
        
        // Update switch state
        const autoSwitch = document.getElementById('autoTradingSwitch');
        if (autoSwitch) {
            autoSwitch.checked = data.is_trading;
            isAutomatedTradingActive = data.is_trading;
        }
        
        // Update form visibility
        const tradingForm = document.getElementById('tradingParametersForm');
        if (tradingForm) {
            tradingForm.style.display = data.is_trading ? 'block' : 'none';
        }
        
        // Update metrics
        document.getElementById('activeTrades').textContent = data.active_trades;
        document.getElementById('totalProfit').textContent = data.total_profit.toFixed(2);
        document.getElementById('winRate').textContent = data.win_rate.toFixed(1);
        
        // Update last trade info if available
        if (data.last_trade) {
            document.getElementById('lastTradeType').textContent = data.last_trade.type;
            document.getElementById('lastTradeAmount').textContent = data.last_trade.amount;
            document.getElementById('lastTradePrice').textContent = data.last_trade.price;
            document.getElementById('lastTradeTime').textContent = new Date(data.last_trade.time).toLocaleString();
        }
        
        // Show/hide stop button
        const stopButtonContainer = document.getElementById('stopButtonContainer');
        if (stopButtonContainer) {
            if (data.is_trading && !document.getElementById('stopTradingBtn')) {
                const stopButton = document.createElement('button');
                stopButton.id = 'stopTradingBtn';
                stopButton.className = 'btn btn-danger mt-3';
                stopButton.textContent = 'Stop Trading';
                stopButton.onclick = stopTrading;
                stopButtonContainer.appendChild(stopButton);
            } else if (!data.is_trading) {
                stopButtonContainer.innerHTML = '';
            }
        }
    } catch (error) {
        console.error('Error updating trading status:', error);
        showNotification('Failed to update trading status', 'error');
    }
}

// Function to start trading
async function startTrading() {
    try {
        const tradeAmount = document.getElementById('tradeAmount').value;
        const minPrice = document.getElementById('minPrice').value;
        const maxPrice = document.getElementById('maxPrice').value;

        // First update the parameters
        const paramsResponse = await makeApiCall('/trading/api/v1/trading/update-parameters/', 'POST', {
            trade_amount: tradeAmount,
            min_price: minPrice,
            max_price: maxPrice
        });

        if (!paramsResponse.ok) {
            throw new Error('Failed to update trading parameters');
        }

        // Then start trading
        const startResponse = await makeApiCall('/trading/api/v1/trading/start/', 'POST');

        if (!startResponse.ok) {
            throw new Error('Failed to start trading');
        }

        showNotification('Trading started successfully', 'success');
        isAutomatedTradingActive = true;
        updateTradingStatus();
        return true;
    } catch (error) {
        console.error('Error starting trading:', error);
        showNotification('Failed to start trading: ' + error.message, 'error');
        return false;
    }
}

// Function to stop trading
async function stopTrading() {
    try {
        const response = await makeApiCall('/trading/api/v1/trading/stop/', 'POST');

        if (!response.ok) {
            throw new Error('Failed to stop trading');
        }

        showNotification('Trading stopped successfully', 'success');
        isAutomatedTradingActive = false;
        
        // Update UI
        const autoSwitch = document.getElementById('autoTradingSwitch');
        const tradingForm = document.getElementById('tradingParametersForm');
        const stopButtonContainer = document.getElementById('stopButtonContainer');
        
        if (autoSwitch) autoSwitch.checked = false;
        if (tradingForm) tradingForm.style.display = 'none';
        if (stopButtonContainer) stopButtonContainer.innerHTML = '';
        
        updateTradingStatus();
    } catch (error) {
        console.error('Error stopping trading:', error);
        showNotification('Failed to stop trading: ' + error.message, 'error');
    }
}

// Function to show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    notification.style.zIndex = '1050';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    const autoSwitch = document.getElementById('autoTradingSwitch');
    const tradingForm = document.getElementById('tradingParametersForm');
    const tradingParamsForm = document.getElementById('tradingForm');
    const depositForm = document.getElementById('depositForm');
    const withdrawForm = document.getElementById('withdrawForm');

    if (autoSwitch) {
        autoSwitch.addEventListener('change', function() {
            if (this.checked) {
                if (tradingForm) tradingForm.style.display = 'block';
            } else {
                stopTrading();
            }
        });
    }

    if (tradingParamsForm) {
        tradingParamsForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const tradeAmount = document.getElementById('tradeAmount').value;
            const minPrice = document.getElementById('minPrice').value;
            const maxPrice = document.getElementById('maxPrice').value;

            try {
                const response = await makeApiCall('/trading/api/v1/trading/update-parameters/', 'POST', {
                    trade_amount: parseFloat(tradeAmount),
                    min_price: parseFloat(minPrice),
                    max_price: parseFloat(maxPrice)
                });

                showNotification('Trading parameters updated successfully', 'success');
                await updateTradingStatus();
            } catch (error) {
                console.error('Error updating parameters:', error);
                showNotification('Failed to update parameters: ' + error.message, 'error');
            }
        });
    }

    // Handle deposit form submission
    if (depositForm) {
        depositForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const amount = document.getElementById('depositAmount').value;
            const method = document.getElementById('depositMethod').value;

            try {
                const response = await makeApiCall('/trading/api/v1/account/deposit/', 'POST', {
                    amount: parseFloat(amount),
                    payment_method: method
                });

                // Handle successful deposit
                if (response.redirect_url) {
                    window.location.href = response.redirect_url;
                } else {
                    showNotification('Deposit request submitted successfully', 'success');
                    // Close the modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('depositModal'));
                    if (modal) modal.hide();
                    // Update account balance display
                    await updateTradingStatus();
                }
            } catch (error) {
                console.error('Error processing deposit:', error);
                showNotification('Failed to process deposit: ' + error.message, 'error');
            }
        });
    }

    // Handle withdraw form submission
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const amount = document.getElementById('withdrawAmount').value;
            const method = document.getElementById('withdrawMethod').value;
            const address = document.getElementById('withdrawAddress').value;

            try {
                const response = await makeApiCall('/trading/api/v1/account/withdraw/', 'POST', {
                    amount: parseFloat(amount),
                    withdrawal_method: method,
                    address: address
                });

                showNotification('Withdrawal request submitted successfully', 'success');
                
                // Close the modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('withdrawModal'));
                if (modal) modal.hide();
                
                // Update account balance display
                await updateTradingStatus();
            } catch (error) {
                console.error('Error processing withdrawal:', error);
                showNotification('Failed to process withdrawal: ' + error.message, 'error');
            }
        });
    }

    // Initial status update
    updateTradingStatus();
    
    // Update status periodically
    setInterval(updateTradingStatus, 5000); // Update every 5 seconds
});