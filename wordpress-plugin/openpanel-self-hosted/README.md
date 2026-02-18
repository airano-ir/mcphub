# OpenPanel Self-Hosted - WordPress Plugin

**Version:** 1.1.1
**Requires:** WordPress 5.8+, PHP 7.4+
**License:** GPLv2 or later

## Description

**OpenPanel Self-Hosted** is a fork of the [official OpenPanel WordPress plugin](https://wordpress.org/plugins/openpanel/) with full **Self-Hosted instance support**. [OpenPanel](https://openpanel.dev) is an open-source web and product analytics platform — a privacy-friendly alternative to Google Analytics.

This plugin seamlessly integrates OpenPanel (Cloud or Self-Hosted) with your WordPress site while maximizing reliability and avoiding ad-blocker interference.

Designed to work with [MCP Hub](https://github.com/airano-ir/mcphub) for AI-powered analytics management.

## Key Features

- **Self-Hosted Support**: Works with both OpenPanel Cloud and your own Self-Hosted instance
- **Ad-Blocker Resistant**: Serves analytics scripts and API calls from your own domain
- **Real-Time Analytics**: Instant insights without processing delays
- **Privacy-Friendly**: Cookie-less tracking — no cookie banners needed
- **Performance Optimized**: Local script caching and efficient proxying
- **Product Analytics**: Funnel analysis, retention tracking, conversion metrics
- **Web Analytics**: Visitors, referrals, top pages, devices, sessions, bounce rates

## How It Works

1. **Inlines** `op1.js` directly into your pages (cached locally for 1 week)
2. **Bootstraps** the OpenPanel SDK with your Client ID automatically
3. **Proxies** all SDK requests through WordPress REST API (`/wp-json/openpanel/`)
4. **Preserves** all request methods, headers, query parameters, and body data

Serving scripts and data from your own domain origin avoids third-party blocking and improves tracking reliability.

## Installation

### Method 1: Upload via WordPress Admin

1. Download `openpanel-self-hosted.zip` from [Releases](https://github.com/airano-ir/mcphub)
2. Go to WordPress Admin > Plugins > Add New > Upload Plugin
3. Upload the ZIP and click "Install Now"
4. Activate the plugin

### Method 2: Manual Upload

1. Upload the `openpanel-self-hosted` folder to `/wp-content/plugins/`
2. Activate via WordPress Admin > Plugins

## Configuration

### Cloud Mode (openpanel.dev)

1. Sign up at [OpenPanel.dev](https://openpanel.dev) and create a project
2. Go to **Settings > OpenPanel** in WordPress admin
3. Select **Cloud (openpanel.dev)** as hosting mode
4. Paste your **Client ID** (starts with `op_client_`)
5. Enable desired auto-tracking features

### Self-Hosted Mode

1. Go to **Settings > OpenPanel** in WordPress admin
2. Select **Self-Hosted** as hosting mode
3. Enter your **API URL** (e.g., `https://api.openpanel.yourdomain.com`)
4. Enter your **Dashboard URL** (e.g., `https://openpanel.yourdomain.com`)
5. Paste your **Client ID** from your self-hosted instance
6. Enable desired auto-tracking features

| Setting | Example Value |
|---------|---------------|
| API URL | `https://api.openpanel.yourdomain.com` |
| Dashboard URL | `https://openpanel.yourdomain.com` |
| Client ID | Your project's client ID from OpenPanel |

## Privacy

- **No Cookie Banners Required**: Cookie-less tracking technology
- **GDPR Friendly**: Compliant without requiring user consent for basic analytics
- **Data Ownership**: Full control over your analytics data
- **No PII Collection**: Tracks behavior patterns without personal information

## Changelog

### 1.1.1
- Fixed op1.js loading for self-hosted instances (was always loading from CDN)
- Both inline cache and external fallback now use the correct self-hosted URL

### 1.1.0
- Full self-hosted OpenPanel instance support
- Hosting mode selector: Cloud vs Self-Hosted
- Configurable API URL and Dashboard URL
- Dynamic proxy validation for custom domains

### 1.0.0
- Initial release with OpenPanel Cloud integration
- Automatic script inlining with local caching
- REST API proxy for ad-blocker resistant tracking
- Auto-tracking: page views, outgoing links, page attributes

## Support

- **Plugin issues:** [GitHub Issues](https://github.com/airano-ir/mcphub/issues)
- **OpenPanel platform:** [OpenPanel.dev](https://openpanel.dev)
- **MCP Hub:** [MCP Hub Documentation](https://github.com/airano-ir/mcphub)

## License

GPLv2 or later - See [LICENSE](https://www.gnu.org/licenses/gpl-2.0.html) for details
