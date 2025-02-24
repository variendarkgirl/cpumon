# System Monitoring Dashboard

A basic real-time system monitoring dashboard built with Python, utilizing the `psutil` and `rich` libraries to display key system metrics such as CPU usage, memory utilization, network activity, battery status, and system temperatures in a visually appealing format.
![image](https://github.com/user-attachments/assets/e2067e74-a67a-486d-9bd6-2bf7b1f0b4b7)

<img width="402" alt="image" src="https://github.com/user-attachments/assets/b78c923c-09ba-4fd8-83f3-9c2f87b354ec" />
<img width="402" alt="image" src="https://github.com/user-attachments/assets/2147e5b0-7868-4791-929b-6644285318e0" />
<img width="402" alt="image" src="https://github.com/user-attachments/assets/0ef5e71a-95fc-4c34-a51a-0f7e91068433" />
<img width="402" alt="image" src="https://github.com/user-attachments/assets/66473c4d-4fa8-48a2-8a53-a0ad55a8f1a8" />
" />


## Features

- Real-time monitoring of CPU usage with a heartbeat-like wave representation.
- Displays memory utilization (total, used, free, cached).
- Shows network data (sent and received bytes).
- Battery status including percentage and charging status.
- System temperatures (if available).
- Lists top CPU-consuming processes.

## Requirements

- Python 3.12
- `psutil`
- `rich`

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/variendarkgirl/cpumon.git
   cd cpumon
Install the required packages:
pip install psutil rich
## Usage
To run the system monitoring dashboard, execute the following command in your terminal:

   ```bash
   python cpu.py
   python cpuchart.py
   ```

## This will launch the dashboard in your terminal, displaying real-time system metrics.
Example Output
The dashboard will show:

CPU Usage: Visual representation of CPU usage per core and total CPU usage.
Memory (RAM): Total, used, free, and cached memory.
Network Data: Amount of data sent and received over the network.
Battery Status: Current battery percentage and charging status.
System Temperatures: Current CPU temperature (if available).
Top Processes: List of the top 5 CPU-consuming processes.
Contributing
Contributions are welcome! If you would like to contribute to this project, please fork the repository and create a new branch for your feature or bug fix. Then, submit a pull request with a description of your changes.
