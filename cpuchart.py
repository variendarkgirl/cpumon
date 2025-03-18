import sys
import os
import json
import time
import psutil
import wmi
from datetime import datetime
from collections import deque
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, QSettings
from PyQt5.QtGui import QColor, QIcon, QFont, QPalette, QBrush, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QLabel,
    QTreeWidget, QTreeWidgetItem, QSplitter, QStyleFactory, 
    QGridLayout, QProgressBar, QAction, QInputDialog, QMessageBox,
    QDialog, QLineEdit, QPushButton, QHBoxLayout, QCheckBox,
    QComboBox, QFileDialog, QToolBar, QStatusBar, QFrame
)
import pyqtgraph as pg

# Constants
MAX_CHART_HISTORY = 120  # 2 minutes at 1s updates
CONFIG_FILE = 'taskmgr_settings.json'
PRIORITY_LEVELS = {
    "Realtime": psutil.REALTIME_PRIORITY_CLASS,
    "High": psutil.HIGH_PRIORITY_CLASS,
    "Above Normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "Normal": psutil.NORMAL_PRIORITY_CLASS,
    "Below Normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "Low": psutil.IDLE_PRIORITY_CLASS
}

# Process data collection worker thread
class ProcessWorker(QThread):
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        
    def stop(self):
        self._running = False
        self.wait()
        
    def run(self):
        previous_data = {}
        
        while self._running:
            try:
                current_time = time.time()
                current_data = {}
                
                # Get all processes with batch collection for efficiency
                for proc in psutil.process_iter(['pid', 'name', 'status', 'username', 
                                              'cpu_percent', 'memory_percent']):
                    try:
                        pid = proc.info['pid']
                        process_info = {
                            'name': proc.info['name'],
                            'status': proc.info['status'],
                            'username': proc.info['username'] or 'N/A',
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_percent': proc.info['memory_percent'],
                            'disk_usage': 0,
                            'network_usage': 0,
                            'timestamp': current_time
                        }


                        
                                try:
                                    io = proc.io_counters()
                                    process_info['disk_read'] = io.read_bytes
                                    process_info['disk_write'] = io.write_bytes
                                    process_info['disk_usage'] = io.read_bytes + io.write_bytes
                                    
                                    # Calculate rate if we have previous data
                                    if pid in previous_data and 'disk_read' in previous_data[pid]:
                                        time_diff = current_time - previous_data[pid]['timestamp']
                                        if time_diff > 0:
                                            read_rate = (io.read_bytes - previous_data[pid]['disk_read']) / time_diff
                                            write_rate = (io.write_bytes - previous_data[pid]['disk_write']) / time_diff
                                            process_info['disk_read_rate'] = read_rate
                                            process_info['disk_write_rate'] = write_rate
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                                
                                # Try to get network info
                                try:
                                    # Use net_connections() instead of the deprecated connections()
                                    connections = proc.net_connections()
                                    if connections:
                                        process_info['network_connections'] = len(connections)
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                                    
                                # Try to get process creation time
                                try:
                                    create_time = proc.create_time()
                                    process_info['create_time'] = create_time
                                    process_info['running_time'] = time.time() - create_time
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                                    
                                # Get command line if possible
                                try:
                                    cmdline = proc.cmdline()
                                    process_info['cmdline'] = ' '.join(cmdline) if cmdline else ''
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                                    
                                # Get current working directory
                                try:
                                    process_info['cwd'] = proc.cwd()
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                                    
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            # Partial info is still useful
                            pass
                            
                        current_data[pid] = process_info
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                

class PerformanceWorker(QThread):
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self.prev_disk_io = None
        self.prev_net_io = None
        self.prev_time = time.time()
        
    def stop(self):
        self._running = False
        self.wait()
        
    def run(self):
        while self._running:
            try:
                current_time = time.time()
                perf_data = {}
                
                # CPU
                perf_data['cpu_percent'] = psutil.cpu_percent(interval=None)
                perf_data['cpu_per_core'] = psutil.cpu_percent(interval=None, percpu=True)
                perf_data['cpu_count'] = psutil.cpu_count()
                perf_data['cpu_freq'] = psutil.cpu_freq()
                
                # Memory
                memory = psutil.virtual_memory()
                perf_data['memory'] = {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent,
                    'free': memory.free
                }
                
                # Swap
                swap = psutil.swap_memory()
                perf_data['swap'] = {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent
                }
                
                # Disk
                disk_io = psutil.disk_io_counters()
                if self.prev_disk_io is not None:
                    # Calculate rates
                    time_diff = current_time - self.prev_time
                    if time_diff > 0:
                        read_rate = (disk_io.read_bytes - self.prev_disk_io.read_bytes) / time_diff
                        write_rate = (disk_io.write_bytes - self.prev_disk_io.write_bytes) / time_diff
                        
                
                # Disk usage for all partitions
                disk_partitions = []
                for part in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disk_partitions.append({
                            'device': part.device,
                            'mountpoint': part.mountpoint,
                            'fstype': part.fstype,
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': usage.percent
                        })
                    except (PermissionError, FileNotFoundError):
                        continue
                perf_data['disk_partitions'] = disk_partitions
                
                # Network
                net_io = psutil.net_io_counters()
                if self.prev_net_io is not None:
                    # Calculate rates
                    time_diff = current_time - self.prev_time
                    if time_diff > 0:
                        bytes_sent_rate = (net_io.bytes_sent - self.prev_net_io.bytes_sent) / time_diff
                        bytes_recv_rate = (net_io.bytes_recv - self.prev_net_io.bytes_recv) / time_diff
                        
                        perf_data['network'] = {
                            'bytes_sent': net_io.bytes_sent,
                            'bytes_recv': net_io.bytes_recv,
                            'packets_sent': net_io.packets_sent,
                            'packets_recv': net_io.packets_recv,
                            'bytes_sent_rate': bytes_sent_rate,
                            'bytes_recv_rate': bytes_recv_rate
                        }
                self.prev_net_io = net_io
                
                # System load over time (1, 5, 15 min averages)
                try:
                    load_avg = psutil.getloadavg()
                    perf_data['load_avg'] = load_avg
                except (AttributeError, OSError):
                    # Not available on Windows
                    pass
                
                # Battery info if available
                if hasattr(psutil, 'sensors_battery'):
                    battery = psutil.sensors_battery()
                    if battery:
                        perf_data['battery'] = {
                            'percent': battery.percent,
                            'power_plugged': battery.power_plugged,
                            'secsleft': battery.secsleft
                        }
                
                # Temperature sensors if available
                if hasattr(psutil, 'sensors_temperatures'):
                    try:
                        temps = psutil.sensors_temperatures()
                        if temps:
                            perf_data['temperatures'] = temps
                    except (AttributeError, OSError):
                        pass
                
                # Emit the collected data
                self.data_updated.emit(perf_data)
                self.prev_time = current_time
                
            except Exception as e:
                self.error_occurred.emit(f"Performance collection error: {str(e)}")
            
            # Sleep for a short while to save resources
            time.sleep(1)

# Search dialog for finding processes
class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Process")
        self.resize(300, 100)
        
        layout = QVBoxLayout()
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Enter process name or PID...")
        layout.addWidget(self.search_field)
        
        button_layout = QHBoxLayout()
        self.case_sensitive = QCheckBox("Case sensitive")
        button_layout.addWidget(self.case_sensitive)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.search_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Enable search on Enter key
        self.search_field.returnPressed.connect(self.accept)
    
    def get_search_text(self):
        return self.search_field.text()
    
    def is_case_sensitive(self):
        return self.case_sensitive.isChecked()

# Process Details Dialog
class ProcessDetailsDialog(QDialog):
    def __init__(self, pid, process_data, parent=None):
        super().__init__(parent)
        self.pid = pid
        self.process_data = process_data
        self.setWindowTitle(f"Process Details - {process_data.get('name', 'Unknown')} ({pid})")
        self.resize(500, 400)
        self.create_ui()
        
    def create_ui(self):
        layout = QVBoxLayout()
        
        # Create tabs for different information categories
        tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        gen_layout = QGridLayout()
        
        # Process info
        gen_layout.addWidget(QLabel("Name:"), 0, 0)
        gen_layout.addWidget(QLabel(self.process_data.get('name', 'Unknown')), 0, 1)
        
        gen_layout.addWidget(QLabel("PID:"), 1, 0)
        gen_layout.addWidget(QLabel(str(self.pid)), 1, 1)
        
        gen_layout.addWidget(QLabel("Status:"), 2, 0)
        gen_layout.addWidget(QLabel(self.process_data.get('status', 'Unknown')), 2, 1)
        
        gen_layout.addWidget(QLabel("User:"), 3, 0)
        gen_layout.addWidget(QLabel(self.process_data.get('username', 'Unknown')), 3, 1)
        
        # Format the creation time nicely if available
        if 'create_time' in self.process_data:
            create_time_str = datetime.fromtimestamp(
                self.process_data['create_time']
            ).strftime('%Y-%m-%d %H:%M:%S')
            gen_layout.addWidget(QLabel("Started:"), 4, 0)
            gen_layout.addWidget(QLabel(create_time_str), 4, 1)
        
        # Add path if available
        if 'cwd' in self.process_data:
            gen_layout.addWidget(QLabel("Working Directory:"), 5, 0)
            gen_layout.addWidget(QLabel(self.process_data.get('cwd', 'Unknown')), 5, 1)
        
        # Add command line if available
        if 'cmdline' in self.process_data:
            gen_layout.addWidget(QLabel("Command Line:"), 6, 0)
            cmdline_label = QLabel(self.process_data.get('cmdline', ''))
            cmdline_label.setWordWrap(True)
            gen_layout.addWidget(cmdline_label, 6, 1)
        
        general_tab.setLayout(gen_layout)
        tabs.addTab(general_tab, "General")
        
        # Performance tab
        perf_tab = QWidget()
        perf_layout = QGridLayout()
        
        perf_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
        perf_layout.addWidget(QLabel(f"{self.process_data.get('cpu_percent', 0):.1f}%"), 0, 1)
        
        perf_layout.addWidget(QLabel("Memory Usage:"), 1, 0)
        mem_percent = self.process_data.get('memory_percent', 0)
        mem_bytes = self.process_data.get('memory_bytes', 0)
        perf_layout.addWidget(QLabel(f"{mem_percent:.1f}% ({self.format_bytes(mem_bytes)})"), 1, 1)
        
        # Add disk read/write rates if available
        if 'disk_read_rate' in self.process_data:
            perf_layout.addWidget(QLabel("Disk Read Rate:"), 2, 0)
            perf_layout.addWidget(QLabel(f"{self.format_bytes(self.process_data['disk_read_rate'])}/s"), 2, 1)
            
            perf_layout.addWidget(QLabel("Disk Write Rate:"), 3, 0)
            perf_layout.addWidget(QLabel(f"{self.format_bytes(self.process_data['disk_write_rate'])}/s"), 3, 1)
        
        # Add network info if available
        if 'network_connections' in self.process_data:
            perf_layout.addWidget(QLabel("Network Connections:"), 4, 0)
            perf_layout.addWidget(QLabel(str(self.process_data['network_connections'])), 4, 1)
        
        perf_tab.setLayout(perf_layout)
        tabs.addTab(perf_tab, "Performance")
        
        # Add the tabs to the main layout
        layout.addWidget(tabs)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def format_bytes(self, size):
        power = 2**10
        n = 0
        units = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power and n < len(units)-1:
            size /= power
            n += 1
        return f"{size:.1f} {units[n]}"

# Main application class
class SystemMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Windows Task Manager")
        self.setWindowIcon(QIcon("taskmgr.ico"))
        self.resize(1200, 800)
        
        # Instance variables
        self.process_data = {}
        self.sorted_process_list = []
        self.chart_data = {
            'cpu': deque([0] * MAX_CHART_HISTORY, maxlen=MAX_CHART_HISTORY),
            'memory': deque([0] * MAX_CHART_HISTORY, maxlen=MAX_CHART_HISTORY),
            'disk': deque([0] * MAX_CHART_HISTORY, maxlen=MAX_CHART_HISTORY),
            'network': deque([0] * MAX_CHART_HISTORY, maxlen=MAX_CHART_HISTORY)
        }
        self.time_data = list(range(-MAX_CHART_HISTORY + 1, 1))
        
        # Create the UI
        self.init_ui()
        
        # Initialize background workers
        self.init_workers()
        
        # Load any saved settings
        self.load_settings()
        
        # Set up refresh timer for UI updates
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update_ui)
        self.refresh_timer.start(1000)  # Update UI every second
        
        # Show initial data
        self.update_ui()
    
    def init_ui(self):
        # Set the application style
        self.setStyleSheet("""
            QWidget { 
                font-family: Segoe UI; 
                font-size: 9pt; 
                background-color: #FFFFFF;
            }
            QTableWidget { 
                border: 1px solid #D4D4D4; 
                gridline-color: #EAEAEA;
            }
            QHeaderView::section { 
                background-color: #F0F0F0; 
                border: 1px solid #D4D4D4;
                padding: 4px;
            }
            QTabBar::tab { 
                padding: 8px; 
                border: 1px solid #D4D4D4;
            }
            QTabBar::tab:selected {
                background-color: #F0F0F0;
                border-bottom-color: #FFFFFF;
            }
            QProgressBar {
                border: 1px solid #D4D4D4;
                border-radius: 2px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007ACC;
            }
        """)

        # Create main toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Add actions
        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self.force_refresh)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        search_action = QAction("Search", self)
        search_action.triggered.connect(self.show_search_dialog)
        toolbar.addAction(search_action)
        
        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        toolbar.addAction(settings_action)
        
        # Create central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create the main tabs
        self.create_processes_tab()
        self.create_performance_tab()
        self.create_app_history_tab()
        self.create_startup_tab()
        self.create_users_tab()
        self.create_details_tab()
        self.create_services_tab()  # New tab for services
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # CPU usage indicator in status bar
        self.cpu_indicator = QLabel("CPU: 0%")
        self.status_bar.addPermanentWidget(self.cpu_indicator)
        
        # Memory usage indicator
        self.memory_indicator = QLabel("Memory: 0%")
        self.status_bar.addPermanentWidget(self.memory_indicator)
        
        # Process count indicator
        self.process_count = QLabel("Processes: 0")
        self.status_bar.addPermanentWidget(self.process_count)
    
    def init_workers(self):
        # Create and start process data worker
        self.process_worker = ProcessWorker()
        self.process_worker.data_updated.connect(self.update_process_data)
        self.process_worker.error_occurred.connect(self.show_error)
        self.process_worker.start()
        
        # Create and start performance data worker
        self.perf_worker = PerformanceWorker()
        self.perf_worker.data_updated.connect(self.update_performance_data)
        self.perf_worker.error_occurred.connect(self.show_error)
        self.perf_worker.start()
    
    #region Process Tab
    def create_processes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("View by:"))
        self.group_combo = QComboBox()
        self.group_combo.addItems(["All processes", "Apps only", "Background processes", "Windows processes"])
        self.group_combo.currentIndexChanged.connect(self.apply_process_filter)
        filter_layout.addWidget(self.group_combo)
        
        filter_layout.addStretch()
        
        # Add grouping options
        filter_layout.addWidget(QLabel("Group by:"))
        self.grouping_combo = QComboBox()
        self.grouping_combo.addItems(["None", "Process type", "Status", "User"])
        self.grouping_combo.currentIndexChanged.connect(self.apply_process_grouping)
        filter_layout.addWidget(self.grouping_combo)
        
        layout.addLayout(filter_layout)
        
        # Add process table
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(10)
        self.process_table.setHorizontalHeaderLabels([
            "Name", "PID", "Status", "User name", "CPU %", "Memory",
            "Disk I/O", "Network I/O", "GPU %", "Description"
        ])
        
        # Set column stretch behavior
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name column stretches
        for i in range(1, 10):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        
        # Enable sorting
        self.process_table.setSortingEnabled(True)
        
        # Enable context menu
        self.process_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self.show_process_menu)
        
        # Enable selection behavior
        self.process_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.process_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Connect double-click to show details
        self.process_table.cellDoubleClicked.connect(self.show_process_details)
        
        layout.addWidget(self.process_table)
        
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Processes")
    
    def update_process_table(self):
        if not self.process_data:
            return
            
        # Remember the current selection
        selected_items = self.process_table.selectedItems()
        selected_pid = None
        if selected_items:
            row = selected_items[0].row()
            pid_item = self.process_table.item(row, 1)
            if pid_item:
                selected_pid = int(pid_item.text())
        
        # Apply filters based on current filter settings
        filtered_pids = self.apply_process_filter()
        
        # Sort processes by CPU usage (descending) by default
        sorted_pids = sorted(
            filtered_pids, 
            key=lambda pid: self.process_data.get(pid, {}).get('cpu_percent', 0),
            reverse=True
        )
        self.sorted_process_list = sorted_pids
        
        # Update the table
        self.process_table.setSortingEnabled(False)  # Disable sorting while updating
        self.process_table.setRowCount(len(sorted_pids))
        
        for row, pid in enumerate(sorted_pids):
            process = self.process_data.get(pid, {})
            
            # Prepare cell items
            name_item = QTableWidgetItem(process.get('name', 'Unknown'))
            pid_item = QTableWidgetItem(str(pid))
            status_item = QTableWidgetItem(process.get('status', 'Unknown'))
            username_item = QTableWidgetItem(process.get('username', 'N/A'))
            
            cpu_value = process.get('cpu_percent', 0)
            cpu_item = QTableWidgetItem()
            cpu_item.setData(Qt.DisplayRole, f"{cpu_value:.1f}%")
            cpu_item.setData(Qt.UserRole, cpu_value)  # For sorting
            
            memory_bytes = process.get('memory_bytes', 0)
            memory_percent = process.get('memory_percent', 0)
            memory_item = QTableWidgetItem()
            memory_item.setData(Qt.DisplayRole, f"{memory_percent:.1f}% ({self.format_bytes(memory_bytes)})")
            memory_item.setData(Qt.UserRole, memory_percent)  # For sorting
            
            disk_usage = process.get('disk_usage', 0)
            disk_item = QTableWidgetItem(self.format_bytes(disk_usage))
            disk_item.setData(Qt.UserRole, disk_usage)  # For sorting
            
            network_usage = process.get('network_usage', 0)
            network_item = QTableWidgetItem(self.format_bytes(network_usage))
            network_item.setData(Qt.UserRole, network_usage)  # For sorting
            
            gpu_item = QTableWidgetItem("N/A")  # Placeholder
            desc_item = QTableWidgetItem("")  # Placeholder
            
            # Set items in the table
            items = [name_item, pid_item, status_item, username_item, 
                    cpu_item, memory_item, disk_item, network_item, gpu_item, desc_item]
            
            for col, item in enumerate(items):
                self.process_table.setItem(row, col, item)
                
                # Color high resource usage cells
                if col == 4 and cpu_value > 50:  # CPU
                    item.setForeground(QBrush(QColor("#CC0000")))
                elif col == 5 and memory_percent > 50:  # Memory
                    item.setForeground(QBrush(QColor("#CC0000")))
        
        self.process_table.setSortingEnabled(True)  # Re-enable sorting
        
        # Restore selection if the process still exists
        if selected_pid is not None:
            for row in range(self.process_table.rowCount()):
                pid_item = self.process_table.item(row, 1)
                if pid_item and int(pid_item.text()) == selected_pid:
                    self.process_table.selectRow(row)
                    break
    
    def apply_process_filter(self):
        filter_text = self.group_combo.currentText() if hasattr(self, 'group_combo') else "All processes"
        filtered_pids = []
        
        for pid, process in self.process_data.items():
            # Apply filtering logic based on selected filter
            if filter_text == "All processes":
                filtered_pids.append(pid)
            elif filter_text == "Apps only":
                # Simple heuristic to identify apps: they have a visible window
                if process.get('status') == 'running' and not process.get('name', '').startswith('System'):
                    filtered_pids.append(pid)
            elif filter_text == "Background processes":
                # Background processes usually don't have visible windows
                if process.get('status') in ['sleeping', 'disk-sleep', 'stopped']:
                    filtered_pids.append(pid)
            elif filter_text == "Windows processes":
                # Windows processes typically run as SYSTEM, LOCAL SERVICE, or NETWORK SERVICE
                username = process.get('username', '').lower()
                if 'system' in username or 'local service' in username or 'network service' in username:
                    filtered_pids.append(pid)
        
        return filtered_pids
    
    def apply_process_grouping(self):
        grouping = self.grouping_combo.currentText() if hasattr(self, 'grouping_combo') else "None"
        # In a real implementation, this would reorganize the table with group headers
        # For simplicity, just update the table
        self.update_process_table()
    
    def show_process_menu(self, pos):
        selected_items = self.process_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        pid_item = self.process_table.item(row, 1)
        if not pid_item:
            return
            
        try:
            pid = int(pid_item.text())
            if not psutil.pid_exists(pid):
                return
                
            menu = QMenu()
            
            # Add menu actions
            end_task_action = menu.addAction("End task")
            end_task_action.triggered.connect(lambda: self.end_process(pid))
            
            # Priority submenu
            priority_menu = menu.addMenu("Set priority")
            for priority_name, priority_value in PRIORITY_LEVELS.items():
                action = priority_menu.addAction(priority_name)
                action.triggered.connect(lambda checked, p=pid, v=priority_value: self.set_process_priority(p, v))
            
            menu.addSeparator()
            
            details_action = menu.addAction("Properties")
            details_action.triggered.connect(lambda: self.show_process_details(row, 0))
            
            create_dump_action = menu.addAction("Create dump file")
            create_dump_action.triggered.connect(lambda: self.create_dump_file(pid))
            
            menu.exec_(self.process_table.viewport().mapToGlobal(pos))
        except Exception as e:
            self.show_error(f"Menu creation error: {str(e)}")
    
    def end_process(self, pid):
        try:
            process = psutil.Process(pid)
            process_name = process.name()
            
            reply = QMessageBox.question(
                self, 
                "End Process", 
                f"Are you sure you want to end the process '{process_name}' (PID: {pid})?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                process.terminate()
                self.status_bar.showMessage(f"Process {process_name} (PID: {pid}) terminated.", 5000)
        except psutil.NoSuchProcess:
            self.show_error(f"Process with PID {pid} does not exist.")
        except psutil.AccessDenied:
            self.show_error(f"Access denied when trying to terminate process with PID {pid}.")
        except Exception as e:
            self.show_error(f"Error ending process: {str(e)}")
    
    def set_process_priority(self, pid, priority):
        try:
            process = psutil.Process(pid)
            process.nice(priority)
            self.status_bar.showMessage(f"Priority set for PID {pid}.", 3000)
        except psutil.NoSuchProcess:
            self.show_error(f"Process with PID {pid} does not exist.")
        except psutil.AccessDenied:
            self.show_error(f"Access denied when trying to set priority for process with PID {pid}.")
        except Exception as e:
            self.show_error(f"Error setting priority: {str(e)}")
    
    def create_dump_file(self, pid):
        try:
            # In a real implementation, this would use platform-specific methods to create a memory dump
            process = psutil.Process(pid)
            process_name = process.name()
            
            # Get the save location from user
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Dump File", 
                f"{process_name}_{pid}.dmp", 
                "Dump Files (*.dmp)"
            )
            
            if file_path:
                # This is a placeholder - real implementation would use Windows API
                with open(file_path, 'w') as f:
                    f.write(f"Memory dump for {process_name} (PID: {pid})\n")
                    f.write("This is a placeholder file. Real implementation would create an actual memory dump.\n")
                
                self.status_bar.showMessage(f"Dump file created for {process_name} (PID: {pid}).", 5000)
        except Exception as e:
            self.show_error(f"Error creating dump file: {str(e)}")
    
    def show_process_details(self, row, column):
        pid_item = self.process_table.item(row, 1)
        if not pid_item:
            return
            
        try:
            pid = int(pid_item.text())
            if pid in self.process_data:
                dialog = ProcessDetailsDialog(pid, self.process_data[pid], self)
                dialog.exec_()
        except Exception as e:
            self.show_error(f"Error showing process details: {str(e)}")
    
    def show_search_dialog(self):
        dialog = SearchDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            search_text = dialog.get_search_text()
            case_sensitive = dialog.is_case_sensitive()
            self.search_process(search_text, case_sensitive)
    
    def search_process(self, search_text, case_sensitive=False):
        if not search_text:
            return
            
        # Check if search text is a valid PID
        try:
            pid = int(search_text)
            # Search by PID
            for row in range(self.process_table.rowCount()):
                pid_item = self.process_table.item(row, 1)
                if pid_item and int(pid_item.text()) == pid:
                    self.process_table.selectRow(row)
                    return
        except ValueError:
            # Search by name
            for row in range(self.process_table.rowCount()):
                name_item = self.process_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    if case_sensitive:
                        if search_text in name:
                            self.process_table.selectRow(row)
                            return
                    else:
                        if search_text.lower() in name.lower():
                            self.process_table.selectRow(row)
                            return
        
        # If not found
        self.status_bar.showMessage(f"No process matching '{search_text}' found.", 5000)
    #endregion

    #region Performance Tab
    def create_performance_tab(self):
        widget = QWidget()
        layout = QGridLayout()
        
        # Create splitter for left navigation and right content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left navigation panel
        nav_panel = QTreeWidget()
        nav_panel.setHeaderHidden(True)
        nav_panel.setMaximumWidth(200)
        
        # Add navigation items
        cpu_item = QTreeWidgetItem(["CPU"])
        memory_item = QTreeWidgetItem(["Memory"])
        disk_item = QTreeWidgetItem(["Disk"])
        network_item = QTreeWidgetItem(["Network"])
        gpu_item = QTreeWidgetItem(["GPU"])
        
        nav_panel.addTopLevelItem(cpu_item)
        nav_panel.addTopLevelItem(memory_item)
        nav_panel.addTopLevelItem(disk_item)
        nav_panel.addTopLevelItem(network_item)
        nav_panel.addTopLevelItem(gpu_item)
        
        # Add disk drives
        for disk in psutil.disk_partitions():
            disk_item.addChild(QTreeWidgetItem([f"{disk.device} ({disk.mountpoint})"]))
        
        # Add network adapters
        if hasattr(psutil, 'net_if_stats'):
            for iface, stats in psutil.net_if_stats().items():
                network_item.addChild(QTreeWidgetItem([iface]))
        
        # Connect item selection
        nav_panel.itemClicked.connect(self.change_performance_view)
        
        # Right content area with stacked widgets
        self.perf_content = QWidget()
        self.perf_layout = QVBoxLayout(self.perf_content)
        
        # CPU Chart
        self.cpu_chart_widget = pg.PlotWidget()
        self.cpu_chart_widget.setBackground('w')
        self.cpu_chart_widget.setTitle("CPU Utilization", color='k')
        self.cpu_chart_widget.setLabel('left', 'Usage', units='%')
        self.cpu_chart_widget.setLabel('bottom', 'Time (seconds)')
        self.cpu_chart_widget.showGrid(x=True, y=True)
        self.cpu_chart_widget.setYRange(0, 100)
        self.cpu_plot = self.cpu_chart_widget.plot(self.time_data, 
                                                 list(self.chart_data['cpu']), 
                                                 pen='#1f77b4')
        
        # CPU information display
        self.cpu_info = QLabel("CPU Information")
        
        # Memory Chart
        self.memory_chart_widget = pg.PlotWidget()
        self.memory_chart_widget.setBackground('w')
        self.memory_chart_widget.setTitle("Memory Usage", color='k')
        self.memory_chart_widget.setLabel('left', 'Usage', units='%')
        self.memory_chart_widget.setLabel('bottom', 'Time (seconds)')
        self.memory_chart_widget.showGrid(x=True, y=True)
        self.memory_chart_widget.setYRange(0, 100)
        self.memory_plot = self.memory_chart_widget.plot(self.time_data, 
                                                       list(self.chart_data['memory']), 
                                                       pen='#2ca02c')
        
        # Memory information display
        self.memory_info = QLabel("Memory Information")
        
        # Initial view (CPU)
        self.current_perf_view = "CPU"
        self.perf_layout.addWidget(self.cpu_chart_widget)
        self.perf_layout.addWidget(self.cpu_info)
        
        # Add panels to splitter
        splitter.addWidget(nav_panel)
        splitter.addWidget(self.perf_content)
        splitter.setSizes([200, 800])  # Set initial sizes
        
        layout.addWidget(splitter, 0, 0)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Performance")
    
    def change_performance_view(self, item, column):
        # Clear current layout
        for i in reversed(range(self.perf_layout.count())): 
            widget = self.perf_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        view_name = item.text(0)
        self.current_perf_view = view_name
        
        if view_name == "CPU":
            self.perf_layout.addWidget(self.cpu_chart_widget)
            self.perf_layout.addWidget(self.cpu_info)
        elif view_name == "Memory":
            self.perf_layout.addWidget(self.memory_chart_widget)
            self.perf_layout.addWidget(self.memory_info)
        elif view_name == "Disk":
            # Basic disk view
            disk_widget = pg.PlotWidget()
            disk_widget.setBackground('w')
            disk_widget.setTitle("Disk Activity", color='k')
            disk_widget.setLabel('left', 'Usage', units='MB/s')
            disk_widget.setLabel('bottom', 'Time (seconds)')
            disk_widget.showGrid(x=True, y=True)
            disk_plot = disk_widget.plot(self.time_data, list(self.chart_data['disk']), pen='#9467bd')
            
            self.perf_layout.addWidget(disk_widget)
            self.perf_layout.addWidget(QLabel("Disk Information"))
        elif view_name == "Network":
            # Basic network view
            net_widget = pg.PlotWidget()
            net_widget.setBackground('w')
            net_widget.setTitle("Network Activity", color='k')
            net_widget.setLabel('left', 'Usage', units='MB/s')
            net_widget.setLabel('bottom', 'Time (seconds)')
            net_widget.showGrid(x=True, y=True)
            net_plot = net_widget.plot(self.time_data, list(self.chart_data['network']), pen='#d62728')
            
            self.perf_layout.addWidget(net_widget)
            self.perf_layout.addWidget(QLabel("Network Information"))
        elif view_name == "GPU":
            # Placeholder for GPU
            gpu_label = QLabel("GPU information not available")
            gpu_label.setAlignment(Qt.AlignCenter)
            self.perf_layout.addWidget(gpu_label)
    
    def update_performance_charts(self, perf_data):
        # Update CPU chart
        if 'cpu_percent' in perf_data:
            self.chart_data['cpu'].append(perf_data['cpu_percent'])
            self.cpu_plot.setData(self.time_data, list(self.chart_data['cpu']))
            
            # Update CPU info
            cpu_info_text = ""
            if 'cpu_count' in perf_data:
                cpu_info_text += f"Logical Processors: {perf_data['cpu_count']}\n"
            if 'cpu_freq' in perf_data and perf_data['cpu_freq']:
                cpu_info_text += f"Current Frequency: {perf_data['cpu_freq'].current:.2f} MHz\n"
                if hasattr(perf_data['cpu_freq'], 'max') and perf_data['cpu_freq'].max:
                    cpu_info_text += f"Maximum Frequency: {perf_data['cpu_freq'].max:.2f} MHz\n"
            cpu_info_text += f"Current Utilization: {perf_data['cpu_percent']:.1f}%"
            self.cpu_info.setText(cpu_info_text)
        
        # Update Memory chart
        if 'memory' in perf_data:
            memory = perf_data['memory']
            self.chart_data['memory'].append(memory['percent'])
            self.memory_plot.setData(self.time_data, list(self.chart_data['memory']))
            
            # Update Memory info
            memory_info_text = (
                f"Total: {memory['total'] / (1024**3):.2f} GB\n"
                f"Available: {memory['available'] / (1024**3):.2f} GB\n"
                f"Used: {memory['used'] / (1024**3):.2f} GB ({memory['percent']}%)\n"
                f"Free: {memory['free'] / (1024**3):.2f} GB"
            )
            self.memory_info.setText(memory_info_text)
        
        # Update Disk data
        if 'disk' in perf_data:
            disk = perf_data['disk']
            # Use total rate for chart
            total_rate = (disk['read_rate'] + disk['write_rate']) / (1024**2)  # Convert to MB/s
            self.chart_data['disk'].append(total_rate)
        
        # Update Network data
        if 'network' in perf_data:
            network = perf_data['network']
            # Use total rate for chart
            total_rate = (network['bytes_sent_rate'] + network['bytes_recv_rate']) / (1024**2)  # Convert to MB/s
            self.chart_data['network'].append(total_rate)
    #endregion

    #region Other Tabs (Stub implementations)
    def create_app_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("App history view is not fully implemented in this demo.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Name", "CPU Time", "Network", "Metered Network", "Tile Updates"
        ])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "App History")

    def create_startup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Startup programs view is not fully implemented in this demo.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Name", "Publisher", "Status", "Startup impact"
        ])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Startup")

    def create_users_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Users view is not fully implemented in this demo.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        tree = QTreeWidget()
        tree.setHeaderLabels(["User", "Status", "CPU", "Memory"])
        
        # Add current user
        try:
            import getpass
            user_item = QTreeWidgetItem([getpass.getuser(), "Active", "0%", "0%"])
            tree.addTopLevelItem(user_item)
        except:
            pass
            
        layout.addWidget(tree)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Users")

    def create_details_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # This is basically a more detailed version of the process tab
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(8)
        self.details_table.setHorizontalHeaderLabels([
            "Name", "PID", "Status", "User name", "CPU", "Memory", 
            "Description", "Command Line"
        ])
        
        header = self.details_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name column stretches
        header.setSectionResizeMode(7, QHeaderView.Stretch)  # Command line column stretches
        
        layout.addWidget(self.details_table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Details")
    
    def create_services_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Services view is not fully implemented in this demo.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Name", "Status", "PID", "Description"
        ])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Services")
    #endregion

    #region Status Bar and UI Updates
    def update_ui(self):
        # Update the process table if we're on the Processes tab
        if self.tabs.currentWidget() == self.tabs.widget(0):
            self.update_process_table()
        
        # Update the details table if we're on the Details tab
        if hasattr(self, 'details_table') and self.tabs.currentWidget() == self.tabs.widget(5):
            self.update_details_table()
        
        # Update status bar
        self.update_status_bar()
    
    def update_details_table(self):
        if not self.process_data:
            return
            
        self.details_table.setRowCount(0)
        for pid, process in self.process_data.items():
            row = self.details_table.rowCount()
            self.details_table.insertRow(row)
            
            # Prepare and set items
            self.details_table.setItem(row, 0, QTableWidgetItem(process.get('name', 'Unknown')))
            self.details_table.setItem(row, 1, QTableWidgetItem(str(pid)))
            self.details_table.setItem(row, 2, QTableWidgetItem(process.get('status', 'Unknown')))
            self.details_table.setItem(row, 3, QTableWidgetItem(process.get('username', 'N/A')))
            
            cpu_item = QTableWidgetItem(f"{process.get('cpu_percent', 0):.1f}%")
            self.details_table.setItem(row, 4, cpu_item)
            
            memory_bytes = process.get('memory_bytes', 0)
            memory_percent = process.get('memory_percent', 0)
            self.details_table.setItem(row, 5, QTableWidgetItem(
                f"{memory_percent:.1f}% ({self.format_bytes(memory_bytes)})"
            ))
            
            self.details_table.setItem(row, 6, QTableWidgetItem(""))  # Description placeholder
            self.details_table.setItem(row, 7, QTableWidgetItem(process.get('cmdline', '')))
    
    def update_status_bar(self):
        try:
            # Update process count
            self.process_count.setText(f"Processes: {len(self.process_data)}")
            
            # Get CPU and memory values from performance data
            cpu_percent = 0
            memory_percent = 0
            
            for proc in self.process_data.values():
                cpu_percent += proc.get('cpu_percent', 0)
                memory_percent = max(memory_percent, proc.get('memory_percent', 0))
            
            # Cap CPU percent at 100% per core
            cpu_count = psutil.cpu_count() or 1
            cpu_percent = min(cpu_percent, 100 * cpu_count)
            
            # Update indicators
            self.cpu_indicator.setText(f"CPU: {cpu_percent:.1f}%")
            self.memory_indicator.setText(f"Memory: {memory_percent:.1f}%")
            
            # Show general status message
            self.status_bar.showMessage("Ready")
        except Exception as e:
            self.show_error(f"Status bar update error: {str(e)}")
    #endregion

    #region Data Handling
    def update_process_data(self, data):
        self.process_data = data
    
    def update_performance_data(self, data):
        # Update charts
        self.update_performance_charts(data)
        
        # Update status bar indicators with the latest data
        if 'cpu_percent' in data:
            self.cpu_indicator.setText(f"CPU: {data['cpu_percent']:.1f}%")
        
        if 'memory' in data:
            self.memory_indicator.setText(f"Memory: {data['memory']['percent']:.1f}%")
    
    def force_refresh(self):
        # Force a full UI update
        if hasattr(self, 'process_worker'):
            self.process_worker.data_updated.emit(self.process_data)
        
        self.update_ui()
        self.status_bar.showMessage("Refreshed", 3000)
    #endregion

    #region Settings and Configuration
    def show_settings_dialog(self):
        # Simple settings dialog implementation
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout()
        
        # Update interval setting
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Update interval (seconds):"))
        interval_spin = QComboBox()
        interval_spin.addItems(["0.5", "1", "2", "3", "5"])
        interval_spin.setCurrentText("1")  # Default
        interval_layout.addWidget(interval_spin)
        layout.addLayout(interval_layout)
        
        # Always on top option
        always_on_top = QCheckBox("Always on top")
        layout.addWidget(always_on_top)
        
        # Minimize on close option
        minimize_on_close = QCheckBox("Minimize on close")
        layout.addWidget(minimize_on_close)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # If accepted, apply settings
        if dialog.exec_() == QDialog.Accepted:
            interval = float(interval_spin.currentText())
            self.refresh_timer.setInterval(interval * 1000)
            
            # Set window flags
            if always_on_top.isChecked():
                self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()  # Need to call show() after changing window flags
            
            # Save settings
            self.save_settings()
    
    def save_settings(self):
        settings = {
            'window_size': [self.width(), self.height()],
            'window_position': [self.x(), self.y()],
            'active_tab': self.tabs.currentIndex(),
            'update_interval': self.refresh_timer.interval(),
            'column_widths': [
                self.process_table.columnWidth(i) 
                for i in range(self.process_table.columnCount())
            ]
        }
        
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            self.show_error(f"Error saving settings: {str(e)}")
    
    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                
                # Apply window geometry
                if 'window_size' in settings:
                    self.resize(settings['window_size'][0], settings['window_size'][1])
                
                if 'window_position' in settings:
                    self.move(settings['window_position'][0], settings['window_position'][1])
                
                # Set active tab
                if 'active_tab' in settings:
                    self.tabs.setCurrentIndex(settings['active_tab'])
                
                # Set update interval
                if 'update_interval' in settings:
                    self.refresh_timer.setInterval(settings['update_interval'])
                
                # Restore column widths
                if 'column_widths' in settings:
                    for i, width in enumerate(settings['column_widths']):
                        if i < self.process_table.columnCount():
                            self.process_table.setColumnWidth(i, width)
        except Exception as e:
            self.show_error(f"Error loading settings: {str(e)}")
    #endregion

    #region Helper Functions
    def format_bytes(self, size):
        if size == 0:
            return "0 B"
            
        power = 2**10
        n = 0
        units = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power and n < len(units)-1:
            size /= power
            n += 1
        return f"{size:.1f} {units[n]}"
    
    def show_error(self, message):
        self.status_bar.showMessage(message, 5000)
        print(f"Error: {message}")
    #endregion

    #region Event Handlers
    def closeEvent(self, event):
        # Save settings
        self.save_settings()
        
        # Clean up resources
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        
        if hasattr(self, 'process_worker'):
            self.process_worker.stop()
        
        if hasattr(self, 'perf_worker'):
            self.perf_worker.stop()
        
        # Accept the close event
        event.accept()
    #endregion

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = SystemMonitor()
    window.show()
    sys.exit(app.exec_())
