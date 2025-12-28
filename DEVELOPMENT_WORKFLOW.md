# Development Workflow - Daemon Accord

**Strategy:** Continue developing while keeping `main` sale-ready

---

## Branch Strategy

### `main` Branch
- **Purpose:** Production-ready, sale-ready code
- **Status:** Always stable, tested, deployable
- **Use:** For buyers, demos, production deployments
- **Rule:** Only merge from `develop` after thorough testing

### `develop` Branch
- **Purpose:** Active development, new features
- **Status:** Work-in-progress, may be unstable
- **Use:** Daily development, feature additions
- **Rule:** Merge to `main` when features are complete and tested

---

## Workflow

### Starting New Development
```bash
# Make sure you're on develop
git checkout develop

# Pull latest changes
git pull origin develop

# Create feature branch (optional, for larger features)
git checkout -b feature/your-feature-name
```

### Daily Development
```bash
# Work on develop branch
git checkout develop

# Make changes, commit
git add .
git commit -m "Add: your feature description"

# Push to GitHub
git push origin develop
```

### Merging to Main (When Feature is Complete)
```bash
# 1. Test everything on develop
# 2. Make sure develop is stable
git checkout develop
git pull origin develop

# 3. Switch to main
git checkout main
git pull origin main

# 4. Merge develop into main
git merge develop

# 5. Test main one more time
# 6. Push to GitHub
git push origin main

# 7. Tag the release (optional)
git tag -a v1.1.0 -m "Release v1.1.0: Added feature X"
git push origin v1.1.0
```

---

## Making Money While Selling

### Strategy
1. **Show `main` to buyers** - Production-ready, stable
2. **Show `develop` to buyers** - Active development, roadmap
3. **Both increase value:**
   - `main` = Working product now
   - `develop` = Future value, active development

### What Buyers See
- **GitHub `main` branch:** Clean, production-ready code
- **GitHub `develop` branch:** Active development, new features
- **Both demonstrate:** Working product + active development = higher value

---

## Quick Commands

### Check Current Branch
```bash
git branch
```

### Switch Branches
```bash
git checkout main      # Switch to main (sale-ready)
git checkout develop   # Switch to develop (development)
```

### See What's Different
```bash
git diff main..develop  # See what's in develop but not main
```

### Create Feature Branch (for larger features)
```bash
git checkout develop
git checkout -b feature/new-feature
# ... work on feature ...
git push origin feature/new-feature
# When done, merge to develop, then develop to main
```

---

## Rules

1. **Never commit directly to `main`** - Always go through `develop`
2. **Test before merging to `main`** - Keep main stable
3. **Keep `main` deployable** - Should always work
4. **Document features** - Update README/docs when adding features
5. **Tag releases** - Tag stable versions in main

---

## Current Status

- ✅ `main` branch: Production-ready, sale-ready
- 🔄 `develop` branch: For new development
- 📦 Both pushed to GitHub for buyers to see

---

**Remember:** Customers are most important, but active development shows value to buyers too!

