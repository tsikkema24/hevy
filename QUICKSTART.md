# Hevy Dashboard - Quick Start Guide

## 🚀 Get Started in 60 Seconds

### 1. Verify Container is Running
```bash
cd /home/trent/github/hevy
docker compose ps
```

You should see:
```
NAME       STATUS
hevy_app   Up
```

### 2. Open Dashboard
Open your browser to:
```
http://localhost:5050
```

You'll see a clean dashboard with your workout stats.

### 3. Sync Your Data
1. Click **"⚙️ Admin"** in the top-right corner
2. Click the **"📥 Backfill All"** button
3. Wait ~10 seconds
4. Click **"← Back to Dashboard"** 

You should now see:
- ✅ Workout heatmap populated
- ✅ Stats cards showing your numbers
- ✅ Top exercises chart filled in

---

## 📊 What You'll See

### Stats Summary
- **187 workouts** - All your training sessions
- **100 exercises** - Unique movements performed
- **2,867 sets** - Total sets across all workouts
- **831,220 lbs** - Total volume lifted
- **58 weeks** - Longest active streak

### Top Exercises
1. Bench Press (Barbell) - 57 workouts
2. Lateral Raise (Dumbbell) - 55 workouts
3. Triceps Extension (Dumbbell) - 45 workouts

---

## 🔄 Keeping Data Fresh

### Automatic Sync
The dashboard automatically syncs new workouts **every 15 minutes**.

### Manual Sync (Admin Panel)
1. Go to **Admin** (`/admin`)
2. Click **"🔄 Sync Latest"** to fetch recent workouts

### Full Re-sync (Admin Panel)
1. Go to **Admin** (`/admin`)
2. Click **"🗑️ Reset & Re-sync"** to clear and reload all data
3. Confirm when prompted

---

## ⚙️ Common Commands

### Start Dashboard
```bash
docker compose up -d
```

### Stop Dashboard
```bash
docker compose down
```

### View Logs
```bash
docker compose logs -f hevy
```

### Restart After Changes
```bash
docker compose restart hevy
```

---

## 🐛 Troubleshooting

### Dashboard is blank?
1. Go to **Admin** panel (`/admin`)
2. Click **"📥 Backfill All"** button
3. Wait 10 seconds
4. Return to main dashboard and refresh

### Sync button not working?
1. Go to **Admin** panel
2. Check `.env` file has your API key
3. Click **"🏥 Health Check"** → Test endpoints
4. Restart container: `docker compose restart hevy`
5. Check logs: `docker compose logs hevy`

### Container won't start?
```bash
# Check if port 5050 is already in use
lsof -i :5050

# Rebuild container
docker compose up -d --build
```

---

## 📖 Documentation

- [README.md](README.md) - Full documentation
- [SUMMARY.md](SUMMARY.md) - Technical details and fixes applied

---

## ✅ Current Status

**Application:** ✅ Running  
**Data:** ✅ Synced (187 workouts)  
**Dashboard:** ✅ Accessible at http://localhost:5050  
**Auto-sync:** ✅ Every 15 minutes  

**You're all set! 🎉**

