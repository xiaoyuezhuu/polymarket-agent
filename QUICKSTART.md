# Quick Start Guide

Get your Polymarket AI Trading Agent up and running in 15 minutes!

## 📋 Prerequisites

- Python 3.8+ installed
- A Supabase account (free tier works fine)
- Internet connection

## 🚀 Step-by-Step Setup

### 1. Clone and Setup Environment (2 min)

```bash
cd /Users/xiaoyue/repo/xiaoyuezhuu/polymarket-agent

# Create virtual environment
python3 -m venv pm-venv

# Activate it
source pm-venv/bin/activate  # On Windows: pm-venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Create Supabase Database (5 min)

1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project (give it a name like "polymarket-agent")
3. Wait for project to finish initializing (~2 minutes)
4. Go to **SQL Editor** in left sidebar
5. Click **New Query**
6. Copy entire contents of `migrations/001_initial_schema.sql`
7. Paste and click **Run** (or press Cmd+Enter)
8. Wait for success message ✅

### 3. Get Your Supabase Credentials (1 min)

1. In Supabase, go to **Project Settings** (gear icon)
2. Click **API** in left menu
3. Copy the **URL** (looks like: `https://xxxxx.supabase.co`)
4. Copy the **anon public** key (long string starting with `eyJ...`)

### 4. Set Environment Variables (1 min)

**On Mac/Linux:**
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key-here"
```

**On Windows (Command Prompt):**
```cmd
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_KEY=your-anon-key-here
```

**On Windows (PowerShell):**
```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_KEY="your-anon-key-here"
```

**Permanent Setup (Recommended):**
Add to `~/.zshrc` or `~/.bashrc`:
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key-here"
```

### 5. Load Initial Data (5 min)

```bash
python load_data_to_db.py
```

This will:
- ✅ Fetch 1000 markets from Polymarket
- ✅ Load 5000 recent trades
- ✅ Extract user information
- ✅ Take market snapshots
- ✅ Calculate initial user metrics

Expected output:
```
============================================================
Polymarket Data Loader
============================================================

1. Loading markets...
Fetching markets (limit=1000, active_only=False)...
Fetched 1000 markets
Upserting markets to database...
Upserted 1000 markets

2. Loading recent trades...
Fetching trades (limit=5000)...
Fetched 5000 trades
Found 1234 unique users
Upserted 1234 users
Inserted 5000 trades

3. Taking market snapshots...
Found 587 active markets
Took 587 market snapshots

4. Updating user metrics...
User metrics updated successfully

============================================================
Data loading complete!
============================================================
```

### 6. Verify Data (1 min)

Go back to Supabase and run some test queries:

```sql
-- Check markets
SELECT COUNT(*) FROM markets;

-- Check trades
SELECT COUNT(*) FROM trades;

-- Check users
SELECT COUNT(*) FROM users;

-- See top traders
SELECT pseudonym, win_rate, roi_percentage, total_trades
FROM users
WHERE total_trades > 10
ORDER BY roi_percentage DESC
LIMIT 10;
```

## 🎉 You're Ready!

Now you can:

### Explore Data in Jupyter
```bash
jupyter notebook pm_dev.ipynb
```

### Analyze Trading Patterns
```bash
python analyze_patterns.py
```

### Check Database Visually
1. Go to [dbdiagram.io](https://dbdiagram.io/)
2. Copy contents of `database_design.dbml`
3. Paste and visualize your schema

## 📊 Next Steps

### Daily Data Updates

Set up a cron job (Mac/Linux) or Task Scheduler (Windows):

```bash
# Update every 6 hours
0 */6 * * * cd /path/to/polymarket-agent && /path/to/pm-venv/bin/python load_data_to_db.py
```

### Build Your First Analysis

1. Open `pm_dev.ipynb`
2. Query your database:
   ```python
   from supabase import create_client
   import os
   
   supabase = create_client(
       os.environ['SUPABASE_URL'],
       os.environ['SUPABASE_KEY']
   )
   
   # Get successful traders
   result = supabase.table('users').select('*').gte('win_rate', 60).execute()
   print(result.data)
   ```

### Start Building Your AI Model

1. Identify successful traders (win rate > 55%)
2. Analyze their trading patterns
3. Extract features (timing, position size, market selection)
4. Train a prediction model
5. Backtest your strategy

## 🐛 Troubleshooting

### "Module not found" Error
```bash
pip install --upgrade -r requirements.txt
```

### "Connection Error" to Supabase
- Check your `SUPABASE_URL` is correct (no trailing slash)
- Verify `SUPABASE_KEY` is the **anon public** key (not service role)
- Make sure your Supabase project is active

### "Permission Denied" Error
- Make sure Row Level Security (RLS) is **disabled** for initial setup
- In Supabase: Go to each table → Policies → Disable RLS temporarily

### "No Data Returned"
- Check if API is working: `curl https://gamma-api.polymarket.com/markets?limit=1`
- Verify database tables exist: Check Supabase Table Editor
- Run `load_data_to_db.py` again

### Rate Limiting
If you see 429 errors:
- Reduce the `limit` parameters
- Add delays between requests
- Use smaller batch sizes

## 💡 Pro Tips

1. **Start Small**: Load 100 markets first to test everything works
2. **Monitor Costs**: Supabase free tier has limits, monitor your usage
3. **Backup Data**: Export your database regularly
4. **Version Control**: Don't commit your `.env` file with credentials!
5. **Test Queries**: Use Supabase SQL Editor to test queries before Python

## 📚 Learn More

- [Database Schema Documentation](DATABASE_README.md)
- [Full Project README](README.md)
- [Polymarket API Docs](https://docs.polymarket.com/)

## 🆘 Need Help?

- Check the [DATABASE_README.md](DATABASE_README.md) for detailed schema info
- Review example queries in the README
- Check Supabase logs for errors
- Verify environment variables are set correctly

---

**Ready to build your AI trading agent! 🤖📈**

