# Hevy Workout Dashboard

A beautiful, feature-rich dashboard for tracking and analyzing your Hevy workout data.

![Dashboard](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue)

## Features

### 📊 Data Visualization
- **GitHub-style Heatmap** - View your workout consistency over the past year
- **Summary Statistics** - Total workouts, exercises, sets, and volume
- **Top Exercises** - See your most frequently performed exercises
- **Active Weeks Tracking** - Current and longest active streaks

### 🔄 Data Sync
- **Automatic Syncing** - Fetches new workouts every 15 minutes
- **Manual Sync** - One-click sync button for immediate updates
- **Full Backfill** - Import your entire workout history
- **Reset & Re-sync** - Fresh start with one click

### 🏋️ Workout Tracking
- 187 workouts synced
- 100 unique exercises
- 2,867+ sets logged
- 831,220+ lbs total volume

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Hevy API Key ([Get one here](https://api.hevyapp.com/))

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd /home/trent/github/hevy
   ```

2. **Create `.env` file:**
   ```bash
   cat > .env << EOF
   HEVY_API_KEY=your_api_key_here
   HEVY_AUTH_SCHEME=api-key
   DATABASE_URL=sqlite+aiosqlite:///./hevy.db
   EOF
   ```

3. **Start the application:**
   ```bash
   docker compose up -d
   ```

4. **Open dashboard:**
   ```
   http://localhost:5050
   ```

5. **Backfill your data:**
   - Navigate to Admin: `http://localhost:5050/admin`
   - Click the "📥 Backfill All" button to import your workout history
   - Wait ~10 seconds and return to the main dashboard

## Usage

### Starting the Application
```bash
docker compose up -d
```

### Viewing Logs
```bash
docker compose logs -f hevy
```

### Stopping the Application
```bash
docker compose down
```

### Rebuilding After Code Changes
```bash
docker compose up -d --build
```

## Dashboard

The application has two main pages:

### 🏋️ Main Dashboard (`/`)
Clean, focused view of your workout data:
- **📊 Summary Statistics** - 6 key metrics at a glance
- **📅 Workout Heatmap** - GitHub-style contribution calendar
- **🏆 Top Exercises** - Most frequently performed exercises

### ⚙️ Admin Panel (`/admin`)
Management and configuration tools:
- **🔄 Data Sync** - Manual sync, backfill, and reset controls
- **🏥 Health Check** - API connectivity testing
- **🔌 API Endpoints** - Direct access to data APIs
- **📋 Configuration** - System settings overview
- **📚 Documentation** - Quick command reference

## API Endpoints

### Frontend Pages
- `GET /` - Main dashboard
- `GET /admin` - Admin panel

### Sync Actions (Admin)
- `POST /sync-now` - Sync latest workouts
- `POST /sync-all` - Backfill all workout history
- `POST /reset-db` - Reset database and re-sync

### Data APIs
- `GET /api/summary` - Overall statistics
- `GET /api/heatmap-year` - Workout frequency data
- `GET /api/top-exercises?limit=10` - Most frequent exercises

### Debug & Health
- `GET /healthz` - Health check
- `GET /api/debug/hevy` - Test Hevy API connection
- `GET /api/debug/auth` - Check authentication config
- `GET /api/debug/backfill` - Test workout fetching

## Architecture

```
┌─────────────────┐
│   Dashboard UI  │
│  (index.html)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   FastAPI App   │
│   (main.py)     │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬─────────┐
    ▼         ▼          ▼         ▼
┌────────┐ ┌───────┐ ┌──────┐ ┌─────────┐
│ Stats  │ │ Sync  │ │ Hevy │ │ SQLite  │
│Service │ │Service│ │Client│ │Database │
└────────┘ └───────┘ └──────┘ └─────────┘
                        │
                        ▼
                  ┌──────────┐
                  │ Hevy API │
                  └──────────┘
```

## Database Schema

### Tables
- **workout** - Workout sessions (id, started_at, ended_at, notes)
- **exercise** - Exercise definitions (id, name)
- **workout_exercise** - Workout-Exercise relationships
- **setlog** - Individual sets (weight_kg, reps, rpe)

## Configuration

### Environment Variables
- `HEVY_API_KEY` - Your Hevy API key (required)
- `HEVY_AUTH_SCHEME` - Authentication scheme (default: `api-key`)
- `DATABASE_URL` - SQLite database path (default: `sqlite+aiosqlite:///./hevy.db`)

### Port Configuration
The application runs on port **5050** by default. To change:
1. Edit `docker-compose.yml` ports section
2. Edit `Dockerfile` EXPOSE directive
3. Edit `CMD` in Dockerfile

## Troubleshooting

### Dashboard shows 0 workouts
1. Check API key in `.env` file
2. Go to Admin panel: `http://localhost:5050/admin`
3. Click "📥 Backfill All" button
4. Wait ~10 seconds and refresh the main dashboard
5. Check logs: `docker compose logs hevy`
6. Visit debug endpoint: `http://localhost:5050/api/debug/hevy`

### Sync button returns error
1. Verify API key is valid in `.env`
2. Check network connection
3. Review logs for specific error: `docker compose logs hevy`
4. Try "🗑️ Reset & Re-sync" button in Admin panel

### Container won't start
1. Check Docker is running
2. Verify port 5050 is available: `lsof -i :5050`
3. Check logs: `docker compose logs hevy`
4. Rebuild: `docker compose up -d --build`

## Development

### Local Development (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Run application
uvicorn app.main:app --reload --port 5050
```

### Running Tests
```bash
# TODO: Add unit tests
```

### Code Structure
```
hevy/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── db.py                # Database connection
│   ├── settings.py          # Configuration
│   └── services/
│       ├── hevy_client.py   # Hevy API client
│       ├── sync.py          # Sync logic
│       ├── stats.py         # Statistics
│       └── debug.py         # Debug endpoints
├── templates/
│   └── index.html           # Dashboard UI
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

## Roadmap

### Planned Features
- [ ] Exercise-specific volume charts
- [ ] Personal record (PR) tracking
- [ ] Workout split visualization
- [ ] AI-powered workout recommendations
- [ ] Progressive overload analysis
- [ ] Recovery time tracking
- [ ] Export data to CSV/JSON
- [ ] Custom date range filters
- [ ] Mobile app version

## Contributing

This is a personal project, but feel free to fork and customize for your own use!

## License

MIT License - feel free to use this code for your own Hevy dashboard.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Charts powered by [Chart.js](https://www.chartjs.org/)
- Data from [Hevy](https://www.hevyapp.com/)

---

**Status:** ✅ Production Ready  
**Version:** 1.0.0  
**Last Updated:** October 14, 2025
