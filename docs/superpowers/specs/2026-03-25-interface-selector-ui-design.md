# Network Interface Selector UI

## Problem

The proxy server automatically selects the first matching network interface for both proxy access (PROXY_HOST) and internet connection (CONNECT_HOST). Users cannot choose which interfaces to use, making it impossible to route traffic through specific networks like Tailscale VPN at runtime.

## Solution

Replace the console-based status display with a Pythonista `ui` module GUI that combines interface selection with live traffic monitoring. Users can change interfaces while the server is running.

## UI Layout

```
┌─────────────────────────────────┐
│  Proxy 접근: en0 - WiFi (...)   │  [변경]
│  인터넷 연결: pdp_ip0 - Cell .. │  [변경]
├─────────────────────────────────┤
│  Status: Running                │
│  In:  12.34 Mbps                │
│  Out:  5.67 Mbps                │
│  Connections: 3                 │
│  Total In:  123.45 MB           │
│  Total Out:  67.89 MB           │
│  PAC URL: http://...            │
│  SOCKS: ...:9876                │
│  HTTP:  ...:9877                │
├─────────────────────────────────┤
│  Last 5 log messages:           │
│    ...                          │
├─────────────────────────────────┤
│        [Start / Restart]        │
└─────────────────────────────────┘
```

## Interface List Display Format

Each interface shown as: `{name} - {type_label} ({ip_address})`

Type labels derived from interface name prefix:
- `en*` → WiFi
- `bridge*` → Hotspot
- `utun*` → VPN
- `pdp_ip*` → Cellular
- others → Other

Only IPv4 interfaces shown in the selection dialogs. IPv6 is auto-matched from the same interface name as the selected IPv4 CONNECT_HOST interface (existing behavior preserved).

## Components

### 1. Interface discovery (modify existing logic in `socks5.py`)

Extract the interface enumeration and classification into a reusable function that returns a list of available interfaces with their type labels. This replaces the current inline classification code.

```python
def get_labeled_interfaces():
    """Return list of (display_string, iface) tuples for all routable IPv4 interfaces."""
```

### 2. UI view (`lib/ui_view.py` — new file)

A Pythonista `ui.View` subclass that:
- Shows two labeled rows for current proxy access and connect interfaces, each with a "변경" (Change) button
- "변경" buttons open `dialogs.list_dialog` with the labeled interface list
- Displays live traffic stats (replaces `StatusMonitor.render_forever`)
- Shows server connection info (PAC URL, SOCKS/HTTP addresses)
- Shows last 5 log messages
- Has a Start/Restart button
- Keeps `console.set_idle_timer_disabled(True)` active to prevent screen from turning off

### 3. Server lifecycle management (modify `socks5.py`)

- Server start is triggered by UI button, not by script start
- When interface is changed while running, stop current servers and restart with new settings
- The asyncio event loop runs in a background thread; UI runs on main thread (Pythonista requirement)

### 4. StatusMonitor adaptation (modify `lib/status.py`)

- Add a method or callback mechanism so the UI can pull/receive stats updates
- Keep `render_forever` for non-Pythonista (terminal) fallback
- Add a UI-oriented update path that writes to `ui.Label` references instead of console

## Screen-off Prevention

The existing `console.set_idle_timer_disabled(True)` call is preserved. It will be called during UI initialization to ensure the screen stays on while the proxy is active.

## Flow

1. App starts → detect interfaces → build labeled list
2. Show UI with auto-selected defaults (existing heuristic: bridge > en for proxy, cell/vpn for connect)
3. User can change selections via "변경" buttons at any time
4. User presses Start → servers launch with selected interfaces
5. Stats update live in UI labels
6. User changes interface → servers restart automatically with new selection

## Non-Pythonista Fallback

When not running in Pythonista (no `ui` module), fall back to the existing console-based behavior with automatic interface selection. The GUI is Pythonista-only.
