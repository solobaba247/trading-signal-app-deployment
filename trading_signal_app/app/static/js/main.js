document.addEventListener('DOMContentLoaded', () => {
    const fallbackAnalyzer = new RegressionChannelAnalyzer();

    const modelStatusBadge = document.getElementById('model-status-badge');
    const globalStatusAlert = document.getElementById('global-status-alert');
    const timeframeSelect = document.getElementById('timeframe-select');
    const analysisPeriodInput = document.getElementById('analysis-period-input');
    const regressionPeriodInput = document.getElementById('regression-period-input');
    const categorySelect = document.getElementById('pair-category');
    const assetSelect = document.getElementById('asset-symbol');
    const generateSignalBtn = document.getElementById('generate-signal-btn');
    const singleSignalResult = document.getElementById('single-signal-result');
    
    const allInteractiveElements = [timeframeSelect, analysisPeriodInput, regressionPeriodInput, categorySelect, assetSelect, generateSignalBtn];

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
                         <p class="card-text text-muted">The primary ML model failed. The following is a simplified, rule-based analysis.</p>
                         <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between"><strong>Signal:</strong> <span class="${signalClass} fw-bold">${data.signal}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Current Price:</strong> <span>${data.entry_price}</span></li>
                            <li class="list-group-item d-flex justify-content-between"><strong>Timestamp:</strong> <span>${data.timestamp}</span></li>
                        </ul>
                    </div>
                    <div class="card-footer bg-transparent text-muted small">
                        <strong>Reasoning:</strong> ${data.reason || 'No specific reason provided.'}
                    </div>
                </div>`;
        } else if (data.signal === "HOLD") {
            resultHtml = `<div class="card bg-secondary-subtle text-center p-3">... HOLD signal content ...</div>`;
        } else { // ML Signal
            const cardBorder = data.signal === 'BUY' ? 'border-success' : 'border-danger';
            resultHtml = `
                <div class="card ${cardBorder}">
                    <div class="card-header bg-transparent d-flex justify-content-between align-items-center">
                        <h5 class="mb-0 ${signalClass}"><i class="fas fa-brain me-2"></i>${data.signal} SIGNAL (ML)</h5>
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
        const mlPeriod = analysisPeriodInput.value;
        const regressionPeriod = regressionPeriodInput.value;
        if (!symbol) return;

        toggleButtonSpinner(generateSignalBtn, true);
        singleSignalResult.innerHTML = '';

        try {
            const apiUrl = `/api/generate_signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&period=${encodeURIComponent(mlPeriod)}`;
            const response = await fetch(apiUrl);
            const data = await response.json();

            if (!response.ok) throw new Error(data.error || 'Server responded with an error.');
            
            renderSignalResult(data, false); // Success from ML model

        } catch (error) {
            console.warn(`ML Server failed: ${error.message}. Triggering rule-based fallback.`);
            showAlert(globalStatusAlert, `<strong>ML Server Failed:</strong> ${error.message}. Attempting rule-based fallback...`, 'warning');
            
            // This is the fallback logic
            const fallbackResult = await fallbackAnalyzer.getAnalysis(symbol, timeframe, '3mo', regressionPeriod); // Use a fixed '3mo' period for fallback
            
            if (fallbackResult.success) {
                renderSignalResult(fallbackResult, true); // Render with fallback styling
            } else {
                showAlert(singleSignalResult, `<strong>Total Failure:</strong> The ML server and the rule-based fallback both failed. <br><strong>Reason:</strong> ${fallbackResult.error}`, 'danger');
            }
        } finally {
            toggleButtonSpinner(generateSignalBtn, false);
        }
    };
    
    // --- Setup and Event Listeners ---
    const checkModelStatus = async () => { /* ... unchanged ... */ };
    const handleCategoryChange = () => { /* ... unchanged ... */ };
    
    checkModelStatus();
    categorySelect.addEventListener('change', handleCategoryChange);
    assetSelect.addEventListener('change', () => { generateSignalBtn.disabled = !assetSelect.value; });
    generateSignalBtn.addEventListener('click', handleGenerateSignal);
});
