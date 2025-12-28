# Safe Websites for Training Exercises

**Important:** These websites are specifically designed to be safe for testing and learning. They won't block you or cause problems.

---

## Recommended Websites for Exercises

### 1. **example.com** (Current Exercise)
- **URL:** https://example.com
- **Why it's safe:** Created specifically for documentation and examples
- **What you can get:** Simple heading, basic HTML structure
- **Best for:** Very first exercises, learning basics
- **Difficulty:** ⭐ (Easiest)

### 2. **quotes.toscrape.com** (Recommended for Next Exercise)
- **URL:** http://quotes.toscrape.com
- **Why it's safe:** Built specifically for web scraping practice
- **What you can get:** 
  - Quote text
  - Author names
  - Tags
  - Multiple pages
- **Best for:** Learning to extract specific information
- **Difficulty:** ⭐⭐ (Easy)

### 3. **books.toscrape.com** (Good for Practice)
- **URL:** http://books.toscrape.com
- **Why it's safe:** Built specifically for web scraping practice
- **What you can get:**
  - Book titles
  - Prices
  - Ratings
  - Categories
- **Best for:** Learning to extract structured data
- **Difficulty:** ⭐⭐⭐ (Medium)

### 4. **httpbin.org** (For Advanced Testing)
- **URL:** https://httpbin.org
- **Why it's safe:** Testing service, designed for developers
- **What you can get:** Various HTTP response types
- **Best for:** Testing different scenarios
- **Difficulty:** ⭐⭐⭐⭐ (Advanced)

---

## Suggested Client Request Scenarios

### Scenario 1: Simple Heading (Current Exercise)
**Client says:** "Get me the main heading from example.com"

**What to extract:** The `<h1>` tag text

**Result:** "Example Domain"

**Difficulty:** ⭐ (Easiest - what you're doing now)

---

### Scenario 2: Quote Collection (Recommended Next)
**Client says:** "I need all the quotes from the first page of quotes.toscrape.com. Get me the quote text and the author name for each one."

**What to extract:** 
- Quote text (from `.text` class)
- Author name (from `.author` class)

**Result:** List of quotes with authors

**Difficulty:** ⭐⭐ (Easy - multiple items)

---

### Scenario 3: Book Price Check
**Client says:** "Check books.toscrape.com and get me the title and price of the first 5 books on the homepage."

**What to extract:**
- Book titles
- Prices

**Result:** List of 5 books with prices

**Difficulty:** ⭐⭐⭐ (Medium - multiple items, specific count)

---

### Scenario 4: News Headlines
**Client says:** "Visit [news site] and get me the top 3 headline titles."

**What to extract:** Headline text from news articles

**Result:** 3 headline titles

**Difficulty:** ⭐⭐⭐ (Medium - specific count)

---

### Scenario 5: Product Information
**Client says:** "Get me the product name, price, and availability status from [product page]."

**What to extract:**
- Product name
- Price
- Stock status

**Result:** Structured product information

**Difficulty:** ⭐⭐⭐⭐ (Harder - multiple fields, structured data)

---

## For Your Current Exercise

**I recommend sticking with example.com for now** because:
- ✅ It's the simplest
- ✅ It's guaranteed to work
- ✅ It's perfect for learning the basics
- ✅ No surprises

**For Exercise 02 (WALK level), we'll use quotes.toscrape.com** because:
- ✅ Still very safe
- ✅ More interesting data
- ✅ Multiple items to extract
- ✅ Good practice for real-world scenarios

---

## Important Notes

**⚠️ Always ask before scraping:**
- Real websites (not the practice ones above)
- Commercial websites
- Websites with terms of service that prohibit scraping

**✅ These practice websites are safe because:**
- They're designed for learning
- They don't have restrictions
- They won't block you
- They're free to use

**Remember:** When you move to real client work, always:
1. Check the website's robots.txt
2. Read their terms of service
3. Be respectful (don't overload their servers)
4. Ask permission if unsure

