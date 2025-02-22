import psutil
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime, timedelta

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
x_data, y_data = [], []
line, = ax1.plot(x_data, y_data, color='blue', lw=2)

# Set up the CPU utilization plot
ax1.set_ylim(0, 100)  # CPU usage percentage range
ax1.set_xlim(0, 100)  # Number of data points to display
ax1.set_xlabel('Time (seconds)')
ax1.set_ylabel('CPU Usage (%)')
ax1.set_title('Real-Time CPU Usage')
ax1.grid(True)

# Set up the text box for additional CPU information
text_box = ax2.text(0.05, 0.95, '', transform=ax2.transAxes, fontsize=10, 
                    verticalalignment='top', bbox=dict(facecolor='white', alpha=0.5))
ax2.axis('off')  # Hide the axis for the text box

# Function to gather additional CPU information
def get_cpu_info():
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=True)
        cpu_cores = psutil.cpu_count(logical=False)
        uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        processes = len(psutil.pids())
        
        # Handle cases where cpu_freq might return None (e.g., on some virtual machines)
        current_freq = cpu_freq.current / 1000 if cpu_freq else "N/A"
        max_freq = cpu_freq.max / 1000 if cpu_freq else "N/A"
        
        info = (
            f"Current Utilization: {psutil.cpu_percent(interval=0.1):.1f}%\n"
            f"Speed: {current_freq:.2f} GHz\n"
            f"Base Speed: {max_freq:.2f} GHz\n"
            f"Sockets: 1\n"
            f"Cores: {cpu_cores}\n"
            f"Logical Processors: {cpu_count}\n"
            f"Virtualization: {'Enabled' if psutil.cpu_stats().ctx_switches > 0 else 'Disabled'}\n"
            f"Uptime: {str(uptime).split('.')[0]}\n"
            f"Processes: {processes}\n"
            f"Threads: {psutil.Process().num_threads()}\n"
        )
        return info
    except Exception as e:
        return f"Error fetching CPU info: {e}"

# Function to update the plot and text box
def animate(i):
    try:
        # Get CPU usage percentage
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        # Append the new data point with the current time
        current_time = datetime.now()
        x_data.append(current_time)
        y_data.append(cpu_usage)
        
        # Keep the list length to 100
        if len(x_data) > 100:
            x_data.pop(0)
            y_data.pop(0)
        
        # Update the line data
        line.set_data(x_data, y_data)
        
        ax1.set_xlim(x_data[0], x_data[-1])
        fig.autofmt_xdate()  # Auto-format the x-axis dates
        
        # Update the text box with CPU information
        text_box.set_text(get_cpu_info())
        
        return line, text_box
    except Exception as e:
        print(f"Error during animation: {e}")
        return line, text_box

ani = animation.FuncAnimation(fig, animate, interval=100, blit=False, save_count=100)

# Show the plot
plt.tight_layout()
plt.show()
