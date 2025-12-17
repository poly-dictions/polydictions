# Polydictions Chrome Extension

A Chrome extension for tracking and analyzing Polymarket prediction markets.

## Features

- **Overview Dashboard**: View total events, volume, and active markets
- **Category Breakdown**: See events organized by crypto, politics, sports, finance, etc.
- **Trending Events**: Track the most active markets by volume
- **Watchlist**: Star your favorite events to track them
- **Real-time Updates**: Auto-refresh data every 5 minutes
- **Notifications**: Get notified when new events are created

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked"
4. Select the `chrome-extension` folder
5. The extension icon should appear in your toolbar

## Usage

Click the extension icon to open the popup with:
- **Overview**: Stats and category breakdown
- **Trending**: Top events by volume
- **Watchlist**: Your starred events

## Development

The extension is built with vanilla JavaScript and uses:
- Manifest V3
- Polymarket Gamma API
- Local Storage for watchlist
- Chrome Notifications API

## Links

- Telegram Bot: https://t.me/polydictions_bot
- GitHub: https://github.com/poly-dictions/polydictions
