# Deployment Guide — stillloading.tech

This guide explains how to deploy **Still Loading...** to production under the custom domain [stillloading.tech](https://stillloading.tech).

---

## Architecture Overview

```
                                      [ Public Web Client ]
                                                │
                                                ▼ HTTPS
                                     [ stillloading.tech ]
                             (Static Frontend: Cloudflare Pages / Vercel)
                                                │
                                                ▼ /api/telemetry (Read-Only)
                                    [ Telemetry Relay Proxy ]
                                 (Fly.io / Railway / Cloud Run)
                                                │
                              Bearer Token Auth │ (Private Local Network)
                                                ▼
                                    [ Arduino UNO Q Receiver ]
                                       (192.168.1.5:8090)
                                                │
                                      Router Bridge IPC
                                                ▼
                                     [ STM32 LED Matrix (8×13) ]
```

---

## 1. Frontend Deployment (stillloading.tech)

The web frontend is a lightweight, optimized Vite React Single-Page Application (`web/`).

### Prerequisites
- Node.js 18+ (tested with v26.8.1)
- npm 9+

### Build Locally
```bash
cd web
npm install
npm run build
```
This generates the optimized static bundle in `web/dist/`.

### Option A: Cloudflare Pages (Recommended)
1. In Cloudflare Dashboard, navigate to **Compute (Workers) > Workers & Pages > Create application > Pages**.
2. Connect your Git repository.
3. Set build configuration:
   - **Framework preset:** `Vite`
   - **Build command:** `cd web && npm install && npm run build`
   - **Build output directory:** `web/dist`
   - **Root directory:** `/` (or `web` if setting root to `web`)
4. Under **Custom domains**, add `stillloading.tech` and `www.stillloading.tech`.
5. Cloudflare automatically issues and manages free Universal SSL certificates.

### Option B: Vercel
1. Install Vercel CLI or import the repository in [vercel.com](https://vercel.com).
2. Set Root Directory to `web`.
3. Build Command: `npm run build`
4. Output Directory: `dist`
5. Go to **Settings > Domains** and add `stillloading.tech`.
6. Add the DNS records provided by Vercel to your domain registrar.

---

## 2. DNS Configuration for `stillloading.tech`

Configure the following DNS records at your domain registrar (e.g., Cloudflare, Namecheap, Google Domains):

| Type | Name | Content / Target | TTL | Proxy / CDN |
| :--- | :--- | :--- | :--- | :--- |
| **A** | `@` | `192.0.2.1` *(or provider IP, e.g. 76.76.21.21 for Vercel)* | Auto | Proxied (Cloudflare) / DNS only |
| **CNAME** | `www` | `stillloading.tech` *(or your-app.pages.dev / cname.vercel-dns.com)* | Auto | Proxied |
| **CNAME** | `relay` | *(Optional: Target for cloud telemetry relay)* | Auto | DNS only |

---

## 3. Telemetry Relay Deployment (Optional for Live Hardware Telemetry)

To make your physical desk hardware observable from the public domain without exposing your home IP or local credentials:

### Deploying `relay/telemetry_relay.py` on Fly.io
1. Install `flyctl` (`brew install flyctl`).
2. Run `fly launch` in the repository root.
3. Set secrets in Fly:
   ```bash
   fly secrets set STILL_LOADING_TOKEN="your-16-character-bearer-token"
   fly secrets set UNO_Q_RECEIVER_URL="http://your-wireguard-or-tailscale-ip:8090"
   ```
4. Deploy:
   ```bash
   fly deploy
   ```

### Running the Relay Locally (Testing)
```bash
export STILL_LOADING_TOKEN='e51c5d87976dfcfccb521f2f11d2a63b'
python3 relay/telemetry_relay.py --host 127.0.0.1 --port 8080 --upstream http://127.0.0.1:8090
```

---

## 4. Verification Checklist

Before publishing, verify:
- [x] Production build passes (`npm run build` exits 0 with zero TypeScript errors).
- [x] All 74 Mac agent unit tests pass (`python3 -m unittest discover -s mac-agent/tests -t mac-agent`).
- [x] Demo mode functions predictably with zero external dependencies.
- [x] Switching between Demo Mode and Live Mode toggles all visual badges honestly.
- [x] Virtual LED matrix renders exactly 104 pixels across 8 rows and 13 columns.
- [x] No private bearer tokens are embedded in frontend source files or environment variables.
- [x] Responsive layout verified on mobile, tablet, and widescreen desktop viewports.
- [x] Accessibility: Keyboard focus visible, `prefers-reduced-motion` supported, screen reader status announcements present.

---

## 5. Troubleshooting Common Failures

### 1. Website says "OFFLINE / UNREACHABLE" in Live Mode
- Confirm the Telemetry Relay or Receiver is active.
- If no live hardware is running, simply click **DEMO** on the navigation bar to explore deterministic scenarios.

### 2. Battery Percentage is Stale
- If your MacBook lid was closed, macOS paused userland processes. Open the lid or verify the Mac is awake.
- Stale data is automatically marked with an amber badge after 30 seconds of inactivity.

### 3. Missing Heartbeat Warning `[ ! ]`
- If a monitored process pauses emitting heartbeats for >6 seconds, the matrix displays the framed warning `[ ! ]`.
- This is an indicator of suspected stall, not a permanent failure. Once the process emits its next progress update, the matrix resumes normal rendering.
