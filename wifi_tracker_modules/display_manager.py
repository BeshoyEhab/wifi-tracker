"""
Display Manager Module for WiFi Tracker
Handles all display formatting and output operations using Rich
"""

import subprocess
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.align import Align
    from rich.box import ROUNDED

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Fallback to standard print if rich is not available (though we expect it to be)


class DisplayManager:
    """Manages display formatting and output for WiFi tracker using Rich"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None

    def clear_screen(self) -> None:
        """Clear the terminal screen"""
        if RICH_AVAILABLE:
            self.console.clear()
        else:
            subprocess.run(["clear"] if os.name == "posix" else ["cls"], check=False)

    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string"""
        if bytes_value == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(bytes_value)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    def format_rate(self, rate: float) -> str:
        """Format transfer rate into human-readable string"""
        return f"{self.format_bytes(int(rate))}/s"

    def format_duration(self, duration: timedelta) -> str:
        """Format duration into human-readable string"""
        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _calculate_period_usage(
        self,
        ssid_data: Dict[str, Any],
        interval: str = "monthly",
        custom_start_date: Optional[datetime] = None,
        custom_end_date: Optional[datetime] = None,
    ) -> int:
        """Calculate usage for the specified interval or custom date range"""
        period_usage = 0

        if custom_start_date or custom_end_date:
            start_date = (
                custom_start_date
                if custom_start_date
                else (
                    datetime.now().replace(day=1)
                    if interval == "monthly"
                    else datetime.now() - timedelta(days=7)
                )
            )
            end_date = custom_end_date if custom_end_date else datetime.now()
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_date.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                daily_data = ssid_data.get("daily", {}).get(date_str, {})
                period_usage += daily_data.get("rx", 0) + daily_data.get("tx", 0)
                current_date += timedelta(days=1)
            return period_usage

        if interval == "daily":
            today = datetime.now().strftime("%Y-%m-%d")
            daily_data = ssid_data.get("daily", {}).get(today, {})
            period_usage = daily_data.get("rx", 0) + daily_data.get("tx", 0)

        elif interval == "weekly":
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())

            for i in range(7):
                date = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
                daily_data = ssid_data.get("daily", {}).get(date, {})
                period_usage += daily_data.get("rx", 0) + daily_data.get("tx", 0)

        elif interval == "monthly":
            today = datetime.now()
            month_start = today.replace(day=1)

            current_date = month_start
            while current_date.month == today.month:
                date_str = current_date.strftime("%Y-%m-%d")
                daily_data = ssid_data.get("daily", {}).get(date_str, {})
                period_usage += daily_data.get("rx", 0) + daily_data.get("tx", 0)
                current_date += timedelta(days=1)
                if current_date > today:
                    break

        return period_usage

    def build_watch_display(
        self,
        interface: str,
        pid: int,
        current_time: datetime,
        uptime: timedelta,
        update_count: int,
        current_ssid: str,
        last_save_time: float,
        ssid_data: Dict[str, Any],
        rx_rate: float,
        tx_rate: float,
        limits_data: Dict[str, Any],
        interval: float,
        session_rx: int,
        session_tx: int,
    ) -> str:
        """
        Build legacy string-based display for non-rich environments.

        Args:
            interface: Network interface name
            pid: Current process ID
            current_time: Current datetime
            uptime: Application uptime
            update_count: Number of updates
            current_ssid: Connected SSID or None
            last_save_time: Timestamp of last save
            ssid_data: Usage data for current SSID
            rx_rate: Current download rate
            tx_rate: Current upload rate
            limits_data: Data limits configuration
            interval: Update interval
            session_rx: Session download bytes
            session_tx: Session upload bytes

        Returns:
            str: Formatted string for display
        """
        lines = []
        lines.append(f"Network Interface: {interface}")
        lines.append(f"WiFi Tracker PID: {pid}")
        lines.append(
            f"Time: {current_time.strftime('%H:%M:%S')} | Uptime: {self.format_duration(uptime)}"
        )
        lines.append("-" * 50)

        status = f"Connected to {current_ssid}" if current_ssid else "Disconnected"
        lines.append(f"Status: {status}")

        if current_ssid:
            lines.append(f"Download Rate: {self.format_rate(rx_rate)}")
            lines.append(f"Upload Rate:   {self.format_rate(tx_rate)}")
            lines.append("-" * 50)

            lines.append("Session Usage:")
            lines.append(f"  Down: {self.format_bytes(session_rx)}")
            lines.append(f"  Up:   {self.format_bytes(session_tx)}")
            lines.append(f"  Total: {self.format_bytes(session_rx + session_tx)}")

            if ssid_data:
                lines.append("-" * 20)
                lines.append(f"Lifetime Usage for {current_ssid}:")
                total_rx = ssid_data.get("total_rx", 0)
                total_tx = ssid_data.get("total_tx", 0)
                lines.append(f"  Total: {self.format_bytes(total_rx + total_tx)}")

        lines.append("-" * 50)
        lines.append(f"Updates: {update_count}")
        lines.append("Press Ctrl+C to exit")

        return "\n".join(lines)

    def create_layout(
        self,
        interface: str,
        pid: int,
        current_time: datetime,
        uptime: timedelta,
        update_count: int,
        current_ssid: str,
        ssid_data: Dict[str, Any],
        rx_rate: float,
        tx_rate: float,
        limits_data: Dict[str, Any],
        session_rx: int,
        session_tx: int,
    ) -> Layout:
        """Create the Rich layout for watch mode"""

        layout = Layout()

        # Header Info
        time_str = current_time.strftime("%H:%M:%S")
        uptime_str = self.format_duration(uptime)
        status_color = "green" if current_ssid else "red"
        status_text = (
            f"[{status_color}]{current_ssid or 'Disconnected'}[/{status_color}]"
        )

        # Create Header Panel
        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left", ratio=1)
        header_table.add_column(justify="center", ratio=1)
        header_table.add_column(justify="right", ratio=1)

        header_table.add_row(
            f"Interface: [bold cyan]{interface}[/]",
            f"WiFi: {status_text}",
            f"PID: [dim]{pid}[/]",
        )
        header_table.add_row(
            f"Time: {time_str}", f"Uptime: {uptime_str}", f"Updates: {update_count}"
        )

        layout.split_column(
            Layout(
                Panel(
                    header_table, title="WiFi Tracker", border_style="blue", box=ROUNDED
                ),
                name="header",
                size=6,
            ),
            Layout(name="body"),
        )

        if current_ssid and ssid_data:
            # Stats Table
            stats_table = Table(
                expand=True, box=ROUNDED, show_header=True, header_style="bold magenta"
            )
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Total", justify="right")
            stats_table.add_column("Download (RX)", justify="right", style="green")
            stats_table.add_column("Upload (TX)", justify="right", style="blue")

            # Session Stats
            session_total = session_rx + session_tx
            stats_table.add_row(
                "Session Usage",
                self.format_bytes(session_total),
                f"↓ {self.format_bytes(session_rx)}",
                f"↑ {self.format_bytes(session_tx)}",
            )

            # Today's Stats
            today = datetime.now().strftime("%Y-%m-%d")
            daily_data = ssid_data.get("daily", {}).get(today, {})
            daily_rx = daily_data.get("rx", 0)
            daily_tx = daily_data.get("tx", 0)
            daily_total = daily_rx + daily_tx

            stats_table.add_row(
                "Today's Usage",
                self.format_bytes(daily_total),
                f"↓ {self.format_bytes(daily_rx)}",
                f"↑ {self.format_bytes(daily_tx)}",
            )

            # Total Stats
            total_rx = ssid_data.get("total_rx", 0)
            total_tx = ssid_data.get("total_tx", 0)
            total_usage = total_rx + total_tx

            stats_table.add_row(
                "Lifetime Usage",
                self.format_bytes(total_usage),
                f"↓ {self.format_bytes(total_rx)}",
                f"↑ {self.format_bytes(total_tx)}",
            )

            # Rates Panel content
            rates_table = Table.grid(expand=True)
            rates_table.add_column(justify="center", ratio=1)
            rates_table.add_column(justify="center", ratio=1)

            rates_table.add_row(
                f"[bold green]↓ {self.format_rate(rx_rate)}[/]",
                f"[bold blue]↑ {self.format_rate(tx_rate)}[/]",
            )

            # Limits (if any)
            limits_panel = None
            if current_ssid in limits_data:
                limit_info = limits_data[current_ssid]
                limit_bytes = limit_info.get("limit", 0)
                interval = limit_info.get("interval", "monthly")

                if limit_bytes > 0:
                    period_usage = self._calculate_period_usage(ssid_data, interval)
                    usage_percent = min(100, (period_usage / limit_bytes) * 100)
                    remaining = max(0, limit_bytes - period_usage)

                    color = "green"
                    if usage_percent > 80:
                        color = "yellow"
                    if usage_percent > 95:
                        color = "red"

                    # Create a custom progress bar using text since Rich Progress needs context manager or complex handling
                    width = 40
                    filled = int(width * (usage_percent / 100))
                    bar = f"[{color}]{'━' * filled}[/][dim white]{'━' * (width - filled)}[/]"

                    limits_table = Table.grid(expand=True)
                    limits_table.add_column()
                    limits_table.add_row(
                        f"[bold]{interval.capitalize()} Limit[/]: {self.format_bytes(period_usage)} / {self.format_bytes(limit_bytes)} ({usage_percent:.1f}%)"
                    )
                    limits_table.add_row(bar)
                    limits_table.add_row(f"Remaining: {self.format_bytes(remaining)}")

                    limits_panel = Panel(
                        limits_table,
                        title="Data Limit",
                        border_style=color,
                        box=ROUNDED,
                    )

            # Assemble Body
            body_layout = Layout()

            if limits_panel:
                body_layout.split_column(
                    Layout(
                        Panel(
                            rates_table,
                            title="Live Speed",
                            border_style="magenta",
                            box=ROUNDED,
                        ),
                        size=5,
                    ),
                    Layout(
                        Panel(
                            stats_table,
                            title=f"Statistics ({current_ssid})",
                            box=ROUNDED,
                        )
                    ),
                    Layout(limits_panel, size=5),
                )
            else:
                body_layout.split_column(
                    Layout(
                        Panel(
                            rates_table,
                            title="Live Speed",
                            border_style="magenta",
                            box=ROUNDED,
                        ),
                        size=5,
                    ),
                    Layout(
                        Panel(
                            stats_table,
                            title=f"Statistics ({current_ssid})",
                            box=ROUNDED,
                        )
                    ),
                )

            layout["body"].update(body_layout)

        else:
            # Not connected
            layout["body"].update(
                Panel(
                    Align.center("[bold red]Not connected to WiFi[/]"),
                    box=ROUNDED,
                    title="Status",
                )
            )

        return layout

    def print_top_network_apps(self, apps: list) -> None:
        """Print top network apps in a formatted table"""
        if not RICH_AVAILABLE:
            if not apps:
                print("No active network apps found.")
                return
            print(f"{'PID':>6}  {'User':<12} {'App':<20} {'Conns':>5}  {'Note'}")
            print("-" * 70)
            for app in apps:
                pid = str(app.get("pid", "N/A"))
                user = app.get("user", "unknown")[:12]
                name = app.get("name", "unknown")[:20]
                conns = str(app.get("connections", 0))
                print(f"{pid:>6}  {user:<12} {name:<20} {conns:>5}")
            print("\n  Note: Bytes shown are total process I/O (disk+network), not network-only.")
            return

        table = Table(title="Top Network Applications", box=ROUNDED, expand=True)

        table.add_column("PID", justify="right", style="dim")
        table.add_column("User", style="cyan")
        table.add_column("App Name", style="bold white")
        table.add_column("Conns", justify="right", style="yellow")
        table.add_column("I/O Total", justify="right", style="dim")

        for app in apps:
            pid = str(app.get("pid", "N/A"))
            user = app.get("user", "unknown")
            name = app.get("name", "unknown")
            conns = str(app.get("connections", 0))
            total = self.format_bytes(app.get("total_bytes", 0))

            table.add_row(pid, user, name, conns, total)

        self.console.print(table)
        self.console.print("  [dim]Note: I/O Total is process-wide (disk+network), not network-only. Conns = active network connections.[/dim]")

    def print_detailed_stats(
        self,
        usage_data: Dict[str, Any],
        limits_data: Dict[str, Any],
        current_ssid: Optional[str] = None,
        current_measurement: Optional[Dict[str, Any]] = None,
        custom_start_date: Optional[datetime] = None,
        custom_end_date: Optional[datetime] = None,
    ) -> None:
        """Print detailed statistics using Rich"""
        if not RICH_AVAILABLE:
            print("Rich library required.")
            return

        start_label = "Today"
        if custom_start_date and custom_end_date:
            start_label = f"{custom_start_date.strftime('%Y-%m-%d')} to {custom_end_date.strftime('%Y-%m-%d')}"
        elif custom_start_date:
            start_label = f"{custom_start_date.strftime('%Y-%m-%d')} to today"
        elif custom_end_date and not custom_start_date:
            start_label = f"to {custom_end_date.strftime('%Y-%m-%d')}"

        table = Table(
            title="📊 Enhanced WiFi Usage Statistics", box=ROUNDED, expand=True
        )

        table.add_column("SSID", style="bold cyan")
        table.add_column("Total Usage", justify="right")
        table.add_column(start_label, justify="right")
        table.add_column("Connections", justify="right")
        table.add_column("Last Seen", style="dim")
        table.add_column("Limit", justify="center")

        sorted_ssids = sorted(
            usage_data.items(),
            key=lambda x: x[1].get("total_rx", 0) + x[1].get("total_tx", 0),
            reverse=True,
        )

        for ssid, data in sorted_ssids:
            # Total
            total = data.get("total_rx", 0) + data.get("total_tx", 0)

            # Custom range or Today
            if custom_start_date or custom_end_date:
                period_usage = self._calculate_period_usage(
                    data, "monthly", custom_start_date, custom_end_date
                )
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                daily_data = data.get("daily", {}).get(today, {})
                period_usage = daily_data.get("rx", 0) + daily_data.get("tx", 0)

            # Info
            conns = str(data.get("connection_count", 0))
            last_seen = data.get("last_seen", "Unknown")

            # Limit
            limit_str = "-"
            if ssid in limits_data:
                limit_info = limits_data[ssid]
                limit = limit_info.get("limit", 0)
                interval = limit_info.get("interval", "monthly")
                if limit > 0:
                    limit_usage = self._calculate_period_usage(
                        data, interval, custom_start_date, custom_end_date
                    )
                    percent = (limit_usage / limit) * 100
                    color = "green" if percent < 80 else "red"
                    limit_str = f"[{color}]{percent:.0f}% of {interval[0].upper()}[/]"

            ssid_display = ssid
            if ssid == current_ssid:
                ssid_display = f"🟢 {ssid}"

            table.add_row(
                ssid_display,
                self.format_bytes(total),
                self.format_bytes(period_usage),
                conns,
                last_seen,
                limit_str,
            )

        self.console.print(table)

    def print_all_stats(
        self,
        usage_data: Dict[str, Any],
        limits_data: Dict[str, Any],
        current_ssid: str = None,
        current_measurement: Dict[str, Any] = None,
    ) -> None:
        """Print detailed stats (using same format as detailed for now, but potentially expanded)"""
        # For now, reuse the detailed stats table as it's cleaner
        self.print_detailed_stats(
            usage_data, limits_data, current_ssid, current_measurement
        )

    def print_ascii_graph(self, hourly_data: list, ssid: str, width: int = 50) -> None:
        """Print a simple ASCII bar graph of hourly usage.

        Args:
            hourly_data: List of (hour_label, bytes_used) tuples for last 24h.
            ssid: Network name for display.
            width: Max bar width in characters.
        """
        if not hourly_data:
            return

        max_val = max((v for _, v in hourly_data), default=1) or 1
        lines = [f"\n  Usage graph for {ssid} (last 24h):"]
        lines.append(f"  {'Hour':<6} {'Used':<10} Graph")
        lines.append(f"  {'─'*6} {'─'*10} {'─'*width}")

        for hour_label, bytes_used in hourly_data:
            bar_len = int((bytes_used / max_val) * width) if max_val > 0 else 0
            bar = "█" * bar_len + "░" * (width - bar_len)
            size = self.format_bytes(bytes_used)
            lines.append(f"  {hour_label:<6} {size:<10} {bar}")

        if self.console:
            self.console.print("\n".join(lines))
        else:
            print("\n".join(lines))

    def print_quick_status(self, ssid: str, today_usage: int, total_usage: int,
                           rate_up: float, rate_down: float,
                           limit: int = 0, top_app: str = "") -> None:
        """Print a compact one-line status."""
        size_today = self.format_bytes(today_usage)
        size_total = self.format_bytes(total_usage)
        up = self.format_rate(rate_up)
        down = self.format_rate(rate_down)

        parts = [f"  {ssid}"]
        parts.append(f"Today: {size_today}")
        parts.append(f"Total: {size_total}")
        parts.append(f"↑{up} ↓{down}")
        if limit > 0:
            pct = (today_usage / limit) * 100
            parts.append(f"Limit: {pct:.0f}%")
        if top_app:
            parts.append(f"Top: {top_app}")

        line = " │ ".join(parts)
        if self.console:
            self.console.print(f"\n  {line}\n")
        else:
            print(f"\n  {line}\n")
