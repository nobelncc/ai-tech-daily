# AI & Tech Daily — Automated News Aggregator

This is a fully automated news aggregator. Once set up, it needs **no daily
manual work**: no writer, no editor, no one clicking "publish." A robot
(GitHub Actions) checks your news sources every hour, writes short original
summaries using AI, and updates your website automatically.

You do not need to know how to code to set this up. Just follow the steps
below in order.

---

## What's in this project

| File / Folder | What it's for |
|---|---|
| `sources.json` | The list of news sources it checks. **This is the only file you'll likely ever edit.** |
| `fetch.py` | The robot's brain — fetches news and writes summaries. You never need to touch this. |
| `index.html` | Your actual website homepage. You never need to touch this. |
| `data/articles.json` | Where all the collected articles are stored. Updated automatically. |
| `.github/workflows/update.yml` | The schedule that tells GitHub to run the robot every hour. |
| `requirements.txt` | A technical list GitHub uses to set itself up. Never touch this. |

---

## STEP 1 — Create a free GitHub account

If you don't already have one, go to [github.com](https://github.com) and sign up. It's free.

---

## STEP 2 — Create a new repository and upload these files

1. On GitHub, click the **+** icon (top right) → **New repository**.
2. Name it anything, e.g. `ai-tech-daily`.
3. Set it to **Public** (required for the free version of GitHub Pages, which hosts your site for free).
4. Click **Create repository**.
5. On the new repository page, click **uploading an existing file**.
6. Drag and drop **all the files and folders** from this project into that upload box (keep the folder structure — `.github` folder and `data` folder must stay as folders).
7. Click **Commit changes**.

---

## STEP 3 — Get a free Google Gemini API key (this powers the AI summaries, no cost)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with any Google account.
2. Click **Create API key**.
3. Copy the key. Keep this safe — you'll paste it once in Step 4 and never need it again after that.
4. **No credit card is required.** Google's free tier for this model comfortably covers a small/medium daily news site. See the quota notes at the bottom.

---

## STEP 4 — Add your API key to GitHub (securely, as a "Secret")

This lets the robot use AI summarization without your key ever being visible publicly.

1. In your GitHub repository, click **Settings** (top menu of the repo).
2. In the left sidebar, click **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. Name: `GEMINI_API_KEY`
5. Value: paste the key you copied in Step 3.
6. Click **Add secret**.

---

## STEP 5 — Turn on GitHub Pages (this makes your site publicly viewable)

1. In your repository, click **Settings** → **Pages** (left sidebar).
2. Under "Build and deployment" → **Source**, choose **Deploy from a branch**.
3. Under "Branch," choose `main` and folder `/ (root)`.
4. Click **Save**.
5. Wait 1-2 minutes, then refresh the page — GitHub will show you your live site URL (something like `https://yourusername.github.io/ai-tech-daily/`).

---

## STEP 6 — Run the robot for the first time (don't wait an hour)

1. In your repository, click the **Actions** tab.
2. Click on **Update News Data** (in the left sidebar).
3. Click **Run workflow** (button on the right) → **Run workflow** again to confirm.
4. Wait 1-2 minutes, then refresh — you'll see a green checkmark when it finishes.
5. Visit your website URL from Step 5 — you should now see real news summaries.

**From this point on, this happens automatically every hour, forever, with no action from you.**

---

## About the category menu

The homepage automatically builds a clickable filter menu (All / AI & Tech / Crypto / Gaming / etc.)
from whatever `"category"` values appear in `sources.json` — **you don't design this menu by hand.**
Add a source with `"category": "Health"` and a "Health" button appears on the site automatically;
remove all sources in a category and its button disappears. This is why `sources.json` is the only
file you ever need to edit to reshape the site.

This project ships pre-loaded with sources across 10 categories: AI & Tech, Startups, Crypto,
Remote Work, Climate, Bangladesh News, Gaming, Finance, Freelance, and Health.

---



Open `sources.json` and edit it like a simple list:

```json
{
  "name": "TechCrunch",
  "rss_url": "https://techcrunch.com/feed/",
  "category": "Tech"
}
```

- To **add a source**: copy one of these blocks, change the name/URL/category, add a comma between blocks.
- To **remove a source**: delete its block.
- To find a site's RSS URL: search "[site name] RSS feed" — most news sites have one, usually ending in `/feed` or `/rss`.

**Note on the pre-loaded sources**: The 15 sources included cover your 10 categories, but websites occasionally change or retire their RSS feed URLs over time. After your first automated run (Step 6), check the **Actions** tab — if any source shows a "could not parse feed" warning in the logs, just search for that site's current RSS URL and update it in `sources.json`. This won't break anything else; the script skips broken sources and keeps working with the rest.

After editing `sources.json`, just upload the changed file back to GitHub (same "uploading an existing file" method as Step 2) — the next scheduled run will use your new list automatically.

---

## Monthly cost estimate

| Item | Cost |
|---|---|
| GitHub hosting + automation | **Free** (GitHub Actions free tier covers this easily at this scale) |
| GitHub Pages website hosting | **Free** |
| Google Gemini API (AI summaries) | **Free** — no credit card required (see quota notes below) |
| Domain name (optional, e.g. yoursite.com instead of github.io) | ~$10-15/**year**, bought separately from any domain registrar, then connected to GitHub Pages in Settings → Pages |

This setup can run at **$0/month** with just a domain name as the only optional cost.

### About the free Gemini quota

Google's free tier has a daily and per-minute limit on how many AI requests you can make (the exact
numbers change over time — check [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
for the current figures). This project is already configured conservatively to stay well within
typical free-tier limits:

- At most **15 new AI summaries per hourly run** (`MAX_NEW_SUMMARIES_PER_RUN` in `fetch.py`), so at most ~360/day
- A short pause between each AI call so requests don't burst past the per-minute limit

If you ever do hit the daily quota, the site does **not** break — `fetch.py` automatically falls
back to showing a trimmed original snippet for that article instead of an AI summary, and picks
back up with AI summaries once the quota resets. If your site grows a lot and you consistently hit
the free limit, Gemini's paid tier is inexpensive (a small fraction of a cent per summary) — you'd
just add billing to the same Google account, nothing else changes.

---

## How to add AdSense later

Once you have real traffic, apply for Google AdSense with your site URL.
When approved, Google gives you a small code snippet — paste it into
`index.html` where indicated (or ask for help doing this one small edit).
This project does not include an ad snippet yet, since AdSense approval
must come first.

---

## If something breaks

- Check the **Actions** tab — if a run shows a red X, click it to see the error message.
- The most common issue is a source's RSS URL changing or going offline — just remove or update that entry in `sources.json`.
- The script is written to skip broken sources rather than stop entirely, so one bad source won't take down the whole site.
