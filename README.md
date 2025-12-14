# Polymarket AI Trading Agent

An AI-powered trading agent for Polymarket that learns from successful trader patterns and makes data-driven predictions.

## 🎯 Project Overview

This project aims to build an intelligent trading agent that:
1. **Collects** data from Polymarket's APIs (markets, trades, users)
2. **Stores** data in a well-structured Supabase database
3. **Analyzes** successful trader patterns and behaviors
4. **Learns** from historical data using machine learning
5. **Predicts** profitable trading opportunities
6. **Executes** trades automatically (future implementation)

## 📁 Project Structure

```
polymarket-agent/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── pm_dev.ipynb                # Development notebook (API exploration)
├── database_design.dbml         # Database schema (DBML format)
├── DATABASE_README.md           # Database design documentation
├── load_data_to_db.py          # ETL script for loading data
└── migrations/
    └── 001_initial_schema.sql  # SQL migration for Supabase
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv pm-venv
source pm-venv/bin/activate  # On Windows: pm-venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Set Up Supabase Database

1. Create a new project on [Supabase](https://supabase.com)
2. Go to SQL Editor in your Supabase dashboard
3. Copy and paste the contents of `migrations/001_initial_schema.sql`
4. Execute the migration

### 3. Configure Environment Variables

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key-here"
```

### 4. Load Initial Data

```bash
python load_data_to_db.py
```

This will:
- Fetch markets from Polymarket Gamma API
- Fetch recent trades from Data API
- Extract user information
- Store everything in your Supabase database
- Take initial market snapshots

## 📊 Database Schema

The database consists of 7 main tables:

### Core Tables

1. **events** - Event-level data (contains 1+ markets)
2. **markets** - Individual market data (linked to events)
3. **users** - Trader profiles with performance metrics
4. **trades** - Individual trade records
5. **user_positions** - Aggregated position tracking

### Analytics Tables

6. **market_snapshots** - Time-series price data
7. **trading_patterns** - Identified profitable patterns

### Event vs Market Structure

- **Event**: A question/scenario (e.g., "Where will Barron Trump attend college?")
  - **SMP (Single Market Product)**: 1 event → 1 market (binary yes/no)
  - **GMP (Group Market Product)**: 1 event → multiple markets (mutually exclusive outcomes)
- **Market**: A specific tradable outcome within an event (e.g., "Georgetown", "NYU", "Harvard")

See [DATABASE_README.md](DATABASE_README.md) for detailed schema documentation.

### Visualize Schema

Visit [dbdiagram.io](https://dbdiagram.io/) and paste the contents of `database_design.dbml` to see an interactive diagram.

## 📈 Data Collection

### Polymarket APIs

This project uses three main APIs:

1. **Gamma API** (`https://gamma-api.polymarket.com`)
   - Market metadata
   - Events and categorization
   - General market information

2. **Data API** (`https://data-api.polymarket.com`)
   - Trade history
   - User activity
   - Position data

3. **CLOB API** (future - requires authentication)
   - Order book data
   - Place/cancel orders
   - Real-time trading

### API Documentation

- [Polymarket Developer Docs](https://docs.polymarket.com/)
- [Gamma API Overview](https://docs.polymarket.com/developers/gamma-markets-api/overview)

## 🤖 AI Trading Strategy

### Phase 1: Data Collection ✅
- [x] Set up database schema
- [x] Connect to Polymarket APIs
- [x] Load historical data
- [ ] Set up automated data collection (cron jobs)

### Phase 2: Pattern Analysis (In Progress)
- [ ] Identify successful traders (win rate > 55%, ROI > 10%)
- [ ] Analyze entry/exit timing patterns
- [ ] Detect contrarian opportunities
- [ ] Calculate market momentum indicators
- [ ] Extract feature engineering data

### Phase 3: Model Training (TODO)
- [ ] Build prediction models (Random Forest, XGBoost, Neural Networks)
- [ ] Train on successful trader patterns
- [ ] Validate model accuracy
- [ ] Implement backtesting framework
- [ ] Optimize hyperparameters

### Phase 4: Live Trading (TODO)
- [ ] Connect to CLOB API for order execution
- [ ] Implement risk management
- [ ] Set up position sizing algorithms
- [ ] Create monitoring dashboard
- [ ] Deploy automated trading bot

## 🔍 Key Features

### User Metrics Tracked

- **Performance**: Win rate, ROI, Sharpe ratio, max drawdown
- **Behavior**: Trading frequency, risk score, preferred markets
- **Time-based**: P&L over 7d/30d/90d periods
- **Classification**: Profitable, active, whale, successful trader flags

### Market Metrics Tracked

- **Pricing**: Current prices, bid/ask spread, price changes
- **Volume**: 24hr, 1wk, 1mo, 1yr volumes (regular + CLOB)
- **Liquidity**: Current liquidity, liquidity providers
- **Activity**: Trade count, unique traders

### Trading Patterns

The system can identify patterns like:
- **Early Entry**: Entering before major price movements
- **Contrarian**: Betting against market consensus
- **Momentum**: Following established trends
- **Mean Reversion**: Betting on price corrections
- **Volatility Timing**: Optimal entry during volatility

## 📝 Usage Examples

### Analyze Successful Traders

```sql
-- Find top performing traders
SELECT 
  pseudonym,
  win_rate,
  roi_percentage,
  total_pnl,
  total_trades
FROM users
WHERE is_successful_trader = true
  AND total_trades > 100
ORDER BY roi_percentage DESC
LIMIT 10;
```

### Identify Hot Markets

```sql
-- Find high-volume active markets
SELECT 
  question,
  volume_24hr,
  liquidity_num,
  one_day_price_change,
  spread
FROM markets
WHERE active = true
  AND closed = false
ORDER BY volume_24hr DESC
LIMIT 20;
```

### Analyze Trading Patterns

```sql
-- Get trades from successful users on active markets
SELECT 
  t.datetime,
  t.side,
  t.outcome,
  t.price,
  t.size,
  m.question,
  u.pseudonym,
  u.win_rate
FROM trades t
JOIN users u ON t.proxy_wallet = u.proxy_wallet
JOIN markets m ON t.slug = m.slug
WHERE u.is_successful_trader = true
  AND m.active = true
ORDER BY t.datetime DESC;
```

## 🔧 Development

### Jupyter Notebook

The `pm_dev.ipynb` notebook contains:
- API connection examples
- Data exploration
- Initial analysis
- Prototype code

Start Jupyter:
```bash
jupyter notebook pm_dev.ipynb
```

### Database Functions

The database includes helper functions:

```sql
-- Calculate metrics for a user
SELECT calculate_user_win_rate('0x...');
SELECT calculate_user_roi('0x...');
SELECT calculate_user_total_pnl('0x...');

-- Update all user metrics
SELECT update_user_metrics();
```

### Automated Updates

Set up cron jobs for data collection:

```bash
# Update markets hourly
0 * * * * cd /path/to/project && python load_data_to_db.py

# Take snapshots every 4 hours
0 */4 * * * cd /path/to/project && python -c "from load_data_to_db import take_snapshots_for_active_markets; take_snapshots_for_active_markets()"

# Update user metrics daily
0 0 * * * cd /path/to/project && python -c "from load_data_to_db import update_all_user_metrics; update_all_user_metrics()"
```

## 📊 Monitoring & Analytics

### Key Metrics to Track

1. **Data Freshness**
   - Last market update timestamp
   - Trade ingestion lag
   - Snapshot frequency

2. **User Performance**
   - Distribution of win rates
   - Top traders by ROI
   - Trading volume trends

3. **Market Activity**
   - Active market count
   - Total volume (24hr)
   - Average spread

4. **AI Performance** (when implemented)
   - Prediction accuracy
   - Model confidence vs actual outcomes
   - Profitability of followed predictions

## 🛡️ Security & Best Practices

- ✅ Never commit API keys or credentials
- ✅ Use environment variables for sensitive data
- ✅ Implement rate limiting for API calls
- ✅ Set up Row Level Security (RLS) in Supabase
- ✅ Regular database backups
- ✅ Monitor for anomalous trading activity

## 🚧 Roadmap

### Short Term
- [ ] Automated data collection pipeline
- [ ] Basic pattern recognition algorithms
- [ ] User performance dashboard
- [ ] Market trend visualization

### Medium Term
- [ ] ML model for price prediction
- [ ] Backtesting framework
- [ ] Risk management system
- [ ] Real-time monitoring dashboard

### Long Term
- [ ] Automated trading execution
- [ ] Portfolio optimization
- [ ] Multi-model ensemble predictions
- [ ] Advanced sentiment analysis

## 📚 Resources

- [Polymarket Documentation](https://docs.polymarket.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Prediction Markets Overview](https://en.wikipedia.org/wiki/Prediction_market)
- [Trading Strategy Development](https://www.quantstart.com/)

## ⚠️ Disclaimer

This is an educational project for learning about prediction markets, data engineering, and algorithmic trading. 

**Important:**
- Prediction market trading involves financial risk
- Past performance does not guarantee future results
- Use at your own risk
- Start with small amounts for testing
- This is not financial advice

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📧 Contact

For questions or suggestions, please open an issue on GitHub.

---

**Happy Trading! 🚀📈**

