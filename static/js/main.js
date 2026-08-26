(function () {
    'use strict';

    const API_BASE = '';
    const POLL_INTERVAL = 10000; // 10 seconds

    let currentCurrency = 'usd';
    let currencySymbol = '$';

    /* ===== Utility ===== */

    function formatPrice(val, decimals = 2) {
        if (val === null || val === undefined) return '—';
        return new Intl.NumberFormat('en-US', {
            style: 'decimal',
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(val) + ' ' + currencySymbol;
    }

    function formatAmount(val) {
        if (val === null || val === undefined) return '—';
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 8,
        }).format(val);
    }

    function showFlash(message, type = 'success') {
        const container = document.querySelector('.content') || document.body;
        const el = document.createElement('div');
        el.className = `flash ${type}`;
        el.textContent = message;
        container.prepend(el);
        setTimeout(() => el.remove(), 4000);
    }

    async function apiFetch(path, options = {}) {
        const resp = await fetch(API_BASE + path, {
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || resp.statusText);
        }
        return resp.json();
    }

    /* ===== Live Price ===== */

    let currentPrice = null;

    async function updateLivePrice() {
        try {
            const data = await apiFetch('/api/price?currency=' + currentCurrency);
            currentPrice = data.usdt_price;
            currencySymbol = data.symbol || '$';
            const badge = document.getElementById('live-price-badge');
            if (badge) {
                badge.textContent = currentPrice !== null
                    ? 'USDT: ' + currencySymbol + currentPrice.toFixed(4)
                    : 'Offline';
                badge.style.color = currentPrice !== null ? '#51cf66' : '#ff6b6b';
            }
        } catch (err) {
            const badge = document.getElementById('live-price-badge');
            if (badge) {
                badge.textContent = 'Offline';
                badge.style.color = '#ff6b6b';
            }
        }
    }

    /* ===== Currency Selector ===== */

    async function setupCurrencySelector() {
        const select = document.getElementById('currency-select');
        if (!select) return;

        // Fetch the user's saved currency from the session
        try {
            const resp = await apiFetch('/api/set-currency');
            currentCurrency = resp.currency;
            currencySymbol = resp.symbol;
        } catch (err) {
            // Use defaults (usd, $)
        }

        // Set the dropdown to the user's saved currency
        select.value = currentCurrency;

        select.addEventListener('change', async function() {
            const newCurrency = this.value;
            try {
                const resp = await apiFetch('/api/set-currency', {
                    method: 'POST',
                    body: JSON.stringify({ currency: newCurrency }),
                });
                currentCurrency = resp.currency;
                currencySymbol = resp.symbol;
                showFlash('Currency changed to ' + resp.symbol, 'success');
                // Refresh all price-dependent data
                await updateLivePrice();
                await updatePortfolioSummary();
                await updatePerformanceChart();
                // Re-init price chart with new currency
                if (priceChart) {
                    priceChart.destroy();
                    await initPriceChart(7);
                }
            } catch (err) {
                showFlash('Failed to change currency', 'error');
                select.value = currentCurrency;
            }
        });
    }

    /* ===== Price History Chart ===== */

    let priceChart = null;

    async function initPriceChart(days = 7) {
        const ctx = document.getElementById('priceChart');
        if (!ctx) return;

        const history = await apiFetch(`/api/price-history?days=${days}&currency=${currentCurrency}`);

        // If no history, show "no data" message
        const cardEl = ctx.closest('.chart-card');
        if (history.length === 0) {
            cardEl.classList.add('empty');
            cardEl.querySelector('h3').textContent = 'Price History (No Data)';
            return;
        }
        cardEl.classList.remove('empty');
        cardEl.querySelector('h3').textContent = 'Price History (7D)';

        const labels = history.map(h => {
            const d = new Date(h.timestamp * 1000);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        });
        const data = history.map(h => h.price);

        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'USDT Price',
                    data,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.08)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#00d4ff',
                    pointHoverBackgroundColor: '#00d4ff',
                    fill: true,
                    tension: 0.4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1000, easing: 'easeOutQuart' },
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#888',
                            font: { size: 11 },
                            maxTicksLimit: 6,
                        },
                        border: { display: false },
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: {
                            color: '#888',
                            font: { size: 11 },
                             callback: function(value) {
                                return currencySymbol + value.toFixed(4);
                            },
                        },
                        border: { display: false },
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#aaa', font: { size: 12 } },
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 35, 0.95)',
                        borderColor: 'rgba(0, 212, 255, 0.3)',
                        borderWidth: 1,
                        padding: 10,
                        titleColor: '#fff',
                        bodyColor: '#ccc',
                        titleFont: { size: 13 },
                        bodyFont: { size: 12 },
                        displayColors: false,
                        callbacks: {
                            label: function(ctx) {
                                return 'Price: ' + currencySymbol + ctx.parsed.y.toFixed(6);
                            },
                        },
                    },
                },
            },
        });
    }

    /* ===== Portfolio Summary ===== */

    async function updatePortfolioSummary() {
        try {
            const data = await apiFetch('/api/portfolio');

            // Update currency symbol from API response
            if (data.symbol) {
                currencySymbol = data.symbol;
            }

            // Dashboard cards
            setText('#net-holding', formatAmount(data.net_holding) + ' USDT');
            setText('#total-investment', formatPrice(data.total_investment));
            setText('#current-value', formatPrice(data.current_value));
            const pnlEl = document.getElementById('pnl');
            if (pnlEl) {
                pnlEl.textContent = formatPrice(data.pnl);
                pnlEl.className = 'card-value ' + (data.pnl >= 0 ? 'positive' : 'negative');
            }

            // Full portfolio cards
            setText('#net-holding-full', formatAmount(data.net_holding) + ' USDT');
            setText('#total-investment-full', formatPrice(data.total_investment));
            setText('#current-value-full', formatPrice(data.current_value));
            const pnlFull = document.getElementById('pnl-full');
            if (pnlFull) {
                pnlFull.textContent = formatPrice(data.pnl);
                pnlFull.className = 'card-value ' + (data.pnl >= 0 ? 'positive' : 'negative');
            }

            return data;
        } catch (err) {
            console.error('Portfolio summary error:', err);
        }
    }

    function setText(selector, text) {
        const el = document.querySelector(selector);
        if (el) el.textContent = text;
    }

    /* ===== Transactions Table ===== */

    let transactionsCache = [];

    async function loadTransactions() {
        try {
            transactionsCache = await apiFetch('/api/transactions');
            renderTransactions(transactionsCache);
        } catch (err) {
            console.error('Transactions load error:', err);
        }
    }

    function renderTransactions(txns) {
        const tbody = document.querySelector('#transactions-table tbody');
        const tbodyFull = document.querySelector('#transactions-table-full tbody');
        const recent = document.querySelector('#recent-transactions tbody');

        const render = (container) => {
            if (!container) return;
            container.innerHTML = '';
            txns.forEach(t => {
                const tr = document.createElement('tr');
                const value = currencySymbol + (t.amount * t.buy_price).toFixed(2);
                const typeClass = t.transaction_type === 'BUY' ? 'positive' : 'negative';
                tr.innerHTML = `
                    <td>${t.transaction_date}</td>
                    <td class="${typeClass}">${t.transaction_type}</td>
                    <td>${formatAmount(t.amount)}</td>
                    <td>${formatPrice(t.buy_price, 6)}</td>
                    <td>${value}</td>
                    <td class="actions-cell">
                        <button class="btn btn-outline btn-sm" onclick="editTransaction(${t.id})">Edit</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteTransaction(${t.id})">Delete</button>
                    </td>
                `;
                container.appendChild(tr);
            });
        };

        render(tbody);
        render(tbodyFull);

        // Recent on dashboard
        if (recent) {
            recent.innerHTML = '';
            txns.slice(0, 5).forEach(t => {
                const tr = document.createElement('tr');
                const typeClass = t.transaction_type === 'BUY' ? 'positive' : 'negative';
                tr.innerHTML = `
                    <td class="${typeClass}">${t.transaction_type}</td>
                    <td>${formatAmount(t.amount)}</td>
                    <td>${formatPrice(t.buy_price, 6)}</td>
                    <td>${t.transaction_date}</td>
                `;
                recent.appendChild(tr);
            });
        }
    }

    /* ===== Add Transaction ===== */

    function setupAddModal() {
        const openBtn = document.getElementById('open-add-modal');
        const modal = document.getElementById('add-modal');
        const closeBtn = document.getElementById('add-modal-close');
        const form = document.getElementById('add-transaction-form');

        if (openBtn) openBtn.addEventListener('click', () => modal.style.display = 'block');
        if (closeBtn) closeBtn.addEventListener('click', () => modal.style.display = 'none');

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (modal && modal.style.display === 'block') modal.style.display = 'none';
                const editModal = document.getElementById('edit-modal');
                if (editModal && editModal.style.display === 'block') editModal.style.display = 'none';
            }
        });

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const payload = {
                    transaction_type: formData.get('transaction_type'),
                    amount: formData.get('amount'),
                    buy_price: formData.get('buy_price'),
                    transaction_date: formData.get('transaction_date'),
                };
                try {
                    await apiFetch('/api/transactions', { method: 'POST', body: JSON.stringify(payload) });
                    showFlash('Transaction added successfully', 'success');
                    form.reset();
                    form.querySelector('[name="transaction_date"]').valueAsDate = new Date();
                    modal.style.display = 'none';
                    await loadTransactions();
                    await updatePortfolioSummary();
                    await updatePerformanceChart();
                } catch (err) {
                    showFlash(err.message || 'Failed to add transaction', 'error');
                }
            });
        }

        // Set default date on modal open
        if (openBtn && form) {
            openBtn.addEventListener('click', () => {
                form.querySelector('[name="transaction_date"]').valueAsDate = new Date();
            });
        }
    }

    /* ===== Edit / Delete Transaction ===== */

    window.editTransaction = async function (id) {
        const txn = transactionsCache.find(t => t.id === id);
        if (!txn) return;

        const modal = document.getElementById('edit-modal');
        const form = document.getElementById('edit-transaction-form');
        if (!modal || !form) return;

        form.querySelector('[name="id"]').value = txn.id;
        form.querySelector('[name="transaction_type"]').value = txn.transaction_type;
        form.querySelector('[name="amount"]').value = txn.amount;
        form.querySelector('[name="buy_price"]').value = txn.buy_price;
        form.querySelector('[name="transaction_date"]').value = txn.transaction_date;
        modal.style.display = 'block';
    };

    window.deleteTransaction = async function (id) {
        if (!confirm('Delete this transaction?')) return;
        try {
            await fetch(API_BASE + `/api/transactions/${id}`, {
                method: 'DELETE',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
            });
            showFlash('Transaction deleted', 'success');
            await loadTransactions();
            await updatePortfolioSummary();
            await updatePerformanceChart();
        } catch (err) {
            showFlash(err.message || 'Failed to delete', 'error');
        }
    };

    function setupEditModal() {
        const closeBtn = document.getElementById('edit-modal-close');
        const modal = document.getElementById('edit-modal');
        const form = document.getElementById('edit-transaction-form');
        const deleteBtn = document.getElementById('delete-transaction-btn');

        if (closeBtn) closeBtn.addEventListener('click', () => modal.style.display = 'none');

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = form.querySelector('[name="id"]').value;
                const payload = {
                    transaction_type: form.querySelector('[name="transaction_type"]').value,
                    amount: form.querySelector('[name="amount"]').value,
                    buy_price: form.querySelector('[name="buy_price"]').value,
                    transaction_date: form.querySelector('[name="transaction_date"]').value,
                };
                try {
                    await fetch(API_BASE + `/api/transactions/${id}`, {
                        method: 'PUT',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    showFlash('Transaction updated', 'success');
                    modal.style.display = 'none';
                    await loadTransactions();
                    await updatePortfolioSummary();
                    await updatePerformanceChart();
                } catch (err) {
                    showFlash(err.message || 'Failed to update', 'error');
                }
            });
        }

        if (deleteBtn) {
            deleteBtn.addEventListener('click', async () => {
                const id = form.querySelector('[name="id"]').value;
                if (confirm('Delete this transaction?')) {
                    try {
                        await fetch(API_BASE + `/api/transactions/${id}`, {
                            method: 'DELETE',
                            credentials: 'same-origin',
                            headers: { 'Content-Type': 'application/json' },
                        });
                        showFlash('Transaction deleted', 'success');
                        modal.style.display = 'none';
                        await loadTransactions();
                        await updatePortfolioSummary();
                        await updatePerformanceChart();
                    } catch (err) {
                        showFlash(err.message || 'Failed to delete', 'error');
                    }
                }
            });
        }
    }

    /* ===== Performance Chart ===== */

    let performanceChart = null;
    let performanceChartFull = null;

    async function updatePerformanceChart() {
        try {
            const data = await apiFetch('/api/performance');
            const timeline = data.timeline || [];

            const commonConfig = (labels, values, label) => ({
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label,
                        data: values,
                        borderColor: '#51cf66',
                        backgroundColor: 'rgba(81, 207, 102, 0.10)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        pointBackgroundColor: '#51cf66',
                        pointHoverBackgroundColor: '#51cf66',
                        fill: true,
                        tension: 0.4,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 1000, easing: 'easeOutQuart' },
                    interaction: { intersect: false, mode: 'index' },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#888',
                                font: { size: 11 },
                                maxRotation: 30,
                                autoSkip: true,
                                maxTicksLimit: 6,
                            },
                            border: { display: false },
                        },
                        y: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#888',
                                font: { size: 11 },
                                callback: function(value) {
                                    return currencySymbol + value.toFixed(0);
                                },
                            },
                            border: { display: false },
                        },
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#aaa', font: { size: 12 } },
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 15, 35, 0.95)',
                            borderColor: 'rgba(81, 207, 102, 0.3)',
                            borderWidth: 1,
                            padding: 10,
                            titleColor: '#fff',
                            bodyColor: '#ccc',
                            titleFont: { size: 13 },
                            bodyFont: { size: 12 },
                            displayColors: false,
                            callbacks: {
                                label: function(ctx) {
                                    return 'Value: ' + currencySymbol + ctx.parsed.y.toFixed(2);
                                },
                            },
                        },
                    },
                },
            });

            if (timeline.length > 0) {
                const labels = timeline.map(t => t.date);
                const values = timeline.map(t => t.value);

                const updateChart = (ctx, destVar) => {
                    if (!ctx) return;
                    if (window[destVar]) window[destVar].destroy();
                    window[destVar] = new Chart(ctx, commonConfig(labels, values, 'Portfolio Value (USD)'));
                    const card = ctx.closest('.chart-card');
                    card.classList.remove('empty');
                    card.querySelector('h3').textContent = 'Portfolio Value Over Time';
                };

                updateChart(document.getElementById('performanceChart'), 'performanceChart');
                updateChart(document.getElementById('performanceChartFull'), 'performanceChartFull');
            } else {
                const cards = [
                    { el: document.getElementById('performanceChart'), title: 'Portfolio Performance' },
                    { el: document.getElementById('performanceChartFull'), title: 'Portfolio Value Over Time' },
                ];
                cards.forEach(c => {
                    if (c.el) {
                        const card = c.el.closest('.chart-card');
                        if (card) {
                            card.classList.add('empty');
                            card.querySelector('h3').textContent = c.title + ' (No Transactions)';
                        }
                    }
                });
            }
        } catch (err) {
            console.error('Performance chart error:', err);
        }
    }

    /* ===== Password Toggle ===== */

    function setupPasswordToggle() {
        const toggles = document.querySelectorAll('.password-toggle');
        toggles.forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                const wrapper = this.parentElement;
                const input = wrapper.querySelector('input');
                const icon = this.querySelector('.eye-icon');
                const isVisible = icon.getAttribute('data-visible') === 'true';

                if (isVisible) {
                    input.type = 'password';
                    icon.setAttribute('data-visible', 'false');
                    icon.textContent = '👁️';
                } else {
                    input.type = 'text';
                    icon.setAttribute('data-visible', 'true');
                    icon.textContent = '🙈';
                }
            });
        });
    }

    /* ===== Init ===== */

    async function initDashboard() {
        await updateLivePrice();
        await initPriceChart(7);
        await updatePortfolioSummary();
        await loadTransactions();
        await updatePerformanceChart();

        // Polling
        setInterval(updateLivePrice, POLL_INTERVAL);
        setInterval(updatePortfolioSummary, POLL_INTERVAL);
    }

    async function initPortfolio() {
        await updateLivePrice();
        await updatePortfolioSummary();
        await loadTransactions();
        await updatePerformanceChart();

        setInterval(updateLivePrice, POLL_INTERVAL);
        setInterval(updatePortfolioSummary, POLL_INTERVAL);
    }

    async function initTransactions() {
        await updateLivePrice();
        await loadTransactions();

        setInterval(updateLivePrice, POLL_INTERVAL);
    }

    /* ===== P/L Calculator ===== */

    async function fetchCurrentPrice() {
        try {
            const data = await apiFetch('/api/price');
            return data.usdt_price;
        } catch (err) {
            return null;
        }
    }

    async function updateResultClasses() {
        const elements = document.querySelectorAll('.pl-value');
        elements.forEach(el => {
            const text = el.textContent || '';
            if (text.startsWith('-')) {
                el.className = 'pl-value negative';
             } else if (text.startsWith(currencySymbol) && parseFloat(text.slice(currencySymbol.length)) > 0) {
                el.className = 'pl-value positive';
            } else {
                el.className = 'pl-value';
            }
        });
    }

    async function calculatePL(e) {
        e.preventDefault();
        const buyPrice = parseFloat(document.getElementById('buy_price').value);
        const sellPrice = parseFloat(document.getElementById('sell_price').value);
        const quantity = parseFloat(document.getElementById('quantity').value);

        if (!buyPrice || !sellPrice || !quantity) {
            showFlash('Please fill in all fields', 'error');
            return;
        }

        const payload = {
            buy_price: buyPrice,
            sell_price: sellPrice,
            quantity: quantity,
        };

        const targetInput = document.getElementById('target_price_input');
        if (targetInput.value) {
            payload.target_price = parseFloat(targetInput.value);
        }

        try {
            const result = await apiFetch('/api/calculate-pl', {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            document.getElementById('buy-cost').textContent = currencySymbol + result.buy_cost.toFixed(2);
            document.getElementById('sell-revenue').textContent = currencySymbol + result.sell_revenue.toFixed(2);

            const plAmount = document.getElementById('pl-amount');
            plAmount.textContent = currencySymbol + result.pnl.toFixed(2);
            plAmount.className = 'pl-value ' + (result.pnl >= 0 ? 'positive' : 'negative');

            const plPercent = document.getElementById('pl-percent');
            plPercent.textContent = result.pnl_percent.toFixed(2) + '%';
            plPercent.className = 'pl-value ' + (result.pnl_percent >= 0 ? 'positive' : 'negative');

            document.getElementById('break-even').textContent = currencySymbol + result.break_even_price.toFixed(6);

            const projectionEl = document.getElementById('pl-projection');
            if (result.projected_pnl !== undefined) {
                document.getElementById('pl-projection-amount').textContent = currencySymbol + result.projected_pnl.toFixed(2);
                document.getElementById('pl-projection-amount').className = 'pl-projection-value ' + (result.projected_pnl >= 0 ? 'positive' : 'negative');
                document.getElementById('pl-projection-percent').textContent = result.projected_pnl_percent.toFixed(2) + '%';
                document.getElementById('pl-projection-percent').className = 'pl-value ' + (result.projected_pnl_percent >= 0 ? 'positive' : 'negative');
                projectionEl.style.display = 'block';
            } else {
                projectionEl.style.display = 'none';
            }

            document.getElementById('pl-result').style.display = 'block';

            await updateResultClasses();
        } catch (err) {
            showFlash(err.message || 'Calculation failed', 'error');
        }
    }

    async function useLivePrice(fieldId) {
        const price = await fetchCurrentPrice();
        if (price !== null) {
            document.getElementById(fieldId).value = price;
            // If target price is still calculating, re-run if all fields filled
            const targetInput = document.getElementById('target_price_input');
            if (targetInput.value) {
                const event = new Event('input', { bubbles: true });
                targetInput.dispatchEvent(event);
            }
        } else {
            showFlash('Could not fetch live price', 'error');
        }
    }

    function setupPLCalculator() {
        const form = document.getElementById('pl-calculator-form');
        if (form) {
            form.addEventListener('submit', calculatePL);
        }

        const autoBuyBtn = document.getElementById('auto-buy-price');
        if (autoBuyBtn) {
            autoBuyBtn.addEventListener('click', () => useLivePrice('buy_price'));
        }

        const autoSellBtn = document.getElementById('auto-sell-price');
        if (autoSellBtn) {
            autoSellBtn.addEventListener('click', () => useLivePrice('sell_price'));
        }

        const targetInput = document.getElementById('target_price_input');
        if (targetInput) {
            targetInput.addEventListener('input', function() {
                const buyPrice = parseFloat(document.getElementById('buy_price').value);
                const sellPrice = parseFloat(document.getElementById('sell_price').value);
                const quantity = parseFloat(document.getElementById('quantity').value);
                const targetPrice = parseFloat(this.value);

                if (buyPrice && sellPrice && quantity && targetPrice) {
                    const projectedPL = (targetPrice - buyPrice) * quantity;
                    const projectedPercent = (projectedPL / (buyPrice * quantity)) * 100;
                    document.getElementById('pl-projection-amount').textContent = currencySymbol + projectedPL.toFixed(2);
                    document.getElementById('pl-projection-amount').className = 'pl-projection-value ' + (projectedPL >= 0 ? 'positive' : 'negative');
                    document.getElementById('pl-projection-percent').textContent = projectedPercent.toFixed(2) + '%';
                    document.getElementById('pl-projection-percent').className = 'pl-value ' + (projectedPercent >= 0 ? 'positive' : 'negative');
                    document.getElementById('pl-projection').style.display = 'block';
                    document.getElementById('pl-result').style.display = 'block';
                } else {
                    document.getElementById('pl-projection').style.display = 'none';
                }
            });
        }
    }

    function initPage() {
        setupAddModal();
        setupEditModal();
        setupPasswordToggle();
        setupCurrencySelector();

        // Determine which page we're on
        if (document.getElementById('priceChart')) {
            initDashboard();
        } else if (document.getElementById('performanceChartFull')) {
            initPortfolio();
        } else if (document.getElementById('transactions-table-full')) {
            initTransactions();
        } else if (document.getElementById('pl-calculator-form')) {
            setupPLCalculator();
            updateLivePrice();
            setInterval(updateLivePrice, POLL_INTERVAL);
        } else {
            updateLivePrice();
            setInterval(updateLivePrice, POLL_INTERVAL);
        }
    }

    document.addEventListener('DOMContentLoaded', initPage);
})();
