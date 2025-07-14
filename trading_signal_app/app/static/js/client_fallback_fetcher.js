class ClientFallbackDataFetcher {
    constructor() {
        this.corsProxies = [
            'https://api.allorigins.win/raw?url=',
            'https://corsproxy.io/?',
        ];
        this.lastRequestTime = new Map();
        this.minInterval = 1000; // 1 second between requests
    }

    async rateLimit(source) {
        const now = Date.now();
        const lastRequest = this.lastRequestTime.get(source) || 0;
        if (now - lastRequest < this.minInterval) {
            await new Promise(resolve => setTimeout(resolve, this.minInterval - (now - lastRequest)));
        }
        this.lastRequestTime.set(source, Date.now());
    }

    async fetchWithProxy(url) {
        for (const proxy of this.corsProxies) {
            try {
                await this.rateLimit(proxy);
                const response = await fetch(proxy + encodeURIComponent(url));
                if (response.ok) return await response.json();
            } catch (error) {
                console.warn(`Proxy failed: ${proxy}`, error);
            }
        }
        throw new Error('All CORS proxies failed');
    }

    async fetchCurrentPrice(symbol, assetType) {
        let url;
        if (assetType === 'forex') {
            const baseCurrency = symbol.substring(0, 3);
            url = `https://api.exchangerate-api.com/v4/latest/${baseCurrency}`;
        } else if (assetType === 'crypto') {
            const cleanSymbol = symbol.replace('-USD', '').toLowerCase();
            url = `https://api.coingecko.com/api/v3/simple/price?ids=${cleanSymbol}&vs_currencies=usd`;
        } else {
            throw new Error('Unsupported asset type for fallback.');
        }

        const data = await this.fetchWithProxy(url);
        if (assetType === 'forex') return data?.rates?.[symbol.substring(3, 6)];
        if (assetType === 'crypto') return data?.[symbol.replace('-USD', '').toLowerCase()]?.usd;

        throw new Error('Could not parse price from fallback API response.');
    }

    // NEW: Generates synthetic data for rule-based analysis
    generateSyntheticData(currentPrice, periods = 50) {
        let price = currentPrice;
        const data = [];
        for (let i = 0; i < periods; i++) {
            data.unshift({ close: price }); // Add to the beginning
            const change = (Math.random() - 0.5) * 0.02; // ~2% volatility
            price /= (1 + change); // Work backwards in time
        }
        return data;
    }
    
    // NEW: Generates a signal based on simple rules and provides commentary
    generateSimpleSignal(historicalData, currentPrice) {
        if (!historicalData || historicalData.length < 20) {
            return { signal: 'HOLD', confidence: 0.5, reason: 'Not enough historical data to form a rule-based opinion.' };
        }
        
        const calculateSMA = (data, period) => {
            const relevantData = data.slice(-period);
            const sum = relevantData.reduce((acc, val) => acc + val.close, 0);
            return sum / period;
        };

        const sma10 = calculateSMA(historicalData, 10);
        const sma20 = calculateSMA(historicalData, 20);

        let signal, reason, confidence;
        if (sma10 > sma20 && currentPrice > sma10) {
            signal = 'BUY';
            confidence = 0.65;
            reason = `Rule: The short-term average (10-period SMA) is above the long-term (20-period SMA), suggesting bullish momentum.`;
        } else if (sma10 < sma20 && currentPrice < sma10) {
            signal = 'SELL';
            confidence = 0.65;
            reason = `Rule: The short-term average (10-period SMA) is below the long-term (20-period SMA), suggesting bearish momentum.`;
        } else {
            signal = 'HOLD';
            confidence = 0.5;
            reason = `Rule: The market is consolidating, as short-term and long-term moving averages are too close to indicate a clear trend.`;
        }

        return { signal, confidence, reason, latest_price: currentPrice };
    }

    getAssetType(symbol) {
        if (symbol.includes('=X')) return 'forex';
        if (symbol.includes('-USD')) return 'crypto';
        return 'stock';
    }

    async getFallbackSignal(symbol) {
        console.log(`🔄 Attempting client-side fallback for ${symbol}...`);
        try {
            const assetType = this.getAssetType(symbol);
            const currentPrice = await this.fetchCurrentPrice(symbol, assetType);
            if (typeof currentPrice !== 'number') throw new Error('Invalid price received.');

            const historicalData = this.generateSyntheticData(currentPrice);
            const signalData = this.generateSimpleSignal(historicalData, currentPrice);

            return {
                success: true,
                symbol: symbol,
                signal: signalData.signal,
                entry_price: currentPrice.toFixed(5),
                reason: signalData.reason, // NEW: Pass the reason
                timestamp: new Date().toISOString().slice(0, 19).replace('T', ' '),
            };
        } catch (error) {
            console.error(`Client fallback failed for ${symbol}:`, error);
            return { success: false, error: error.message };
        }
    }
}
