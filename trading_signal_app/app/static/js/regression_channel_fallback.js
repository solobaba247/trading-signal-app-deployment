// app/static/js/regression_channel_fallback.js

class RegressionChannelAnalyzer {
    constructor() {
        this.data = [];
        this.channelData = {};
    }

    async fetchMarketData(symbol, interval, period) {
        const targetUrl = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${interval}&range=${period}&includePrePost=false`;
        const proxies = [
            `https://api.allorigins.win/raw?url=${encodeURIComponent(targetUrl)}`,
            `https://thingproxy.freeboard.io/fetch/${targetUrl}`
        ];

        for (const proxyUrl of proxies) {
            try {
                console.log(`Fallback: Attempting to fetch via ${proxyUrl.substring(0, 40)}...`);
                const response = await fetch(proxyUrl, { signal: AbortSignal.timeout(15000) }); // 15-second timeout
                if (!response.ok) throw new Error(`Proxy responded with status: ${response.status}`);
                const data = await response.json();
                if (data.chart.error) throw new Error(`API Error: ${data.chart.error.description}`);

                const result = data.chart.result[0];
                const timestamps = result?.timestamp;
                const quote = result?.indicators?.quote?.[0];

                if (!timestamps || !quote) throw new Error('No valid data structure in API response.');

                const parsedData = timestamps.map((ts, i) => ({
                    date: new Date(ts * 1000),
                    open: quote.open[i], high: quote.high[i], low: quote.low[i],
                    close: quote.close[i], volume: quote.volume[i] || 0
                })).filter(d => d.open && d.high && d.low && d.close);

                if (parsedData.length === 0) throw new Error('No valid data points after parsing.');
                this.data = parsedData.sort((a, b) => a.date - b.date);
                return this.data;
            } catch (error) {
                console.warn(`Fallback fetch failed for ${symbol}:`, error.message);
            }
        }
        throw new Error(`All fallback data proxies failed for ${symbol}.`);
    }

    calculateRegressionChannel(regressionPeriod) {
        if (this.data.length < regressionPeriod) {
            throw new Error(`Insufficient data for fallback analysis (${this.data.length} bars found, ${regressionPeriod} needed).`);
        }
        const recentData = this.data.slice(-regressionPeriod);
        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        recentData.forEach((d, i) => {
            const y = d.close;
            sumX += i; sumY += y; sumXY += i * y; sumX2 += i * i;
        });

        const n = regressionPeriod;
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;

        let maxDeviation = 0;
        recentData.forEach((d, i) => {
            const regressionValue = intercept + slope * i;
            maxDeviation = Math.max(maxDeviation, Math.abs(d.close - regressionValue));
        });

        const endRegression = intercept + slope * (n - 1);
        this.channelData = {
            slope, maxDeviation, isUpwardSlope: slope > 0,
            C: endRegression, Ch: endRegression + maxDeviation, Cl: endRegression - maxDeviation,
        };
        this.channelData.Chead = this.channelData.isUpwardSlope ? (endRegression + this.channelData.Ch) / 2 : (endRegression + this.channelData.Cl) / 2;
        return this.channelData;
    }

    generateSignals(tradeZoneThreshold, targetZoneThreshold) {
        if (!this.channelData.C || this.data.length === 0) return [];
        
        const currentPrice = this.data[this.data.length - 1].close;
        const channelWidth = this.channelData.Ch - this.channelData.Cl;
        const refPrice = this.channelData.Chead;

        const tradeZoneHigh = refPrice + channelWidth * tradeZoneThreshold;
        const tradeZoneLow = refPrice - channelWidth * tradeZoneThreshold;
        
        const signals = [];
        let reason = 'No clear rule-based signal found. Price is within the neutral zone.';
        let signalType = 'HOLD';

        if (currentPrice > tradeZoneHigh && this.channelData.isUpwardSlope) {
            signalType = 'BUY';
            reason = 'Rule: Price broke out above the upper trade zone in an uptrend.';
        } else if (currentPrice < tradeZoneLow && !this.channelData.isUpwardSlope) {
            signalType = 'SELL';
            reason = 'Rule: Price broke out below the lower trade zone in a downtrend.';
        } else if (currentPrice >= tradeZoneLow && currentPrice <= tradeZoneHigh) {
            if (this.channelData.isUpwardSlope) {
                signalType = 'BUY';
                reason = 'Rule: Price re-entered the trade zone, offering a potential entry in an uptrend.';
            } else {
                signalType = 'SELL';
                reason = 'Rule: Price re-entered the trade zone, offering a potential entry in a downtrend.';
            }
        }
        
        return { signal: signalType, reason: reason, price: currentPrice };
    }

    async getAnalysis(symbol, interval, period, regressionPeriod) {
        try {
            await this.fetchMarketData(symbol, interval, period);
            this.calculateRegressionChannel(regressionPeriod);
            const { signal, reason, price } = this.generateSignals(0.375, 0.875); // Using default thresholds

            return {
                success: true,
                symbol: symbol,
                signal: signal,
                reason: reason,
                entry_price: price.toFixed(5),
                timestamp: new Date().toISOString().slice(0, 19).replace('T', ' '),
            };
        } catch (error) {
            console.error('Full fallback analysis failed:', error);
            return { success: false, error: error.message };
        }
    }
}
