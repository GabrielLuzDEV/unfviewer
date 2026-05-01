# Monetization & Distribution Plan

---

## API Strategy: Why the Dual-Flow Approach Works

The app intentionally uses two different data sources depending on the plan tier. This is not a workaround — it is the core product differentiation.

| | Free | Premium |
|---|---|---|
| Data source | Instagram data export (user-downloaded JSON) | instaloader (live session) |
| Data freshness | Up to 48h stale | Real-time |
| Login required | No | Yes |
| In-app unfollow | No — opens browser | Yes — one at a time, rate-limited |
| Account ban risk | None | Low (human-paced, 50/session) |

**Why not the official Instagram API?** Meta shut down the Instagram Basic Display API in December 2024. The replacement (Graph API) only works for business/creator accounts, not personal ones. Instaloader — which replicates a browser session — is the only viable live data path for personal accounts. Every major competitor app in this category uses the same approach under the hood.

**The differentiator vs competitors:** Most similar apps only offer one mode. Offering both lets users choose their comfort level and creates a clear, trusted upgrade path: "start safe for free, upgrade to live when you're ready."

---

## App Store & Play Store Distribution

### Technical path

The current app is a Python CLI. Publishing on stores requires a mobile app shell. Two architecture options:

**Option A — Backend + Mobile frontend (recommended for web/mobile)**

```
User's phone (Flutter app)
      ↓  HTTPS
Python FastAPI backend (your server)
      ↓
  Free tier:  parse uploaded JSON locally on device (no server needed)
  Premium:    instaloader runs on server, one session per user (encrypted)
```

- Premium sessions stored server-side, encrypted per user
- Backend exposes REST + Server-Sent Events for progress streaming
- Free tier analysis runs entirely on-device (no server cost)
- Risk: you hold user Instagram sessions on your server → strong encryption and a clear privacy policy are required

**Option B — Desktop app (lower risk, faster to ship)**

```
User's machine (Electron or Tauri wrapping Python backend)
      ↓
instaloader runs locally — no server, no session exposure
```

- No infrastructure cost
- No account data leaves the user's machine
- Available on Mac, Windows, Linux
- Not on App Store / Play Store (use direct download or Microsoft/Mac App Store)

**Recommendation:** Ship Option B (desktop) first to validate the product, then build the mobile app when revenue justifies the infrastructure cost.

### Platform costs

| Platform | Cost | Revenue cut |
|---|---|---|
| Apple App Store | $99/year | 30% (15% after 12 months, if < $1M/year revenue) |
| Google Play Store | $25 one-time | 15% up to $1M/year |
| Direct download (desktop) | $0 | 0% (use Stripe or Lemon Squeezy) |

### App Store compliance checklist

- [ ] Privacy policy (required — must state no data is shared with third parties)
- [ ] Unfollow is user-initiated, one at a time (no automation)
- [ ] Session credentials encrypted at rest
- [ ] Clear disclosure: "This app is not affiliated with Meta or Instagram"
- [ ] Free flow (JSON export) needs no special permissions
- [ ] Premium flow disclosure: what data is accessed, how sessions are stored

---

## Monetization Model

### Recommendation: Freemium + Subscription (Hybrid)

Subscriptions generate **82% of non-gaming app revenue**. The highest-revenue apps combine a free ad-supported tier with a premium no-ads subscription. Freemium conversion benchmarks: 2–5% average, 5–8% top performers.

---

## Plan Tiers

### Free — JSON Export Mode

- Import Instagram data export ZIP (no login required)
- Full non-follower list (no limit — the data is already on their device)
- Sort by username only (follower counts not available in export)
- Unfollow via browser link (opens `instagram.com/<username>`)
- Banner + interstitial ads
- 1 analysis per day

**Why unlimited list on free?** The data is already downloaded by the user — artificially limiting it creates friction without value. The real upgrade hook is live data + in-app unfollow.

### Premium — Live Mode ($3.99/month or $24.99/year)

- Instagram login (session stored locally/server-side, never shared)
- Real-time following/followers fetch
- Full non-follower list sorted by follower count (largest first)
- In-app unfollow — one at a time, with 40–70s delay between each
- Session cap: 50 unfollows per session (safety limit)
- Pause and resume across sessions
- No ads
- Ghost account detection (0 posts or inactive 6+ months)
- Whitelist (never unfollow specific accounts)
- CSV export of non-follower list

### Pro — Live Mode + Analytics ($6.99/month or $44.99/year)

- Everything in Premium
- Follower change history: who stopped following since last session
- Scheduled daily check (runs in background, notifies you of new non-followers)
- Bulk unfollow mode (auto-unfollows all non-followers up to session cap)
- Priority support

### One-time purchase ($14.99 lifetime — "Supporter")

- Equivalent to Premium features, no subscription
- Useful at launch to seed revenue and build word-of-mouth
- Lower LTV than subscription but zero churn

---

## Ads Strategy (Free Tier)

| Format | CPM range | Trigger | Notes |
|---|---|---|---|
| Banner (bottom) | $0.50–$2 | Always visible | Low friction |
| Interstitial | $3–$10 | After analysis completes | Never mid-flow |
| Rewarded video | $10–$30 | "Unlock follower counts" | Main conversion hook |
| Native (in-list) | $2–$5 | Between list rows | Blends with content |

**The rewarded video hook:** Since the free tier doesn't show follower counts (they require live API calls), offer a rewarded video to "preview" the Premium feature — fetch and show follower counts for the top 5 non-followers. This demonstrates value directly before asking for a purchase.

**Ad networks (priority order):**
1. Google AdMob — highest fill rate, both platforms
2. Meta Audience Network — highest CPM for social-app audience (ironic but effective)
3. AppLovin MAX — mediation layer, picks the highest payer per impression

---

## Revenue Projections

**Conservative (10,000 MAU):**

| Metric | Value |
|---|---|
| MAU | 10,000 |
| Premium subscribers (3%) | 300 |
| Avg subscription price | $4/month |
| Gross subscription revenue | $1,200/month |
| After store cut (15%) | $1,020/month |
| Ad revenue (7,000 free × $0.015 avg CPM) | ~$105/month |
| **Total** | **~$1,125/month** |

**Growth scenario (50,000 MAU, 5% conversion):**
~$8,000–10,000/month

---

## Competitive Landscape

| App | Price | Data source | In-app unfollow | Differentiator |
|---|---|---|---|---|
| FollowMeter | $4.99/mo | Instagram login | No | Analytics depth |
| UnfollowGram | Free + ads | Browser-based | No | No login needed |
| Followers & Unfollowers | Free + sub | Instagram login | No | Play Store volume |
| Social Ghost | $2.99/mo | Instagram login | No | Ghost detection |
| **This app** | Free + $3.99/mo | **Both** (export free, live premium) | **Yes (premium)** | Only app with both modes + in-app unfollow |

**The main differentiators to lead with in marketing:**
1. Free mode with no login (safest in the category)
2. Premium live mode with in-app unfollow (most powerful in the category)
3. Open-source CLI (trust signal — users can audit the code)

---

## Growth & Marketing

### Organic (zero cost)
- **ASO keywords:** "instagram unfollowers", "who unfollowed me", "followers tracker", "ghost followers", "unfollow app"
- **GitHub:** Keep the CLI open-source. It drives developer trust and organic discovery, and converts to paid mobile users.
- **Reddit:** r/Instagram, r/socialmedia, r/androidapps, r/iosapps — post the free tool first, mention the app as the GUI version
- **TikTok / Reels:** "I found out X accounts don't follow me back" — this content format performs well and is self-promotional by nature

### Paid (after organic validation)
- Meta Ads targeting: Instagram power users, social media managers, micro-influencers (10k–100k followers)
- Start only after organic conversion rate is measured

---

## Development Roadmap to Launch

The website ships before the mobile app. Reasons:
- Faster to build and iterate (no store review, no native SDK)
- Validates pricing, conversion rate, and UX before investing in mobile
- The FastAPI backend built for the web is reused directly by the mobile app
- Revenue from the website funds the mobile development

| Phase | Work | Estimated effort |
|---|---|---|
| 1 | Module split (Refactor 3) + JSON export flow (Refactor 5) | 3–4 weeks |
| 2 | FastAPI backend — auth, live fetch, unfollow endpoints, SSE progress | 2–3 weeks |
| 3 | Next.js frontend — login, non-follower list, unfollow flow | 2–3 weeks |
| 4 | Integrate Stripe for subscriptions (web) | 1 week |
| 5 | Deploy website (Fly.io / Railway + Redis) | 1 week |
| 6 | **Ship website — start monetizing** | — |
| 7 | Measure conversion rate, iterate on UX | 4–8 weeks |
| 8 | Mobile app (Flutter) + AdMob + RevenueCat, reusing FastAPI backend | 6–8 weeks |
| 9 | Submit to App Store + Play Store | 1–2 weeks |

**Stripe** — handles web subscriptions, one-time purchases, and later in-app purchase webhooks from mobile.
**RevenueCat** — manages iOS/Android subscription validation and syncs with Stripe for the mobile tier.
**Fly.io / Railway** — cheap Docker hosting, persistent volumes, Redis add-on included.

---

## Key Decisions

1. **Website before mobile app** — validates the product, generates revenue faster, backend is reused by mobile
2. **Login → features, nothing in between** — the only screen before the dashboard is the login form. No onboarding, no setup, no plan selection walls. Free vs premium is surfaced inline with lock icons, never as a pre-login barrier.
3. **Free tier = JSON export** (no login, zero risk), **Premium = instaloader** (live, in-app unfollow)
4. **In-app unfollow is the premium hook** — not analytics, not ad removal. That is what competitors don't have.
5. **Keep CLI open-source** — the commercial product is the GUI, not the logic
6. **Rewarded video** bridges free → premium by previewing the follower count sort feature
