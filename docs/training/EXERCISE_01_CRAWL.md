# Training Exercise 01: Your First Client Order (CRAWL)

**Welcome!** This is your first hands-on exercise with the Accord Engine. Don't worry if you don't understand everything yet - that's what training is for!

## What We're Going To Do

Imagine you're running a business and a client calls you. They say:

> "Hey, I need you to visit a website and grab some information for me. Can you go to example.com and get me the main heading text?"

This is a real-world scenario! In this exercise, you'll:
1. **Start the system** (like turning on your computer)
2. **Send the client's request** to the Accord Engine
3. **Watch it work** (like watching a robot do the job)
4. **Get the results** back
5. **Show the client** what you found

**Time needed:** About 10-15 minutes  
**Difficulty:** Beginner (Crawl level)

---

## Before We Start

### What You Need
- Docker Desktop running (the green whale icon should be in your system tray)
- A web browser (Chrome, Edge, Firefox - any is fine)
- This document open
- A text editor or notepad (to copy/paste commands)

### What We're NOT Going To Do
- We're NOT writing code
- We're NOT using complex commands
- We're NOT doing anything dangerous
- We're just clicking buttons and copying/pasting

**Think of this like:** Using a vending machine - you press buttons, it gives you what you want!

---

## Part 1: Check If Everything Is Running

**What we're doing:** Like checking if your car has gas before a trip, we're making sure the system is ready.

### Step 1.1: Open Your Terminal

**What's a terminal?** It's like a text-based control panel for your computer. Instead of clicking buttons, you type commands.

**How to open it:**
- Press `Windows Key + R`
- Type: `powershell`
- Press Enter

You'll see a window with text that looks like:
```
PS C:\Users\YourName>
```

**Don't worry if it looks scary!** We're just going to copy and paste things.

### Step 1.2: Navigate to the Project Folder

**What we're doing:** Telling the computer "I want to work in this folder."

**Copy and paste this command:**
```powershell
cd C:\ChatGPT_Workspace\Accord-Engine
```

**What happened?** The computer moved you to the project folder. You should see the path change in your terminal.

**Expected output:** The prompt should now show:
```
PS C:\ChatGPT_Workspace\Accord-Engine>
```

**If you see an error:** Let me know what it says, and I'll help you fix it!

### Step 1.3: Check If Services Are Running

**What we're doing:** Checking if all the "workers" (the parts of the system) are awake and ready.

**Copy and paste this command:**
```powershell
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml ps
```

**What this does:** 
- `docker compose` = "Hey Docker, show me what's running"
- `ps` = "process status" (like a list of what's working)

**What to look for:**
- You should see a table with columns like "NAME", "STATUS", "PORTS"
- Look for the "STATUS" column
- You want to see "Up" or "healthy" for the services

**Expected output:** You should see something like:
```
NAME                        STATUS
deploy-control-plane-1      Up (healthy)
deploy-execution-engine-1   Up (healthy)
deploy-postgres-1           Up (healthy)
deploy-redis-1              Up (healthy)
```

**If services aren't running:** That's okay! We'll start them in the next step.

**Question for you:** What do you see in the STATUS column? (Share the output with me)

---

## Part 2: Start the System (If Needed)

**What we're doing:** If the services weren't running, we're starting them up. Like turning on the lights in your office.

### Step 2.1: Start All Services

**Only do this if services weren't running in Part 1!**

**Copy and paste this command:**
```powershell
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml up -d
```

**What this does:**
- `up` = "start everything"
- `-d` = "run in the background" (so you can keep using your terminal)

**What to expect:**
- You'll see a bunch of text scrolling by
- It might take 30-60 seconds
- You'll see messages like "Creating...", "Starting...", "Healthy"

**Expected output:** You should see:
```
[+] Running 6/6
 ✔ Container deploy-control-plane-1     Started
 ✔ Container deploy-execution-engine-1  Started
 ✔ Container deploy-postgres-1          Started
 ✔ Container deploy-redis-1             Started
```

**If you see errors:** Copy the error message and share it with me. Don't worry - we'll fix it together!

**Question for you:** Did everything start successfully? (Look for checkmarks ✔)

---

## Part 3: The Client's Request

**What we're doing:** Now we're going to send the client's request to the system. Think of it like placing an order at a restaurant.

### Step 3.1: Understand What the Client Wants

**The client said:**
> "Go to example.com and get me the main heading text"

**What this means:**
- **Website:** example.com (a safe test website)
- **What to get:** The main heading (the big title on the page)
- **Why:** The client wants this information for their records

**In technical terms:**
- We're creating a "job" (a task for the system to do)
- The job type is "navigate_extract" (go to a website and get information)
- The strategy is "vanilla" (the simplest, most basic way)

**Don't worry about the technical terms yet!** Just know we're asking the system to visit a website and grab some text.

### Step 3.2: Create the Job

**What we're doing:** Sending the client's request to the Accord Engine.

**Copy and paste this command:**
```powershell
python -c "import httpx; r = httpx.post('http://localhost:8082/api/v1/jobs', params={'domain':'example.com','url':'https://example.com','job_type':'navigate_extract','strategy':'vanilla','priority':2}, json={'selector':'h1'}, timeout=30); print('Job ID:', r.json()['job_id'])"
```

**What this does:**
- `python -c` = "Run this Python code"
- `httpx.post` = "Send a request to the system"
- `http://localhost:8082` = "The address of our system" (localhost = this computer)
- The rest = "Here's what the client wants"

**What to expect:**
- It might take a few seconds
- You should see: `Job ID: [some long number with dashes]`

**Expected output:**
```
Job ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Important:** Copy that Job ID! We'll need it in the next step.

**If you see an error:** Share the error message with me. Common issues:
- "Connection refused" = Services aren't running (go back to Part 2)
- "Timeout" = System is busy (wait 30 seconds and try again)

**Question for you:** What Job ID did you get? (It will be a long string with dashes)

---

## Part 4: Watch It Work

**What we're doing:** Like watching a pizza being made, we're checking on our job to see if it's done.

### Step 4.1: Check the Job Status

**What we're doing:** Asking "Hey, is my job done yet?"

**First, replace `YOUR_JOB_ID` with the actual Job ID you got in Part 3.**

**Copy and paste this command (replace YOUR_JOB_ID):**
```powershell
curl -s "http://localhost:8082/api/v1/jobs/YOUR_JOB_ID" | python -m json.tool
```

**Example:** If your Job ID was `a1b2c3d4-e5f6-7890-abcd-ef1234567890`, you would type:
```powershell
curl -s "http://localhost:8082/api/v1/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" | python -m json.tool
```

**What this does:**
- `curl` = "Ask the system for information"
- `-s` = "Be quiet" (don't show extra messages)
- `python -m json.tool` = "Make the response pretty and readable"

**What to expect:**
- You'll see a bunch of text in a structured format
- Look for `"status":` - it might say "pending", "running", or "completed"

**If status is "pending" or "running":**
- The job is still being processed
- Wait 10-20 seconds
- Run the command again (copy/paste it again)

**If status is "completed":**
- Great! The job is done
- Move to Part 5

**Question for you:** What does the status say? (pending, running, or completed?)

---

## Part 5: Get the Results

**What we're doing:** Getting the information the client asked for - the heading text from the website.

### Step 5.1: See What We Got

**What we're doing:** Looking at the results to see what information was collected.

**Use the same command from Part 4, but this time look for the "result" section:**

```powershell
curl -s "http://localhost:8082/api/v1/jobs/YOUR_JOB_ID" | python -m json.tool
```

**What to look for:**
- Find the section that says `"result":`
- Inside that, look for `"html":`
- The HTML contains the website content

**Expected output:** You should see something like:
```json
{
    "status": "completed",
    "result": {
        "html": "<!DOCTYPE html>...Example Domain...</html>"
    }
}
```

**What this means:**
- The system visited example.com
- It grabbed the HTML (the code that makes up the webpage)
- The heading "Example Domain" is in there

### Step 5.2: Extract Just the Heading

**What we're doing:** Getting just the heading text, not all the HTML code.

**Copy and paste this command (replace YOUR_JOB_ID):**
```powershell
curl -s "http://localhost:8082/api/v1/jobs/YOUR_JOB_ID" | python -c "import sys, json; data = json.load(sys.stdin); html = data.get('result', {}).get('html', ''); import re; match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE); print('Heading found:', match.group(1) if match else 'Not found')"
```

**What this does:**
- Gets the job results
- Looks through the HTML for the `<h1>` tag (the main heading)
- Prints just the heading text

**Expected output:**
```
Heading found: Example Domain
```

**This is what the client wanted!** The main heading from example.com is "Example Domain".

**Question for you:** What heading did you find?

---

## Part 6: Show the Client

**What we're doing:** Preparing a simple report to show the client what we found.

### Step 6.1: Create a Simple Report

**What we're doing:** Making a nice summary of what we did.

**In your notepad or text editor, write:**

```
CLIENT ORDER REPORT
==================

Client Request: Get the main heading from example.com

Job ID: [paste your Job ID here]
Status: Completed
Date: [today's date]

Results:
- Website visited: https://example.com
- Main heading found: [paste the heading you found]

The information has been successfully retrieved and is ready for the client.
```

**Save this file as:** `client_report_01.txt`

**What this does:**
- Creates a record of what you did
- Shows the client you completed their request
- Documents the job for your records

---

## Part 7: Clean Up (Optional)

**What we're doing:** If you want to see the job in the database (like looking at your order history).

### Step 7.1: Check the Database

**What we're doing:** Looking at where the job information is stored.

**Copy and paste this command (replace YOUR_JOB_ID):**
```powershell
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec postgres psql -U postgres -d accord_engine -c "SELECT id, status, domain, url FROM jobs WHERE id = 'YOUR_JOB_ID';"
```

**What this does:**
- Connects to the database (where information is stored)
- Looks up your job
- Shows you the job details

**Expected output:**
```
                  id                  |  status   |   domain    |         url
--------------------------------------+-----------+-------------+------------------
 a1b2c3d4-e5f6-7890-abcd-ef1234567890 | COMPLETED | example.com | https://example.com
```

**This confirms:** Your job is stored in the system and marked as completed.

---

## Exercise Complete! 🎉

**Congratulations!** You just:
1. ✅ Started the Accord Engine system
2. ✅ Created a job for a client
3. ✅ Watched it execute
4. ✅ Got the results
5. ✅ Created a report for the client

### What You Learned

- **How to check if services are running**
- **How to create a job** (send a request to the system)
- **How to check job status** (see if it's done)
- **How to get results** (see what information was collected)
- **How to extract specific information** (get just the heading)

### Common Questions

**Q: What if something doesn't work?**  
A: Share the error message with me, and I'll help you fix it. Don't worry - we'll figure it out together!

**Q: Why did it take so long?**  
A: The system needs to start a browser, visit the website, and collect information. Usually takes 5-15 seconds.

**Q: Can I do this for other websites?**  
A: Yes! In future exercises, we'll try different websites and different types of information.

**Q: What's next?**  
A: Once you're comfortable with this, we'll do Exercise 02 (WALK level) with more complex scenarios.

---

## What's Next?

**Ready for more?** Let me know when you want to:
- Try Exercise 02 (more complex client requests)
- Ask questions about what we just did
- Practice this exercise again

**Remember:** There are no stupid questions! If something doesn't make sense, ask me. That's what training is for.

---

## Quick Reference: Commands Used

Here are all the commands from this exercise, ready to copy/paste:

**Check services:**
```powershell
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml ps
```

**Start services (if needed):**
```powershell
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml up -d
```

**Create a job:**
```powershell
python -c "import httpx; r = httpx.post('http://localhost:8082/api/v1/jobs', params={'domain':'example.com','url':'https://example.com','job_type':'navigate_extract','strategy':'vanilla','priority':2}, json={'selector':'h1'}, timeout=30); print('Job ID:', r.json()['job_id'])"
```

**Check job status:**
```powershell
curl -s "http://localhost:8082/api/v1/jobs/YOUR_JOB_ID" | python -m json.tool
```

**Get heading text:**
```powershell
curl -s "http://localhost:8082/api/v1/jobs/YOUR_JOB_ID" | python -c "import sys, json; data = json.load(sys.stdin); html = data.get('result', {}).get('html', ''); import re; match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE); print('Heading found:', match.group(1) if match else 'Not found')"
```

---

**Good job! You completed your first exercise!** 🎊

