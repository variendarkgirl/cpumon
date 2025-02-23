# windows_task_manager.py
import sys
import psutil
import wmi
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QIcon, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QLabel,
    QTreeWidget, QTreeWidgetItem, QSplitter, QStyleFactory, 
    QGridLayout, QProgressBar
)
import pyqtgraph as pg

class SystemMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windows Task Manager")
        self.setWindowIcon(QIcon("taskmgr.ico"))
        self.resize(1200, 800)
        self.process_data = {}
        self.init_ui()
        self.init_data()

    def init_ui(self):
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
        """)
        
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Initialize all tabs
        self.create_processes_tab()
        self.create_performance_tab()
        self.create_app_history_tab()
        self.create_startup_tab()
        self.create_users_tab()
        self.create_details_tab()
        
        self.status_bar = self.statusBar()
        self.update_status_bar()

    #region Processes Tab
    def create_processes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(10)
        self.process_table.setHorizontalHeaderLabels([
            "Name", "PID", "Status", "User name", "CPU", "Memory", 
            "Disk", "Network", "GPU", "Description"
        ])
        self.process_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.process_table.setSortingEnabled(True)
        self.process_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self.show_process_menu)
        
        layout.addWidget(self.process_table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Processes")

    def update_process_table(self):
        try:
            current_pids = {proc.pid for proc in psutil.process_iter()}
            existing_pids = set(self.process_data.keys())
            
            # Remove dead processes
            for pid in existing_pids - current_pids:
                del self.process_data[pid]
            
            # Update process data
            for proc in psutil.process_iter(['pid', 'name', 'status', 'username', 
                                           'cpu_percent', 'memory_percent', 
                                           'io_counters', 'connections']):
                pid = proc.info['pid']
                if pid not in self.process_data:
                    self.process_data[pid] = {
                        'disk_usage': 0,
                        'network_usage': 0
                    }
                else:
                    # Calculate disk and network usage
                    io = proc.info['io_counters']
                    if io:
                        self.process_data[pid]['disk_usage'] = io.read_bytes + io.write_bytes
                    
                    conns = proc.info['connections']
                    if conns:
                        self.process_data[pid]['network_usage'] = sum(
                            conn.bytes_sent + conn.bytes_recv for conn in conns
                        )
            
            # Update table
            self.process_table.setRowCount(0)
            for proc in psutil.process_iter(['pid', 'name', 'status', 'username',
                                           'cpu_percent', 'memory_percent']):
                pid = proc.info['pid']
                data = self.process_data.get(pid, {})
                
                row = self.process_table.rowCount()
                self.process_table.insertRow(row)
                
                items = [
                    QTableWidgetItem(proc.info['name']),
                    QTableWidgetItem(str(pid)),
                    QTableWidgetItem(proc.info['status']),
                    QTableWidgetItem(proc.info['username'] or 'N/A'),
                    QTableWidgetItem(f"{proc.info['cpu_percent']:.1f}%"),
                    QTableWidgetItem(f"{proc.info['memory_percent']:.1f}%"),
                    QTableWidgetItem(self.format_bytes(data.get('disk_usage', 0))),
                    QTableWidgetItem(self.format_bytes(data.get('network_usage', 0))),
                    QTableWidgetItem("N/A"),  # Placeholder for GPU
                    QTableWidgetItem("")  # Placeholder for Description
                ]
                
                for col, item in enumerate(items):
                    self.process_table.setItem(row, col, item)
        except Exception as e:
            self.status_bar.showMessage(f"Process update error: {str(e)}", 5000)
    #endregion

    #region Performance Tab
    def create_performance_tab(self):
        widget = QWidget()
        layout = QGridLayout()
        
        # CPU Section
        self.cpu_chart = self.create_chart_widget("CPU Utilization (%)", '#1f77b4')
        self.cpu_info = QLabel("Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz")
        
        # Memory Section
        self.memory_chart = self.create_chart_widget("Memory Usage (%)", '#2ca02c')
        self.memory_info = QLabel("16.0 GB DDR4")
        
        # Disk Section
        self.disk_chart = self.create_chart_widget("Disk Activity (MB/s)", '#9467bd')
        
        # Network Section
        self.network_chart = self.create_chart_widget("Network Usage (Mbps)", '#d62728')
        
        layout.addWidget(self.cpu_chart, 0, 0)
        layout.addWidget(self.memory_chart, 0, 1)
        layout.addWidget(self.disk_chart, 1, 0)
        layout.addWidget(self.network_chart, 1, 1)
        layout.addWidget(self.cpu_info, 2, 0)
        layout.addWidget(self.memory_info, 2, 1)
        
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Performance")

    def create_chart_widget(self, title, color):
        widget = pg.PlotWidget()
        widget.setBackground('w')
        widget.setTitle(title, color='k')
        widget.setLabel('left', 'Usage', units='%')
        widget.setLabel('bottom', 'Time (seconds)')
        widget.addLegend()
        widget.showGrid(x=True, y=True)
        widget.setYRange(0, 100)
        return widget
    #endregion

    #region Other Tabs
    def create_app_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Name", "CPU Time", "Network", "Metered Network", "Tile Updates"
        ])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "App history")

    def create_startup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Name", "Publisher", "Startup impact"])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Startup")

    def create_users_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        tree = QTreeWidget()
        tree.setHeaderLabels(["User", "Status", "CPU", "Memory"])
        layout.addWidget(tree)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Users")

    def create_details_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Name", "PID", "Status", "User name", "CPU", "Memory", 
            "Description", "Process"
        ])
        layout.addWidget(table)
        widget.setLayout(layout)
        self.tabs.addTab(widget, "Details")
    #endregion

    def init_data(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_data)
        self.timer.start(1000)
        self.update_all_data()

    def update_all_data(self):
        self.update_process_table()
        self.update_performance_data()
        self.update_status_bar()

    def update_performance_data(self):
        try:
            # CPU
            cpu_percent = psutil.cpu_percent()
            self.cpu_chart.plot([cpu_percent], clear=True, pen='#1f77b4')
            
            # Memory
            mem = psutil.virtual_memory()
            self.memory_chart.plot([mem.percent], clear=True, pen='#2ca02c')
            self.memory_info.setText(
                f"{mem.used/1024**3:.1f} GB / {mem.total/1024**3:.1f} GB " 
                f"({mem.percent}%)"
            )
            
            # Disk
            disk_io = psutil.disk_io_counters()
            disk_usage = (disk_io.read_bytes + disk_io.write_bytes) / 1024**2
            self.disk_chart.plot([disk_usage], clear=True, pen='#9467bd')
            
            # Network
            net_io = psutil.net_io_counters()
            network_usage = (net_io.bytes_sent + net_io.bytes_recv) / 1024**2
            self.network_chart.plot([network_usage], clear=True, pen='#d62728')
            
        except Exception as e:
            self.status_bar.showMessage(f"Performance update error: {str(e)}", 5000)

    def format_bytes(self, size):
        power = 2**10
        n = 0
        units = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
        while size > power and n < len(units)-1:
            size /= power
            n += 1
        return f"{size:.1f} {units[n]}"

    def show_process_menu(self, pos):
        menu = QMenu()
        actions = {
            "End task": self.end_process,
            "Resource values": self.show_resource_values,
            "Create dump file": self.create_dump_file
        }
        
        for text, callback in actions.items():
            action = menu.addAction(text)
            action.triggered.connect(callback)
        
        menu.exec_(self.process_table.viewport().mapToGlobal(pos))

    def end_process(self):
        # Implementation remains same as previous version
        pass

    def update_status_bar(self):
        try:
            status = (
                f"Processes: {len(psutil.pids())} | "
                f"CPU Usage: {psutil.cpu_percent()}% | "
                f"Memory Usage: {psutil.virtual_memory().percent}% | "
                f"Disk Usage: {psutil.disk_usage('/').percent}% | "
                f"Network: {psutil.net_io_counters().bytes_sent/1024**2:.1f}MB sent"
            )
            self.status_bar.showMessage(status)
        except Exception as e:
            self.status_bar.showMessage(f"Status error: {str(e)}", 5000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = SystemMonitor()
    window.show()
    sys.exit(app.exec_())
