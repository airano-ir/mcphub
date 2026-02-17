=== OpenPanel ===
Contributors: openpanel, airano
Tags: analytics, web analytics, privacy-friendly, tracking, proxy, self-hosted
Requires at least: 5.8
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 1.1.1
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

OpenPanel WordPress plugin - Privacy-friendly analytics with ad-blocker resistance. Supports both OpenPanel Cloud and Self-Hosted instances. Inline tracking scripts and proxy API calls through your domain.

== Description ==

**OpenPanel** is an open-source web and product analytics platform that serves as a privacy-friendly alternative to traditional analytics solutions. This WordPress plugin seamlessly integrates [OpenPanel](https://openpanel.dev) with your WordPress site while maximizing reliability and avoiding ad-blocker interference.

= Key Features =

* **🏠 Self-Hosted Support**: Works with both OpenPanel Cloud and your own Self-Hosted instance
* **🚀 Ad-Blocker Resistant**: Serves analytics scripts and API calls from your own domain
* **📊 Real-Time Analytics**: Get instant insights without processing delays
* **🔒 Privacy-Friendly**: Cookie-less tracking that respects user privacy (no cookie banners needed!)
* **⚡ Performance Optimized**: Caches scripts locally and uses efficient proxying
* **🎯 Product Analytics**: Funnel analysis, retention tracking, and conversion metrics
* **📈 Web Analytics**: Visitors, referrals, top pages, devices, sessions, and bounce rates

= How It Works =

This plugin integrates OpenPanel with WordPress in a blocker-resistant way:

* **Inlines** `op1.js` directly into your pages (cached locally for 1 week; falls back to CDN if needed)
* **Bootstraps** the OpenPanel SDK with your Client ID automatically
* **Proxies** all SDK requests through WordPress REST API (`/wp-json/openpanel/`)
* **Preserves** all request methods, headers, query parameters, and body data
* **Handles** CORS properly for cross-origin requests

**Why use a proxy?** Serving scripts and data from your own domain origin avoids third-party blocking and improves tracking reliability significantly.

= Privacy Benefits =

* **🍪 No Cookie Banners Required**: OpenPanel uses cookie-less tracking, so you don't need annoying cookie consent banners
* **🛡️ GDPR Friendly**: Compliant with privacy regulations without requiring user consent for basic analytics
* **🔐 Data Ownership**: You maintain full control over your analytics data
* **🚫 No Personal Data Collection**: Tracks behavior patterns without collecting personally identifiable information

**Learn more at [OpenPanel.dev](https://openpanel.dev)**

== Installation ==

= Getting Started (Cloud) =

1. **Get your OpenPanel Client ID**:
   * Sign up for an account at [OpenPanel.dev](https://openpanel.dev)
   * Create a new project for your website
   * Copy your Client ID (starts with `op_client_`)

2. **Install the Plugin**:
   * Upload the plugin ZIP file via **Plugins → Add New → Upload Plugin**
   * Or place the `openpanel` folder in `/wp-content/plugins/`
   * Activate the plugin via **Plugins → Installed Plugins**

3. **Configure Settings**:
   * Go to **Settings → OpenPanel** in your WordPress admin
   * Select **Cloud (openpanel.dev)** as hosting mode
   * Paste your **Client ID** in the settings
   * Optionally enable auto-tracking features:
     - ✅ **Track page views automatically**
     - ✅ **Track clicks on outgoing links**
     - ✅ **Track additional page attributes**

4. **Verify Installation**:
   * Visit your website frontend
   * Check browser developer tools - you should see OpenPanel tracking requests to your own domain
   * Check your OpenPanel dashboard for incoming data

**That's it!** No theme edits or manual code insertion required.

= Self-Hosted Setup =

If you run your own OpenPanel instance (e.g., on Coolify, Docker, or any self-hosted environment):

1. **Install the Plugin** (same as above)

2. **Configure Self-Hosted Settings**:
   * Go to **Settings → OpenPanel** in your WordPress admin
   * Select **Self-Hosted** as hosting mode
   * Enter your **API URL** (e.g., `https://api.openpanel.yourdomain.com`)
   * Enter your **Dashboard URL** (e.g., `https://openpanel.yourdomain.com`)
   * Paste your **Client ID** from your self-hosted OpenPanel instance
   * Enable desired auto-tracking features

3. **Verify Configuration**:
   * Check the "Current Configuration" table at the bottom of settings page
   * Ensure API URL and JS URL point to your self-hosted instance
   * Visit your website frontend and verify tracking works

= Self-Hosted URL Examples =

| Setting | Example Value |
|---------|---------------|
| API URL | `https://api.openpanel.yourdomain.com` |
| Dashboard URL | `https://openpanel.yourdomain.com` |
| Client ID | Your project's client ID from OpenPanel |

**Note**: In Self-Hosted mode, op1.js is loaded from your Dashboard URL. In Cloud mode, it is loaded from the official OpenPanel CDN.

== Frequently Asked Questions ==

= What is OpenPanel? =
OpenPanel is an open-source web and product analytics platform designed as a privacy-friendly alternative to traditional analytics solutions. It provides real-time insights, funnel analysis, retention tracking, and more while respecting user privacy.

= Does this plugin support Self-Hosted OpenPanel? =
Yes! Version 1.1.0 adds full support for self-hosted OpenPanel instances. Simply select "Self-Hosted" mode in settings and enter your API URL and Dashboard URL.

= Where is the proxy endpoint? =
The proxy endpoint is at `/wp-json/openpanel/` (followed by the OpenPanel API path). The SDK automatically points to this endpoint, so all analytics requests go through your WordPress site instead of directly to OpenPanel servers (Cloud or Self-Hosted).

= Why do I need this proxy approach? =
Serving analytics scripts and API requests from your own domain significantly reduces blocking by ad-blockers and privacy tools. This improves data collection reliability and ensures more accurate analytics.

= Does it respect CORS and security? =
Yes. The proxy responds with proper CORS headers allowing your site origin and credentials. It also sanitizes all inputs and only forwards legitimate OpenPanel API requests.

= What if inlining `op1.js` fails? =
The plugin automatically falls back to loading the script externally. In Self-Hosted mode, it loads from your Dashboard URL; in Cloud mode, from the OpenPanel CDN (`https://openpanel.dev/op1.js`).

= How is the script cached? =
The `op1.js` script is cached locally for 1 week using WordPress transients. You can manually clear the cache from the plugin settings page if needed.

= Can I limit tracking to certain users or pages? =
Yes! The plugin includes hooks and checks. For example, tracking is automatically disabled for admin pages. You can extend this by modifying the `inject_inline_sdk()` method or using WordPress filters.

= Will this affect my site performance? =
No, the plugin is designed for minimal performance impact. Scripts are cached locally, loaded asynchronously, and the proxy only handles analytics requests efficiently.

= Do I need to modify my theme? =
No theme modifications are required. The plugin automatically injects the necessary tracking code into all frontend pages.

= Is my data secure? =
Yes. OpenPanel respects privacy by design with cookie-less tracking. Your data ownership is maintained, and you can export or delete data as needed. Since no cookies are used, you don't need cookie consent banners on your site.

= Do I need cookie consent banners with OpenPanel? =
No! OpenPanel uses cookie-less tracking technology, which means no cookies are stored on your visitors' devices. This eliminates the need for cookie consent banners and makes your site GDPR compliant for basic analytics without requiring user consent.

= Where can I get support? =
For plugin-specific issues, use the WordPress plugin support forum. For OpenPanel platform questions, visit [OpenPanel.dev](https://openpanel.dev) or their community channels.

== External Services ==

This plugin connects to external OpenPanel.dev services to provide web analytics functionality. Here's what you need to know:

**OpenPanel.dev Analytics Service**

* **What it is**: OpenPanel.dev is an open-source web and product analytics platform that combines the power of Mixpanel with the ease of Plausible and one of the best Google Analytics replacements.

* **What data is sent**: 
  - **User Agent**: Browser and device information for compatibility and analytics
  - **IP Address**: Collected from X-Forwarded-For header for geolocation (no personal identification)
  - **Page Information**: Current page URL/path and referrer information
  - **Event Data**: Other user-defined properties when custom events are triggered via `window.op('track', 'event_name')`

* **When data is sent**: 
  - **Page Views**: Only when "Track page views automatically" is enabled in settings
  - **Outgoing Link Clicks**: Only when "Track clicks on outgoing links" is enabled in settings  
  - **Custom Events**: Only when website owner implements `window.op('track', 'custom_event')` method
  - **No background tracking** - data is sent only for the specific interactions you've configured

* **External endpoints used**:
  - `https://openpanel.dev/op1.js` - Analytics tracking script (cached locally)
  - `https://api.openpanel.dev/` - Analytics data collection API (proxied through your WordPress site)

* **Legal Information**:
  - Service Terms: https://openpanel.dev/terms
  - Privacy Policy: https://openpanel.dev/privacy

This integration is essential for the plugin's core functionality of providing website analytics. The plugin uses a proxy approach to serve requests through your own domain to improve reliability and avoid ad-blocker interference.

== Changelog ==

= 1.1.1 =
* **Self-Hosted JS Loading Fix** - op1.js now loads from Dashboard URL in Self-Hosted mode
* ✅ Fixes ERR_SSL_PROTOCOL_ERROR when openpanel.dev CDN is blocked/filtered
* ✅ Both inline cache and external fallback now use the correct self-hosted URL

= 1.1.0 =
* **Self-Hosted Support** - Full support for self-hosted OpenPanel instances
* ✅ New hosting mode selector: Cloud vs Self-Hosted
* ✅ Configurable API URL for self-hosted instances
* ✅ Configurable Dashboard URL for op1.js loading
* ✅ Dynamic proxy validation for custom domains
* ✅ Current configuration display in settings
* ✅ Toggle visibility for self-hosted fields

= 1.0.0 =
* **Initial Release** - Complete OpenPanel WordPress integration
* ✅ Automatic script inlining with local caching (1 week cache duration)
* ✅ REST API proxy for ad-blocker resistant tracking
* ✅ Auto-tracking options: page views, outgoing links, page attributes
* ✅ CORS-compliant request handling
* ✅ Cache management with manual clear functionality
* ✅ Fallback to CDN if local caching fails
* ✅ Admin interface for easy configuration
* ✅ No theme modifications required

== Upgrade Notice ==

= 1.1.1 =
Fixes op1.js loading for self-hosted instances. Previously op1.js always loaded from openpanel.dev CDN even in Self-Hosted mode, causing SSL errors in regions where the CDN is blocked.

= 1.1.0 =
Adds full support for self-hosted OpenPanel instances. You can now use the plugin with your own OpenPanel deployment on Coolify, Docker, or any self-hosted environment.

= 1.0.0 =
Initial release of the OpenPanel WordPress plugin. Provides ad-blocker resistant analytics with local script caching and API proxying.
