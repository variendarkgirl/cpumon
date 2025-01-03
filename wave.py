import psutil
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime, timedelta

# Initialize the figure and axis
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
x_data, y_data = [], []
line, = ax1.plot(x_data, y_data, color='blue')

# Set up the CPU utilization plot
ax1.set_ylim(0, 100)  # CPU usage percentage range
ax1.set_xlim(0, 100)  # Number of data points to display
ax1.set_xlabel('Time')
ax1.set_ylabel('CPU Usage (%)')
ax1.set_title('Real-Time CPU Usage')

# Set up the text box for additional CPU information
text_box = ax2.text(0.05, 0.95, '', transform=ax2.transAxes, fontsize=10, verticalalignment='top')
ax2.axis('off')  # Hide the axis for the text box

# Function to gather additional CPU information
def get_cpu_info():
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count(logical=True)
    cpu_cores = psutil.cpu_count(logical=False)
    uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
    processes = len(psutil.pids())

    info = (
        f"60 seconds Utilization: {psutil.cpu_percent(interval=0.1):.1f}%\n"
        f"Speed: {cpu_freq.current / 1000:.2f} GHz\n"
        f"Base speed: {cpu_freq.max / 1000:.2f} GHz\n"
        f"Sockets: 1\n"
        f"Cores: {cpu_cores}\n"
        f"Logical processors: {cpu_count}\n"
        f"Virtualization: {'Enabled' if psutil.cpu_stats().ctx_switches > 0 else 'Disabled'}\n"
        f"Up time: {uptime}\n"
        f"Processes: {processes}\n"
        f"Threads: {psutil.Process().num_threads()}\n"
        f"Handles: {psutil.Process().num_handles()}"
    )
    return info

# Function to update the plot and text box
def animate(i):
    # Get CPU usage percentage
    cpu_usage = psutil.cpu_percent(interval=0.1)
    
    # Append the new data point
    x_data.append(i)
    y_data.append(cpu_usage)
    
    # Keep the list length to 100
    if len(x_data) > 100:
        x_data.pop(0)
        y_data.pop(0)
    
    # Update the line data
    line.set_data(x_data, y_data)
    
    # Adjust the x-axis limits to create a scrolling effect
    ax1.set_xlim(max(0, i - 100), max(100, i))
    
    # Update the text box with CPU information
    text_box.set_text(get_cpu_info())
    
    return line, text_box

# Create the animation
ani = animation.FuncAnimation(fig, animate, interval=100, blit=True, save_count=100)

# Show the plot
plt.tight_layout()
plt.show()