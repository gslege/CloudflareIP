# 🌐 Cloudflare IP Optimizer

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/gslege/CloudflareIP?style=for-the-badge&logo=github)](https://github.com/gslege/CloudflareIP/stargazers)
[![Auto Update](https://img.shields.io/badge/Auto_Update-Hourly-brightgreen?style=for-the-badge&logo=github-actions)](https://github.com/gslege/CloudflareIP/actions)

> Auto-optimize Cloudflare IPs with coverage across US, Japan, Singapore, Germany, Netherlands and more — updated hourly via GitHub Actions.

<!-- TOC -->
- [Features](#-features)
- [Quick Start](#-quick-start)
- [How It Works](#-how-it-works)
- [Deployment](#-deployment)
- [Free Nodes](#-free-nodes)
- [Contributing](#-contributing)

---

## 🔧 Features

| Feature | Description |
|---------|-------------|
| **Multi-Region** | Coverage for US, JP, SG, DE, NL, and more |
| **Hourly Updates** | Auto-optimized IPs via GitHub Actions |
| **CF Worker** | Minimal `_worker.js` for Cloudflare Pages deployment |
| **VLESS Support** | Generates free VLESS nodes automatically |
| **No Domain Required** | Pages deployment works without custom domain |

---

## 🚀 Quick Start

### 1. Fork This Repo

Click the **Fork** button at the top of this page.

### 2. Deploy to Cloudflare Pages

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Pages**
2. Create a project → Connect to GitHub
3. Select `gslege/CloudflareIP` (or your fork)
4. Set build command: *(leave empty)*
5. Set build output: `/`
6. Deploy!

### 3. Get Your VLESS Nodes

After deployment, visit your Pages URL:
```
https://your-project.pages.dev/sub
```

Import the nodes into **v2ray** or **karing** client.

---

## 📖 How It Works

```
GitHub Actions (hourly)
    ↓
IP Scanner Script
    ↓
Performance Testing
    ↓
Update VLESS.txt
    ↓
Cloudflare Pages
    ↓
Public Node URL
```

The project automatically tests and ranks Cloudflare IPs based on:
- Latency
- Throughput
- Stability

---

## 🔗 Free Nodes (Community)

> ⚠️ **Note**: Public nodes have limited bandwidth. For best results, deploy your own instance.

| Provider | URL |
|----------|-----|
| Node A | `https://free.cndyw.ggff.net/sub` |
| Node B | `https://misaka.cndyw.ggff.net/sub` |
| Adaptive C | `https://suba.cndyw.ggff.net/suba?sub` |
| Adaptive D | `https://subb.cndyw.ggff.net/subb?sub` |
| VLESS List | [Vless.txt](Vless.txt) |

---

## ⚡ CF Worker (Minimal Version)

For advanced users, here's the minimal `_worker.js`:

```javascript
// See: CF-Worker/_worker.js
// Recommended for Pages deployment (no custom domain needed)
// Default UUID: 04c808e2-0b59-47b0-a54b-32fc7ef1c902
// Modify UUID before deploying for security
```

Generate nodes using: **https://ip.cloudip.ggff.net**

---

## 🤝 Contributing

Contributions are welcome! Here's how to help:

1. **Report Issues** — Found a broken node? Open an issue
2. **Suggest Regions** — Which countries should we add?
3. **Improve Scripts** — PRs for faster/more accurate testing

---

## ⚠️ Disclaimer

This project is for **learning purposes only**. Please comply with local laws and regulations regarding network usage.

---

*README optimized with [Gingiris README Generator](https://gingiris.github.io/github-readme-generator/)*
