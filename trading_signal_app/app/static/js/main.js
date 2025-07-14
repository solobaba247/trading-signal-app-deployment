document.addEventListener('DOMContentLoaded', () => {
    const fallbackFetcher = new ClientFallbackDataFetcher();

    const modelStatusBadge = document.getElementById('model-status-badge');
    const globalStatusAlert = document.getElementById('global-status-alert');
    const timeframeSelect = document.getElementById('timeframe-select');
    const categorySelect = document.getElementById('pair-category');
    const assetSelect = document.getElementById('asset-symbol');
    const generateSignalBtn = document.getElementById('generate-signal-btn');
    const singleSignalResult = document.getElementById('single-signal-result');
    const scanSpinner = document.getElementById('scan-spinner');
    const scanResultsBody = document.getElementById('scan-results-body');
    // NEW: Select the new input
    const analysisPeriodInput = document.getElementById('analysis-period-input');
    const allInteractiveElements = [timeframeSelect, analysisPeriodInput, categorySelect, assetSelect, generateSignalBtn, ...document.querySelectorAll('.scan-btn')];

    const showAlert = (container, message, type = 'danger') => {
        container.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message} <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;
    };

    const toggleButtonSpinner = (button, show) => {
        const spinner = button.querySelector('.spinner-border');
        button.disabled = show;
        if (spinner) spinner.classList.toggle('d-none', !show);
    };

    const getSignalClass = (signal) => `signal-${signal ? signal.toLowerCase() : 'hold'}`;

    const renderSignalResult = (data, isFallback = false) => {
        const signalClass = getSignalClass(data.signal);
        let resultHtml;

        if (isFallback) {
            const cardBorder = data.signal === 'BUY' ? 'border-success' : (data.signal === 'SELL' ? 'border-danger' : 'border-secondary');
            resultHtml = `
                <div class="card ${cardBorder}">
                    <div class="card-header bg-warning-subtle d-flex justify-content-between align-items-center">
                        <h5 class="mb-0 text-warning-emphasis"><i class="fas fa-exclamation-triangle me-2"></i>RULE-BASED FALLBACK SIGNAL</h5>
                        <span class="badge bg-secondary">${data.symbol}</span>
                    </div>
                    <div class="card-body">
                         <p class="card-text text-muted">The primary ML model failed to generate a signal. The following is a simplified, rule-based analysis conducted on the client-side.</p>
                         <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between"><strong>Signal:</strong> <span class="${signalClass}">${data.signal}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Current Price:</strong> <span>${data.entry_price}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Timestamp:</strong> <span>${data.timestamp}</span></li>
                        </ul>
                    </div>
                    <!-- NEW: Display the reason for the fallback signal -->
                    <div class="card-footer bg-transparent text-muted small">
                        <strong>Reasoning:</strong> ${data.reason || 'No specific reason provided.'}
                    </div>
                </div>`;
        } else if (data.signal === "HOLD") {
            resultHtml = `
                <div class="card bg-secondary-subtle text-center p-3">
                    <div class="card-body">
                         <h4 class="card-title ${signalClass}"><i class="fas fa-hand-paper me-2"></i>HOLD</h4>
                         <p class="mb-1"><strong>Symbol:</strong> ${data.symbol}</p>
                         <p class="mb-0">The ML model does not have a strong conviction for a BUY or SELL signal at this time.</p>
                    </div>
                </div>`;
        } else {
            const cardBorder = data.signal === 'BUY' ? 'border-success' : 'border-danger';
            resultHtml = `
                <div class="card ${cardBorder}">
                    <div class="card-header bg-transparent d-flex justify-content-between align-items-center">
                        <h5 class="mb-0 ${signalClass}"><i class="fas fa-arrow-trend-${signalClass === 'signal-buy' ? 'up' : 'down'} me-2"></i>${data.signal} SIGNAL (ML)</h5>
                        <span class="badge bg-secondary">${data.symbol}</span>
                    </div>
                    <div class="card-body">
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between"><strong>Confidence:</strong> <span>${data.confidence}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Entry Price:</strong> <span>${data.entry_price}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Take Profit:</strong> <span>${data.exit_price}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Stop Loss:</strong> <span>${data.stop_loss} <small class="text-muted ms-2">${data.stop_loss_value}</small></span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Timestamp:</strong> <span>${data.timestamp}</span></li>
                        </ul>
                    </div>
                </div>`;
        }
        singleSignalResult.innerHTML = resultHtml;
    };

    const handleGenerateSignal = async () => {
        const symbol = assetSelect.value;
        const timeframe = timeframeSelect.value;
        // NEW: Get the period value
        const period = analysisPeriodInput.value;
        if (!symbol) return;

        toggleButtonSpinner(generateSignalBtn, true);
        singleSignalResult.innerHTML = '';

        try {
            // NEW: Add period to the request URL
            const apiUrl = `/api/generate_signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&period=${encodeURIComponent(period)}`;
            const response = await fetch(apiUrl);
            const data = await response.json();

            if (!response.ok) {
                showAlert(singleSignalResult, `<strong>Server Error:</strong> ${data.error}. Attempting client-side fallback...`, 'warning');
                const fallbackResult = await fallbackFetcher.getFallbackSignal(symbol);
                if (fallbackResult.success) {
                    renderSignalResult(fallbackResult, true);
                } else {
                    showAlert(singleSignalResult, `<strong>Fallback Failed:</strong> ${fallbackResult.error || 'Could not retrieve data.'}`, 'danger');
                }
            } else {
                renderSignalResult(data, false);
            }
        } catch (error) {
            showAlert(singleSignalResult, `<strong>Network Error:</strong> Could not connect to the server.`, 'danger');
        } finally {
            toggleButtonSpinner(generateSignalBtn, false);
        }
    };

    const handleScanMarket = async (e) => {
        const button = e.target;
        const assetType = button.dataset.assetType;
        const timeframe = timeframeSelect.value;
        // NEW: Get the period value
        const period = analysisPeriodInput.value;

        scanSpinner.classList.remove('d-none');
        scanResultsBody.innerHTML = '';
        
        try {
            const response = await fetch('/api/scan_market', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // NEW: Add period to the request body
                body: JSON.stringify({ asset_type: assetType, timeframe: timeframe, period: period })
            });
            const results = await response.json();
            if (!response.ok) throw new Error(results.error || 'Failed to scan market.');

            if (Array.isArray(results) && results.length > 0) {
                results.forEach(signal => {
                    const signalClass = getSignalClass(signal.signal);
                    scanResultsBody.innerHTML += `
                        <tr>
                            <td>${signal.symbol}</td>
                            <td class="${signalClass}"><i class="fas fa-circle me-2"></i>${signal.signal}</td>
                            <td>${signal.confidence}</td>
                            <td>${signal.entry_price}</td>
                            <td>${signal.stop_loss}</td>
                            <td>${signal.stop_loss_value}</td>
                            <td>${signal.timestamp}</td>
                        </tr>`;
                });
            } else {
                scanResultsBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No strong BUY/SELL signals found for this category.</td></tr>`;
            }
        } catch (error) {
            scanResultsBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error: ${error.message}</td></tr>`;
        } finally {
            scanSpinner.classList.add('d-none');
        }
    };
    
    // Unchanged setup functions
    const checkModelStatus = async () => {
        try {
            const response = await fetch('/api/check_model_status');
            const data = await response.json();
            if (!data.models_loaded) throw new Error(data.message);
            modelStatusBadge.textContent = 'Loaded';
            modelStatusBadge.className = 'badge bg-success';
            allInteractiveElements.forEach(el => el.disabled = false);
            assetSelect.disabled = true;
            generateSignalBtn.disabled = true;
        } catch (error) {
            modelStatusBadge.textContent = 'Failed';
            modelStatusBadge.className = 'badge bg-danger';
            showAlert(globalStatusAlert, `<strong>Critical Error:</strong> Could not connect to the model service. All features disabled.`, 'danger');
            allInteractiveElements.forEach(el => el.disabled = true);
        }
    };
    const handleCategoryChange = () => {
        const selectedCategory = categorySelect.value;
        assetSelect.innerHTML = '<option value="">Select Asset</option>';
        assetSelect.disabled = true;
        generateSignalBtn.disabled = true;
        if (selectedCategory && assetClasses[selectedCategory]) {
            assetClasses[selectedCategory].forEach(symbol => assetSelect.add(new Option(symbol, symbol)));
            assetSelect.disabled = false;
        }
    };
    
    // Event Listeners & Initial Load
    checkModelStatus();
    categorySelect.addEventListener('change', handleCategoryChange);
    assetSelect.addEventListener('change', () => { generateSignalBtn.disabled = !assetSelect.value; });
    generateSignalBtn.addEventListener('click', handleGenerateSignal);
    document.querySelectorAll('.scan-btn').forEach(button => button.addEventListener('click', handleScanMarket));
});
