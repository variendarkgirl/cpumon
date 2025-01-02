import psutil
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from math import sin, pi
from time import sleep
import platform

console = Console()

# Parameters for heartbeat-like animation
wave_length = 60  # Increased wave length for larger display
wave_step = 0

def heartbeat_wave(amplitude, step, length):
    """Generate a heartbeat-like wave pattern."""
    return [abs(sin((step + i) * (2 * pi / length))) * amplitude for i in range(length)]

def get_system_info():
    """Retrieve system information using psutil."""
    # CPU utilization
    cpu_percentages = psutil.cpu_percent(percpu=True)
    cpu_total = psutil.cpu_percent()

    # Memory utilization
    memory = psutil.virtual_memory()
    total_memory = round(memory.total / (1024 ** 3), 2)  # GB
    used_memory = round(memory.used / (1024 ** 3), 2)
    free_memory = round(memory.available / (1024 ** 3), 2)

    # On Linux, we can access cached memory
    cached_memory = round(memory.cached / (1024 ** 3), 2) if hasattr(memory, 'cached') else 0

    # Network
    net_io = psutil.net_io_counters()
    total_sent = round(net_io.bytes_sent / 1024, 2)  # KB
    total_recv = round(net_io.bytes_recv / 1024, 2)

    # Battery
    battery = psutil.sensors_battery()
    battery_percent = battery.percent if battery else "N/A"
    battery_status = "Charging" if battery and battery.power_plugged else "Discharging"

    # Temperatures
    cpu_temp = "N/A"
    if hasattr(psutil, "sensors_temperatures"):
        temps = psutil.sensors_temperatures()
        cpu_temp = temps['coretemp'][0].current if 'coretemp' in temps else "N/A"

    # Processes
    processes = [(p.info['name'], p.info['cpu_percent'], p.info['memory_percent']) for p in
                 psutil.process_iter(['name', 'cpu_percent', 'memory_percent']) if p.info['cpu_percent']]

    return {
        "cpu_percentages": cpu_percentages,
        "cpu_total": cpu_total,
        "memory": {
            "total": total_memory,
            "used": used_memory,
            "free": free_memory,
            "cached": cached_memory,
        },
        "network": {
            "sent": total_sent,
            "recv": total_recv,
        },
        "battery": {
            "percent": battery_percent,
            "status": battery_status,
        },
        "temperature": {
            "cpu": cpu_temp,
        },
        "processes": sorted(processes, key=lambda x: x[1], reverse=True)[:5]  # Top 5 CPU-consuming processes
    }

def generate_display(info):
    global wave_step
    wave_step += 1

    # CPU Utilization Table with Heartbeat Wave
    cpu_table = Table(title="[bold blue]CPU Usage", show_header=True, header_style="bold yellow")
    cpu_table.add_column("Core", justify="left")
    cpu_table.add_column("Usage (%)", justify="right")
    cpu_table.add_column("Visual", justify="center")
    
    for i, cpu in enumerate(info["cpu_percentages"]):
        wave = heartbeat_wave(20, wave_step + i, wave_length)  # Increased amplitude for better visibility
        wave_visual = "".join(["█" if val > 10 else "░" for val in wave])  # More pronounced visual
        cpu_table.add_row(f"Core {i}", f"[cyan]{cpu}%", f"[green]{wave_visual}")
    
    total_wave = heartbeat_wave(20, wave_step, wave_length)
    total_wave_visual = "".join(["█" if val > 10 else "░" for val in total_wave])
    cpu_table.add_row("Total", f"[magenta]{info['cpu_total']}%", f"[red]{total_wave_visual}")

    # Memory Utilization Table
    memory_table = Table(title="[bold green]Memory (RAM)", show_header=True, header_style="bold white")
    memory_table.add_column("Type", justify="left")
    memory_table.add_column("Amount (GB)", justify="right")
    memory_table.add_row("Total", f"[cyan]{info['memory']['total']}")
    memory_table.add_row("Used", f"[magenta]{info['memory']['used']} GB")
    memory_table.add_row("Free", f"[green]{info['memory']['free']} GB")
    memory_table.add_row("Cached", f"[yellow]{info['memory']['cached']} GB")

    # Network Usage Table with Heartbeat Wave
    network_table = Table(title="[bold cyan]Network Data", show_header=True, header_style="bold magenta")
    network_table.add_column("Type", justify="left")
    network_table.add_column("Amount (KB)", justify="right")
    network_wave = heartbeat_wave(10, wave_step, wave_length)
    network_visual = "".join(["█" if val > 5 else "░" for val in network_wave])
    network_table.add_row("Sent", f"[yellow]{info['network']['sent']} KB")
    network_table.add_row("Received", f"[green]{info['network']['recv']} KB")
    network_table.add_row("Visual", f"[blue]{network_visual}")

    # Battery Panel
    battery_table = Table(title="[bold green]Battery Status", show_header=True, header_style="bold cyan")
    battery_table.add_column("Status", justify="left")
    battery_table.add_column("Value", justify="right")
    battery_table.add_row("Percent", f"[yellow]{info['battery']['percent']}%")
    battery_table.add_row("Status", f"[magenta]{info['battery']['status']}")

    # Temperature Panel
    temp_table = Table(title="[bold red]System Temperatures", show_header=True, header_style="bold yellow")
    temp_table.add_column("Component", justify="left")
    temp_table.add_column("Temperature (°C)", justify="right")
    temp_table.add_row("CPU", f"[red]{info['temperature']['cpu']}")

    # Top Processes Panel
    process_table = Table(title="[bold magenta]Top 5 Processes (CPU %)", show_header=True, header_style="bold cyan")
    process_table.add_column("Name", justify="left")
    process_table.add_column("CPU %", justify="right")
    process_table.add_column("Memory %", justify="right")
    for proc in info["processes"]:
        process_table.add_row(proc[0], f"[red]{proc[1]}%", f"[yellow]{proc[2]}%")

    # Combine Panels
    overview_panel = Panel(
        f"[yellow]CPU Total:[/yellow] {info['cpu_total']}%\n"
        f"[green]Memory Used:[/green] {info['memory']['used']} GB / {info['memory']['total']} GB\n"
        f"[cyan]Network Sent:[/cyan] {info['network']['sent']} KB | [cyan]Received:[/cyan] {info['network']['recv']} KB\n"
        f"[green]Battery:[/green] {info['battery']['percent']}% ({info['battery']['status']})\n"
        f"[red]CPU Temperature:[/red] {info['temperature']['cpu']}°C",
        title="[bold blue]System Overview",
        border_style="bold green",
    )

    return cpu_table, memory_table, network_table, process_table, overview_panel, battery_table, temp_table

def main():
    """Main function to run the system monitoring dashboard."""
    with Live(auto_refresh=True, refresh_per_second=2) as live:
        while True:
            system_info = get_system_info()
            cpu_table, memory_table, network_table, process_table, overview_panel, battery_table, temp_table = generate_display(system_info)

            # Layout
            layout = Table.grid(expand=True)
            layout.add_column(justify="center", ratio=1)
            layout.add_column(justify="center", ratio=1)
            layout.add_row(overview_panel, cpu_table)
            layout.add_row(memory_table, network_table)
            layout.add_row(battery_table, temp_table)
            layout.add_row(process_table)

            live.update(layout)
            sleep(1)

if __name__ == "__main__":
    main()
