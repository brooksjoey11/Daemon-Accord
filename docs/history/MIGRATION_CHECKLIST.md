# Migration Checklist

**Step-by-step checklist for safe repository migration**

---

## Pre-Migration (Current Workspace)

### ✅ Step 1: Review Current State
- [ ] Review `git status` - see what's changed
- [ ] Review `CLEANUP_AND_MIGRATION_PLAN.md` - understand strategy
- [ ] Review files to archive vs keep

### ✅ Step 2: Run Cleanup Script
```powershell
.\scripts\cleanup_workspace.ps1
```
- [ ] Review what will be archived
- [ ] Verify important files are kept
- [ ] Adjust cleanup script if needed

### ✅ Step 3: Verify .gitignore
- [ ] `.gitignore` exists at root
- [ ] Covers Python, Node, IDE, temp files
- [ ] Artifacts directory ignored
- [ ] No secrets will be committed

### ✅ Step 4: Final Code Review
- [ ] No hardcoded secrets
- [ ] No API keys in code
- [ ] No passwords in config files
- [ ] All sensitive data in .env or config files (gitignored)

---

## Migration (New Repository)

### ✅ Step 5: Create New GitHub Repository
- [ ] Go to GitHub.com
- [ ] Click "New repository"
- [ ] Name: `accord-engine` (or your choice)
- [ ] Description: "Policy-driven web automation platform with compliance controls"
- [ ] Visibility: Private (for now, can make public later)
- [ ] **DO NOT** check "Initialize with README"
- [ ] **DO NOT** check "Add .gitignore"
- [ ] **DO NOT** check "Choose a license" (we have LICENSE file)
- [ ] Click "Create repository"
- [ ] Copy the repository URL

### ✅ Step 6: Backup Current Git State (Optional Safety)
```powershell
# If you want to keep current .git as backup
Copy-Item -Recurse .git .git.backup
```

### ✅ Step 7: Initialize Clean Git
**Option A: Fresh Start (Recommended)**
```powershell
# Remove old git
Remove-Item -Recurse -Force .git

# Initialize fresh
git init
```

**Option B: Keep Git, Clean Branch**
```powershell
# Create orphan branch (clean history)
git checkout --orphan clean-main
```

### ✅ Step 8: Stage All Files
```powershell
git add .
```

### ✅ Step 9: Review What Will Be Committed
```powershell
git status
```
- [ ] Verify all important files are staged
- [ ] Verify no secrets are included
- [ ] Verify no large binary files
- [ ] Verify .gitignore is working

### ✅ Step 10: Make Initial Commit
```powershell
git commit -m "Initial commit: Production-ready Accord Engine v1.0

- Policy-driven web automation platform
- Production-ready core executors (Vanilla, Stealth, Assault)
- Enterprise advanced features (Ultimate Stealth, Custom)
- Complete compliance controls and audit logging
- Three production workflows (Page Change Detection, Job Posting Monitor, Uptime Smoke Check)
- Full test coverage and CI/CD
- One-command deployment (docker-compose)
- Production proof pack validation"
```

### ✅ Step 11: Connect to New Repository
```powershell
git remote add origin <YOUR_NEW_REPO_URL>
git branch -M main
git push -u origin main
```

### ✅ Step 12: Verify Push
- [ ] Go to GitHub, verify all files are there
- [ ] Verify structure looks clean
- [ ] Verify README displays correctly
- [ ] Verify no sensitive files visible

---

## Post-Migration (Verification)

### ✅ Step 13: Test Fresh Clone
```powershell
# In a different directory
cd ..
git clone <YOUR_NEW_REPO_URL> accord-engine-test
cd accord-engine-test

# Verify structure
ls

# Test proof pack (if services available)
python scripts/proof_pack/run_proof_pack.py --help
```

### ✅ Step 14: Review Old Repository
- [ ] Keep old repo accessible
- [ ] Review for valuable historical items
- [ ] Extract valuable files/context manually
- [ ] Add to new repo if needed

### ✅ Step 15: Final Polish
- [ ] Add repository description on GitHub
- [ ] Add topics/tags on GitHub
- [ ] Verify all documentation links work
- [ ] Test deployment instructions

---

## Safety Notes

### ⚠️ Before You Start
- **Backup:** Current workspace is safe (we're not deleting anything)
- **Old Repo:** Will remain untouched
- **New Repo:** Fresh start, clean history

### ⚠️ During Migration
- **Don't delete old repo** until you've verified new one is perfect
- **Don't force push** to old repo (might mess it up)
- **Do test clone** before considering migration complete

### ⚠️ After Migration
- **Keep old repo** for at least a week
- **Review old repo** for valuable history
- **Extract manually** - don't try to merge git histories

---

## If Something Goes Wrong

### Problem: Accidentally pushed to wrong repo
**Solution:** Remove remote, add correct one
```powershell
git remote remove origin
git remote add origin <CORRECT_URL>
git push -u origin main
```

### Problem: Forgot to clean up before commit
**Solution:** Amend commit or create new commit
```powershell
# Add cleanup
git add .
git commit --amend --no-edit
# Or
git commit -m "Cleanup: Archive internal tracking documents"
```

### Problem: Need to start over
**Solution:** Delete .git, start fresh
```powershell
Remove-Item -Recurse -Force .git
git init
# Start from Step 7
```

---

## Success Criteria

✅ **New repository:**
- Clean, professional structure
- All production code present
- All documentation present
- No internal tracking files in root
- No secrets or sensitive data
- .gitignore working correctly

✅ **Old repository:**
- Still accessible
- Can review for historical value
- Can extract valuable items manually

✅ **Workspace:**
- Current workspace unchanged (except organized files)
- Can continue working
- Can push updates to new repo

---

**Ready to start?** Begin with Step 1 and work through the checklist.

**Need help?** Ask me to guide you through any step.

---

**Last Updated:** 2024-01-01

