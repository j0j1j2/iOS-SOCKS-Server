import sys
import dialogs

from lib.interfaces import get_labeled_interfaces, get_default_selections

IS_PYTHONISTA = "Pythonista" in sys.executable

if IS_PYTHONISTA:
    import ui
    import console
    from objc_util import on_main_thread


def _make_label(text, frame, font_size=14, alignment=None):
    lbl = ui.Label()
    lbl.text = text
    lbl.frame = frame
    lbl.font = ("<system>", font_size)
    if alignment is not None:
        lbl.alignment = alignment
    lbl.number_of_lines = 0
    return lbl


def _make_button(title, frame, action):
    btn = ui.Button(type="system")
    btn.title = title
    btn.frame = frame
    btn.action = action
    return btn


class ProxyUIView(ui.View):
    def __init__(self, stats, start_server_cb, stop_server_cb, socks_port=9876, http_port=9877, wpad_port=8088):
        super().__init__()
        self.name = "SOCKS5 Proxy"
        self.background_color = "white"
        self.stats = stats
        self._start_server_cb = start_server_cb
        self._stop_server_cb = stop_server_cb
        self._socks_port = socks_port
        self._http_port = http_port
        self._wpad_port = wpad_port
        self._running = False

        # Current selections
        self._proxy_iface = None
        self._connect_iface = None

        # Detect interfaces and pick defaults
        self._refresh_and_set_defaults()

        # Keep screen on
        on_main_thread(console.set_idle_timer_disabled)(True)

        self._build_ui()
        self.update_interval = 1.0

    def _refresh_and_set_defaults(self):
        labeled = get_labeled_interfaces()
        proxy_idx, connect_idx = get_default_selections(labeled)
        if labeled:
            if proxy_idx is not None:
                self._proxy_iface = labeled[proxy_idx]
            else:
                self._proxy_iface = labeled[0]
            if connect_idx is not None:
                self._connect_iface = labeled[connect_idx]
            elif len(labeled) > 1:
                self._connect_iface = labeled[1]
            else:
                self._connect_iface = labeled[0]

    def _build_ui(self):
        w = self.width
        y = 10
        pad = 10

        # --- Proxy access row ---
        self._proxy_label = _make_label("", (pad, y, w - 100, 36))
        self._update_proxy_label()
        self.add_subview(self._proxy_label)

        self._proxy_btn = _make_button("변경", (w - 80, y, 70, 36), self._change_proxy)
        self.add_subview(self._proxy_btn)
        y += 44

        # --- Connect row ---
        self._connect_label = _make_label("", (pad, y, w - 100, 36))
        self._update_connect_label()
        self.add_subview(self._connect_label)

        self._connect_btn = _make_button("변경", (w - 80, y, 70, 36), self._change_connect)
        self.add_subview(self._connect_btn)
        y += 52

        # --- Separator ---
        sep = ui.View(frame=(pad, y, w - 2 * pad, 1))
        sep.background_color = "#cccccc"
        self.add_subview(sep)
        y += 10

        # --- Status label ---
        self._status_label = _make_label("Status: Stopped", (pad, y, w - 2 * pad, 24), font_size=16)
        self.add_subview(self._status_label)
        y += 30

        # --- Stats area ---
        self._stats_text = ui.TextView()
        self._stats_text.frame = (pad, y, w - 2 * pad, 200)
        self._stats_text.editable = False
        self._stats_text.font = ("<system>", 13)
        self.add_subview(self._stats_text)
        y += 210

        # --- Log area ---
        self._log_label = _make_label("", (pad, y, w - 2 * pad, 100), font_size=11)
        self.add_subview(self._log_label)
        y += 110

        # --- Start/Restart button ---
        self._action_btn = _make_button("Start", (pad, y, w - 2 * pad, 44), self._toggle_server)
        self._action_btn.background_color = "#007AFF"
        self._action_btn.tint_color = "white"
        self._action_btn.corner_radius = 8
        self.add_subview(self._action_btn)

    def _update_proxy_label(self):
        display = self._proxy_iface[0] if self._proxy_iface else "None"
        self._proxy_label.text = f"Proxy: {display}"

    def _update_connect_label(self):
        display = self._connect_iface[0] if self._connect_iface else "None"
        self._connect_label.text = f"Connect: {display}"

    def _change_proxy(self, sender):
        labeled = get_labeled_interfaces()
        items = [d for d, _ in labeled]
        choice = dialogs.list_dialog("Proxy 접근 인터페이스", items)
        if choice is not None:
            idx = items.index(choice)
            self._proxy_iface = labeled[idx]
            self._update_proxy_label()
            if self._running:
                self._restart_server()

    def _change_connect(self, sender):
        labeled = get_labeled_interfaces()
        items = [d for d, _ in labeled]
        choice = dialogs.list_dialog("인터넷 연결 인터페이스", items)
        if choice is not None:
            idx = items.index(choice)
            self._connect_iface = labeled[idx]
            self._update_connect_label()
            if self._running:
                self._restart_server()

    def _toggle_server(self, sender):
        if self._running:
            self._stop_server_cb()
            self._running = False
            self._status_label.text = "Status: Stopped"
            self._action_btn.title = "Start"
        else:
            if self._proxy_iface is None or self._connect_iface is None:
                dialogs.alert("Error", "Select both interfaces first.")
                return
            proxy_addr = self._proxy_iface[1].addr.address
            connect_addr = self._connect_iface[1].addr.address
            connect_name = self._connect_iface[1].name
            self._start_server_cb(proxy_addr, connect_addr, connect_name)
            self._running = True
            self._status_label.text = "Status: Running"
            self._action_btn.title = "Stop"

    def _restart_server(self):
        self._stop_server_cb()
        proxy_addr = self._proxy_iface[1].addr.address
        connect_addr = self._connect_iface[1].addr.address
        connect_name = self._connect_iface[1].name
        self._start_server_cb(proxy_addr, connect_addr, connect_name)
        self._status_label.text = "Status: Running (restarted)"

    def update(self):
        """Called by Pythonista UI at update_interval frequency."""
        if not self._running:
            return
        snap = self.stats.get_snapshot()
        megabit = 1024 * 1024 / 8
        megabyte = 1024 * 1024

        proxy_addr = self._proxy_iface[1].addr.address if self._proxy_iface else "?"
        lines = [
            f"In:    {snap['inbound_speed'] / megabit:.2f} Mbps",
            f"Out:   {snap['outbound_speed'] / megabit:.2f} Mbps",
            f"",
            f"Connections: {snap['connections']}",
            f"Total In:    {snap['inbound_total'] / megabyte:.2f} MB",
            f"Total Out:   {snap['outbound_total'] / megabyte:.2f} MB",
            f"Total:       {(snap['inbound_total'] + snap['outbound_total']) / megabyte:.2f} MB",
            f"",
            f"PAC URL: http://{proxy_addr}:{self._wpad_port}/wpad.dat",
            f"SOCKS:   {proxy_addr}:{self._socks_port}",
            f"HTTP:    {proxy_addr}:{self._http_port}",
        ]
        self._stats_text.text = "\n".join(lines)

        if snap["messages"]:
            self._log_label.text = "Log:\n" + "\n".join(snap["messages"][-5:])
        if snap["errors"]:
            self._log_label.text += f"\nErrors: {snap['errors']}"

    @property
    def proxy_address(self):
        return self._proxy_iface[1].addr.address if self._proxy_iface else None

    @property
    def connect_address(self):
        return self._connect_iface[1].addr.address if self._connect_iface else None

    @property
    def connect_iface_name(self):
        return self._connect_iface[1].name if self._connect_iface else None
