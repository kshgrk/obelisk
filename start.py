#!/usr/bin/env python3
"""
Obelisk Development Environment Manager
A comprehensive script to start all components of the Obelisk project with unified logging.
"""

import subprocess
import sys
import signal
import time
import logging
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class Colors:
    """ANSI color codes for console output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[0;37m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

class ProcessManager:
    """Manages multiple processes with logging and monitoring"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_handlers: Dict[str, logging.Handler] = {}
        self.logs: Dict[str, List[str]] = {
            'backend': [],
            'frontend': [],
            'temporal_server': [],
            'worker': [],
            'system': []
        }
        self.running = False
        self.log_server_port = 8090
        
    def check_virtual_env(self):
        """Check if running in a virtual environment"""
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        print(f"{Colors.BLUE}🔍 Environment Check:{Colors.NC}")
        if in_venv:
            print(f"{Colors.GREEN}✅ Running in virtual environment: {sys.prefix}{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}⚠️  Not running in virtual environment{Colors.NC}")
            print(f"{Colors.YELLOW}   Current Python: {sys.executable}{Colors.NC}")
        
        return in_venv
    
    def check_and_install_temporal_cli(self):
        """Check if Temporal CLI is installed and install if needed"""
        print(f"\n{Colors.BLUE}🌊 Checking Temporal CLI...{Colors.NC}")
        
        try:
            # Check if temporal CLI is installed
            result = subprocess.run(['temporal', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"{Colors.GREEN}✅ Temporal CLI found: {version}{Colors.NC}")
                return True
        except FileNotFoundError:
            pass
        
        # Temporal CLI not found, try to install
        print(f"{Colors.YELLOW}⚠️  Temporal CLI not found{Colors.NC}")
        
        # Check if we're on macOS
        try:
            system_info = subprocess.run(['uname', '-s'], capture_output=True, text=True)
            is_mac = system_info.returncode == 0 and system_info.stdout.strip().lower() == 'darwin'
        except Exception:
            is_mac = False
        
        if is_mac:
            print(f"{Colors.BLUE}🍺 Detected macOS - attempting to install via Homebrew...{Colors.NC}")
            try:
                # Check if brew is available
                subprocess.run(['brew', '--version'], capture_output=True, check=True)
                
                print(f"{Colors.BLUE}📥 Installing Temporal CLI via Homebrew...{Colors.NC}")
                result = subprocess.run(['brew', 'install', 'temporal'], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"{Colors.GREEN}✅ Temporal CLI installed successfully via Homebrew{Colors.NC}")
                    
                    # Verify installation
                    verify_result = subprocess.run(['temporal', '--version'], capture_output=True, text=True)
                    if verify_result.returncode == 0:
                        version = verify_result.stdout.strip()
                        print(f"{Colors.GREEN}✅ Verified installation: {version}{Colors.NC}")
                        return True
                    else:
                        print(f"{Colors.RED}❌ Installation verification failed{Colors.NC}")
                        
                else:
                    print(f"{Colors.RED}❌ Homebrew installation failed:{Colors.NC}")
                    print(result.stderr)
                    
            except subprocess.CalledProcessError:
                print(f"{Colors.YELLOW}⚠️  Homebrew not available{Colors.NC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️  Homebrew installation failed: {e}{Colors.NC}")
        
        # If we get here, automatic installation failed or not on macOS
        print(f"\n{Colors.RED}❌ Temporal CLI installation required{Colors.NC}")
        print(f"{Colors.YELLOW}📖 Please install Temporal CLI manually:{Colors.NC}")
        print(f"")
        print(f"   🌐 Visit: {Colors.CYAN}https://temporal.io/setup/install-temporal-cli{Colors.NC}")
        print(f"")
        
        if is_mac:
            print(f"   🍺 For macOS (if Homebrew didn't work):")
            print(f"      brew install temporal")
            print(f"")
        
        print(f"   📦 Or download manually:")
        print(f"      • Intel Macs: Download from temporal.io")
        print(f"      • Apple Silicon: Download from temporal.io") 
        print(f"      • Linux/Windows: Download from temporal.io")
        print(f"")
        print(f"   After installation, run this script again.")
        print(f"")
        
        return False
    
    def setup_dependencies(self):
        """Install uv and sync dependencies"""
        print(f"\n{Colors.BLUE}📦 Setting up dependencies...{Colors.NC}")
        
        try:
            # Check if uv is installed
            result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ uv is already installed: {result.stdout.strip()}{Colors.NC}")
            else:
                raise subprocess.CalledProcessError(1, "uv not found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"{Colors.YELLOW}📥 Installing uv...{Colors.NC}")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv'], check=True)
            print(f"{Colors.GREEN}✅ uv installed successfully{Colors.NC}")
        
        # Sync dependencies
        print(f"{Colors.BLUE}🔄 Syncing dependencies with uv...{Colors.NC}")
        print(f"{Colors.YELLOW}ℹ️  Note: uv warnings about missing RECORD files are normal when upgrading from pip{Colors.NC}")
        
        try:
            result = subprocess.run(['uv', 'sync'], cwd=project_root, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Colors.GREEN}✅ Dependencies synced successfully{Colors.NC}")
                if result.stderr and "RECORD" in result.stderr:
                    print(f"{Colors.YELLOW}⚠️  Some pip->uv migration warnings occurred (this is normal){Colors.NC}")
            else:
                print(f"{Colors.RED}❌ uv sync failed:{Colors.NC}")
                print(result.stderr)
                print(f"{Colors.YELLOW}💡 Try recreating your virtual environment: deactivate && rm -rf .venv && python -m venv .venv && source .venv/bin/activate{Colors.NC}")
                raise subprocess.CalledProcessError(result.returncode, "uv sync")
        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}❌ Failed to sync dependencies: {e}{Colors.NC}")
            raise
    
    def create_directories(self):
        """Create necessary directories"""
        dirs = ['logs', 'pids', 'static/logs']
        for dir_name in dirs:
            (project_root / dir_name).mkdir(parents=True, exist_ok=True)
    
    def add_log_entry(self, component: str, message: str, level: str = "INFO"):
        """Add a log entry to the component's log list"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        if component in self.logs:
            self.logs[component].append(log_entry)
            # Keep only last 1000 entries per component
            if len(self.logs[component]) > 1000:
                self.logs[component] = self.logs[component][-1000:]
    
    def log_reader(self, process: subprocess.Popen, component: str):
        """Read logs from a process and store them"""
        try:
            while True:
                # Check if process is still alive
                if process.poll() is not None:
                    break

                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        line = line.strip()
                        self.add_log_entry(component, line)
                        print(f"{Colors.CYAN}[{component.upper()}]{Colors.NC} {line}")
                    else:
                        # No more output, check if process is still alive
                        if process.poll() is not None:
                            break
                        time.sleep(0.1)
                else:
                    break
        except Exception as e:
            self.add_log_entry(component, f"Log reader error: {e}", "ERROR")

        # Process has finished, log final status
        if process.poll() is not None:
            self.add_log_entry(component, f"Process finished with exit code {process.returncode}", "INFO")
    
    def check_port_availability(self, port: int, service_name: str) -> bool:
        """Check if a port is available and handle conflicts"""
        try:
            # Try to find processes using the port
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                print(f"{Colors.YELLOW}⚠️  Port {port} is already in use by {service_name}{Colors.NC}")
                print(f"{Colors.YELLOW}   Process IDs: {', '.join(pids)}{Colors.NC}")

                # Try to get more info about the processes
                try:
                    for pid in pids[:3]:  # Show details for up to 3 processes
                        ps_result = subprocess.run(
                            ['ps', '-p', pid, '-o', 'pid,comm,args'],
                            capture_output=True, text=True
                        )
                        if ps_result.returncode == 0:
                            lines = ps_result.stdout.strip().split('\n')
                            if len(lines) > 1:  # Skip header line
                                print(f"{Colors.YELLOW}   {lines[1]}{Colors.NC}")
                        else:
                            print(f"{Colors.YELLOW}   Could not get details for PID {pid}{Colors.NC}")
                except Exception as e:
                    print(f"{Colors.YELLOW}   Error getting process details: {e}{Colors.NC}")
                    self.add_log_entry('system', f"Error getting process details for port {port}: {e}", "WARNING")
                
                # Ask for confirmation to kill processes
                try:
                    response = input(f"{Colors.CYAN}❓ Kill existing processes and continue? (y/N): {Colors.NC}")
                    if response.lower() in ['y', 'yes']:
                        for pid in pids:
                            try:
                                subprocess.run(['kill', '-TERM', pid], check=True)
                                print(f"{Colors.GREEN}✅ Killed process {pid}{Colors.NC}")
                                self.add_log_entry('system', f"Killed process {pid} on port {port}")
                            except subprocess.CalledProcessError:
                                print(f"{Colors.YELLOW}⚠️  Could not kill process {pid} (may have already exited){Colors.NC}")
                        
                        # Wait a moment for processes to clean up
                        time.sleep(2)
                        
                        # Check again
                        recheck = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                        if recheck.returncode == 0 and recheck.stdout.strip():
                            print(f"{Colors.RED}❌ Port {port} still in use after killing processes{Colors.NC}")
                            return False
                        else:
                            print(f"{Colors.GREEN}✅ Port {port} is now available{Colors.NC}")
                            return True
                    else:
                        print(f"{Colors.YELLOW}👋 Skipping {service_name} startup due to port conflict{Colors.NC}")
                        return False
                        
                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}👋 Operation cancelled{Colors.NC}")
                    return False
            else:
                # Port is available
                return True
                
        except FileNotFoundError:
            # lsof not available, assume port is free
            print(f"{Colors.YELLOW}⚠️  Cannot check port availability (lsof not found){Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Error checking port {port}: {e}{Colors.NC}")
            return True
    
    def cleanup_temporal_processes(self):
        """Clean up any existing temporal processes"""
        try:
            # Find and kill any existing temporal server processes (default command)
            result = subprocess.run(['pgrep', '-f', 'temporal server start-dev'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                print(f"{Colors.YELLOW}🧹 Found existing Temporal processes: {', '.join(pids)}{Colors.NC}")
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-TERM', pid], check=True)
                        print(f"{Colors.GREEN}✅ Killed existing Temporal process {pid}{Colors.NC}")
                        self.add_log_entry('system', f"Killed existing Temporal process {pid}")
                    except subprocess.CalledProcessError:
                        print(f"{Colors.YELLOW}⚠️  Could not kill process {pid} (may have already exited){Colors.NC}")
                # Wait for processes to clean up
                time.sleep(2)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Error cleaning up Temporal processes: {e}{Colors.NC}")

    def start_temporal_server(self):
        """Start Temporal server using the system CLI"""
        print(f"\n{Colors.PURPLE}🌊 Starting Temporal Server...{Colors.NC}")

        # Clean up any existing temporal processes first
        self.cleanup_temporal_processes()

        # Check port availability first (default Temporal ports)
        if not self.check_port_availability(7233, "Temporal gRPC"):
            return False
        if not self.check_port_availability(8233, "Temporal Web UI"):
            return False
        
        # Check if Temporal server is already running and responding
        try:
            import requests
            response = requests.get("http://localhost:8233/api/v1/namespaces", timeout=2)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✅ Temporal server already running and healthy{Colors.NC}")
                self.add_log_entry('temporal_server', "Temporal server already running and healthy")
                return True
        except Exception:
            pass
        
        self.add_log_entry('temporal_server', "Starting Temporal development server")
        
        # Start Temporal server using the CLI (default ports)
        process = subprocess.Popen(
            ['temporal', 'server', 'start-dev'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root
        )
        self.processes['temporal_server'] = process
        
        # Start log reader in background
        threading.Thread(target=self.log_reader, args=(process, 'temporal_server'), daemon=True).start()
        
        # Wait for server to be ready
        print(f"{Colors.YELLOW}⏳ Waiting for Temporal server to be ready...{Colors.NC}")
        for i in range(45):  # Increased timeout for initial startup
            # Check if process is still alive
            if process.poll() is not None:
                # Process has died
                print(f"\n{Colors.RED}❌ Temporal server process died with exit code {process.returncode}{Colors.NC}")
                self.add_log_entry('temporal_server', f"Temporal server process died with exit code {process.returncode}", "ERROR")

                # Try to get the last output to understand what went wrong
                try:
                    # Read any remaining output
                    remaining_output = process.stdout.read()
                    if remaining_output:
                        print(f"{Colors.RED}Last output: {remaining_output.strip()}{Colors.NC}")
                except Exception:
                    pass

                return False

            try:
                import requests
                response = requests.get("http://localhost:8233/api/v1/namespaces", timeout=1)
                if response.status_code == 200:
                    print(f"\n{Colors.GREEN}✅ Temporal server is ready!{Colors.NC}")
                    print(f"{Colors.BLUE}📊 Web UI available at: http://localhost:8233{Colors.NC}")
                    print(f"{Colors.BLUE}🔧 gRPC endpoint: localhost:7233 (default ports){Colors.NC}")
                    self.add_log_entry('temporal_server', "Temporal server is ready and responding")
                    return True
            except Exception:
                pass

            time.sleep(1)
            if i % 5 == 0:  # Print progress every 5 seconds
                print(f" {i}s", end="", flush=True)
            else:
                print(".", end="", flush=True)

        # If we get here, the process is still alive but not responding
        print(f"\n{Colors.YELLOW}⚠️  Temporal server process is running but not responding on port 8233{Colors.NC}")
        self.add_log_entry('temporal_server', "Temporal server running but not responding - may have port conflicts", "WARNING")

        # Give one more try to check if it's actually working
        try:
            import requests
            response = requests.get("http://localhost:8233/api/v1/namespaces", timeout=5)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✅ Temporal server is now responding!{Colors.NC}")
                return True
        except Exception:
            pass

        print(f"{Colors.RED}❌ Temporal server is not responding after 45 seconds{Colors.NC}")
        return False
    
    def start_backend(self):
        """Start the FastAPI backend server"""
        print(f"\n{Colors.GREEN}🚀 Starting Backend Server...{Colors.NC}")
        
        # Check port availability first
        if not self.check_port_availability(8001, "Backend API"):
            return False
        
        self.add_log_entry('backend', "Starting FastAPI backend server")
        process = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root
        )
        self.processes['backend'] = process
        
        # Start log reader in background
        threading.Thread(target=self.log_reader, args=(process, 'backend'), daemon=True).start()
        
        # Wait for backend to be ready
        print(f"{Colors.YELLOW}⏳ Waiting for backend to be ready...{Colors.NC}")
        for i in range(20):
            try:
                import requests
                response = requests.get("http://localhost:8001/health", timeout=1)
                if response.status_code == 200:
                    print(f"{Colors.GREEN}✅ Backend server is ready!{Colors.NC}")
                    self.add_log_entry('backend', "Backend server is ready and responding")
                    return True
            except Exception:
                pass
            time.sleep(1)
            print(".", end="", flush=True)
        
        print(f"\n{Colors.YELLOW}⚠️  Backend server may still be starting...{Colors.NC}")
        return True
    
    def start_worker(self):
        """Start the Temporal worker"""
        print(f"\n{Colors.BLUE}👷 Starting Temporal Worker...{Colors.NC}")
        
        worker_path = project_root / "src" / "temporal" / "workers" / "simple_chat_worker.py"
        self.add_log_entry('worker', "Starting Temporal chat worker")
        process = subprocess.Popen(
            [sys.executable, str(worker_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root
        )
        self.processes['worker'] = process
        
        # Start log reader in background
        threading.Thread(target=self.log_reader, args=(process, 'worker'), daemon=True).start()
        
        print(f"{Colors.GREEN}✅ Temporal worker started{Colors.NC}")
        self.add_log_entry('worker', "Temporal worker started successfully")
        return True
    
    def start_frontend(self):
        """Start the frontend server"""
        print(f"\n{Colors.CYAN}🎨 Starting Frontend Server...{Colors.NC}")
        
        # Check port availability first
        if not self.check_port_availability(3000, "Frontend"):
            return False
        
        frontend_path = project_root / "frontend" / "app.py"
        self.add_log_entry('frontend', "Starting frontend server")
        process = subprocess.Popen(
            [sys.executable, str(frontend_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=project_root / "frontend"
        )
        self.processes['frontend'] = process
        
        # Start log reader in background
        threading.Thread(target=self.log_reader, args=(process, 'frontend'), daemon=True).start()
        
        # Wait for frontend to be ready
        print(f"{Colors.YELLOW}⏳ Waiting for frontend to be ready...{Colors.NC}")
        for i in range(20):
            try:
                import requests
                response = requests.get("http://localhost:3000/health", timeout=1)
                if response.status_code == 200:
                    print(f"{Colors.GREEN}✅ Frontend server is ready!{Colors.NC}")
                    self.add_log_entry('frontend', "Frontend server is ready and responding")
                    return True
            except Exception:
                pass
            time.sleep(1)
            print(".", end="", flush=True)
        
        print(f"\n{Colors.YELLOW}⚠️  Frontend server may still be starting...{Colors.NC}")
        return True
    
    def create_log_server_html(self):
        """Create the HTML file for the log server"""
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Obelisk - Development Logs</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background: #1a1a1a;
            color: #ffffff;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .header h1 {
            margin: 0;
            color: white;
            font-size: 1.5rem;
        }
        
        .header .status {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .tab-container {
            display: flex;
            background: #2d2d2d;
            border-bottom: 1px solid #444;
        }
        
        .tab {
            flex: 1;
            padding: 0.75rem 1rem;
            background: #3d3d3d;
            border: none;
            color: #ccc;
            cursor: pointer;
            transition: all 0.3s ease;
            border-right: 1px solid #444;
        }
        
        .tab:last-child {
            border-right: none;
        }
        
        .tab:hover {
            background: #4d4d4d;
            color: #fff;
        }
        
        .tab.active {
            background: #667eea;
            color: white;
        }
        
        .log-container {
            height: calc(100vh - 140px);
            overflow-y: auto;
            padding: 1rem;
            background: #1a1a1a;
        }
        
        .log-entry {
            margin-bottom: 0.25rem;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-size: 0.85rem;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-word;
        }
        
        .log-entry.INFO { color: #e6e6e6; }
        .log-entry.ERROR { 
            color: #ff6b6b; 
            background: rgba(255, 107, 107, 0.1);
        }
        .log-entry.WARNING { 
            color: #ffd93d; 
            background: rgba(255, 217, 61, 0.1);
        }
        .log-entry.DEBUG { 
            color: #74c0fc; 
            background: rgba(116, 192, 252, 0.05);
        }
        
        .controls {
            position: fixed;
            bottom: 1rem;
            right: 1rem;
            display: flex;
            gap: 0.5rem;
        }
        
        .btn {
            padding: 0.5rem 1rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: background 0.3s ease;
        }
        
        .btn:hover {
            background: #5a6fd8;
        }
        
        .btn.danger {
            background: #ff6b6b;
        }
        
        .btn.danger:hover {
            background: #ff5252;
        }
        
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        
        .status-indicator.online { background: #4ecdc4; }
        .status-indicator.offline { background: #ff6b6b; }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #5a6fd8;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Obelisk Development Environment</h1>
        <div class="status">
            <span class="status-indicator online"></span>
            All services monitoring
        </div>
    </div>
    
    <div class="tab-container">
        <button class="tab active" onclick="switchTab('backend')">
            📡 Backend
        </button>
        <button class="tab" onclick="switchTab('frontend')">
            🎨 Frontend
        </button>
        <button class="tab" onclick="switchTab('temporal_server')">
            🌊 Temporal Server
        </button>
        <button class="tab" onclick="switchTab('worker')">
            👷 Worker
        </button>
        <button class="tab" onclick="switchTab('system')">
            ⚙️ System
        </button>
    </div>
    
    <div class="log-container" id="log-container">
        <!-- Logs will be populated here -->
    </div>
    
    <div class="controls">
        <button class="btn" onclick="clearLogs()">🗑️ Clear</button>
        <button class="btn" onclick="downloadLogs()">💾 Download</button>
        <button class="btn danger" onclick="stopServices()">🛑 Stop All</button>
    </div>
    
    <script>
        let currentTab = 'backend';
        let autoScroll = true;
        
        function switchTab(tab) {
            currentTab = tab;
            
            // Update tab appearance
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            // Load logs for this tab
            loadLogs();
        }
        
        function loadLogs() {
            fetch(`/api/logs/${currentTab}`)
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('log-container');
                    container.innerHTML = '';
                    
                    data.logs.forEach(log => {
                        const entry = document.createElement('div');
                        entry.className = 'log-entry INFO';
                        entry.textContent = log;
                        container.appendChild(entry);
                    });
                    
                    if (autoScroll) {
                        container.scrollTop = container.scrollHeight;
                    }
                })
                .catch(error => {
                    console.error('Error loading logs:', error);
                });
        }
        
        function clearLogs() {
            fetch(`/api/logs/${currentTab}/clear`, { method: 'POST' })
                .then(() => loadLogs());
        }
        
        function downloadLogs() {
            fetch(`/api/logs/${currentTab}`)
                .then(response => response.json())
                .then(data => {
                    const content = data.logs.join('\\n');
                    const blob = new Blob([content], { type: 'text/plain' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `obelisk-${currentTab}-logs.txt`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                });
        }
        
        function stopServices() {
            if (confirm('Are you sure you want to stop all services?')) {
                fetch('/api/stop', { method: 'POST' })
                    .then(() => {
                        alert('Services are being stopped...');
                    });
            }
        }
        
        // Auto-refresh logs every 2 seconds
        setInterval(loadLogs, 2000);
        
        // Initial load
        loadLogs();
    </script>
</body>
</html>'''
        
        log_html_path = project_root / "static" / "logs" / "index.html"
        log_html_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_html_path, 'w') as f:
            f.write(html_content)
        
        return log_html_path
    
    def start_log_server(self):
        """Start the log monitoring web server"""
        print(f"\n{Colors.PURPLE}📊 Starting Log Server...{Colors.NC}")
        
        # Check port availability first
        if not self.check_port_availability(self.log_server_port, "Log Server"):
            return False
        
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        import uvicorn
        
        app = FastAPI(title="Obelisk Log Server")
        
        # Create the HTML file
        html_path = self.create_log_server_html()
        
        @app.get("/", response_class=HTMLResponse)
        async def get_logs_page():
            with open(html_path, 'r') as f:
                return f.read()
        
        @app.get("/api/logs/{component}")
        async def get_component_logs(component: str):
            if component in self.logs:
                return {"logs": self.logs[component]}
            return {"logs": []}
        
        @app.post("/api/logs/{component}/clear")
        async def clear_component_logs(component: str):
            if component in self.logs:
                self.logs[component].clear()
                self.add_log_entry('system', f"Cleared logs for {component}")
            return {"status": "cleared"}
        
        @app.post("/api/stop")
        async def stop_all_services():
            self.add_log_entry('system', "Received stop request from log server")
            # Signal to stop in a separate thread to avoid blocking the response
            threading.Thread(target=self.stop_all, daemon=True).start()
            return {"status": "stopping"}
        
        # Start server in a separate thread
        def run_server():
            uvicorn.run(app, host="0.0.0.0", port=self.log_server_port, log_level="warning")
        
        log_server_thread = threading.Thread(target=run_server, daemon=True)
        log_server_thread.start()
        
        self.add_log_entry('system', f"Log server started on http://localhost:{self.log_server_port}")
        print(f"{Colors.GREEN}✅ Log server started on http://localhost:{self.log_server_port}{Colors.NC}")
        
        return True
    
    def open_browser_tabs(self):
        """Open browser tabs for all services"""
        print(f"\n{Colors.CYAN}🌐 Opening browser tabs...{Colors.NC}")
        
        urls = [
            f"http://localhost:{self.log_server_port}",  # Log server (main tab)
            "http://localhost:3000",  # Frontend
            "http://localhost:8001/docs",  # Backend API docs
            "http://localhost:8233",  # Temporal Web UI
        ]
        
        for url in urls:
            try:
                webbrowser.open(url)
                self.add_log_entry('system', f"Opened browser tab: {url}")
            except Exception as e:
                self.add_log_entry('system', f"Failed to open {url}: {e}", "ERROR")
        
        print(f"{Colors.GREEN}✅ Browser tabs opened{Colors.NC}")
    
    def start_all(self):
        """Start all services in the correct order"""
        self.running = True
        
        print(f"{Colors.BOLD}{Colors.BLUE}")
        print("🚀" * 20)
        print("🚀  OBELISK DEVELOPMENT ENVIRONMENT  🚀")
        print("🚀" * 20)
        print(Colors.NC)
        
        self.add_log_entry('system', "Starting Obelisk development environment")
        
        # Check virtual environment
        in_venv = self.check_virtual_env()
        
        # Check Temporal CLI installation
        if not self.check_and_install_temporal_cli():
            print(f"\n{Colors.RED}🛑 Cannot proceed without Temporal CLI{Colors.NC}")
            self.add_log_entry('system', "Temporal CLI not available - stopping startup", "ERROR")
            return False
        
        # Setup dependencies
        if in_venv:
            self.setup_dependencies()
        else:
            print(f"{Colors.YELLOW}⚠️  Skipping dependency setup (not in virtual environment){Colors.NC}")
            self.add_log_entry('system', "Skipped dependency setup - not in virtual environment", "WARNING")
        
        # Create directories
        self.create_directories()
        
        # Start services in order
        services = [
            ("Temporal Server", self.start_temporal_server),
            ("Backend", self.start_backend),
            ("Worker", self.start_worker),
            ("Frontend", self.start_frontend),
            ("Log Server", self.start_log_server),
        ]
        
        failed_services = []
        for service_name, start_func in services:
            try:
                success = start_func()
                if not success:
                    print(f"{Colors.RED}❌ Failed to start {service_name} (likely due to port conflict){Colors.NC}")
                    self.add_log_entry('system', f"Failed to start {service_name} - port conflict", "ERROR")
                    failed_services.append(service_name)
                    continue  # Continue with other services instead of stopping
                time.sleep(2)  # Brief pause between services
            except Exception as e:
                print(f"{Colors.RED}❌ Error starting {service_name}: {e}{Colors.NC}")
                self.add_log_entry('system', f"Error starting {service_name}: {e}", "ERROR")
                failed_services.append(service_name)
                continue  # Continue with other services
        
        # Check if any critical services failed
        if failed_services:
            print(f"\n{Colors.YELLOW}⚠️  Some services failed to start: {', '.join(failed_services)}{Colors.NC}")
            self.add_log_entry('system', f"Some services failed: {', '.join(failed_services)}", "WARNING")
            
            # If all services failed, return False
            if len(failed_services) == len(services):
                print(f"{Colors.RED}❌ All services failed to start{Colors.NC}")
                return False
            
            print(f"{Colors.BLUE}ℹ️  Continuing with available services...{Colors.NC}")
        else:
            self.add_log_entry('system', "All services started successfully!")
        
        # Open browser tabs
        time.sleep(3)  # Give services time to fully start
        self.open_browser_tabs()
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}")
        print("🎉" * 20)
        print("🎉  ALL SERVICES STARTED SUCCESSFULLY!  🎉")
        print("🎉" * 20)
        print(Colors.NC)
        
        print(f"\n{Colors.CYAN}📊 Service URLs:{Colors.NC}")
        print(f"  • Log Monitor:    http://localhost:{self.log_server_port}")
        print(f"  • Frontend:       http://localhost:3000")
        print(f"  • Backend API:    http://localhost:8001/docs")
        print(f"  • Temporal UI:    http://localhost:8233 (default ports)")
        
        print(f"\n{Colors.YELLOW}💡 Tips:{Colors.NC}")
        print("  • Use the Log Monitor to watch all services")
        print("  • Press Ctrl+C to stop all services gracefully")
        print("  • Check individual log files in ./logs/ directory")
        
        return True
    
    def stop_all(self):
        """Stop all services gracefully"""
        print(f"\n{Colors.YELLOW}🛑 Stopping all services...{Colors.NC}")
        self.add_log_entry('system', "Stopping all services")
        
        # Stop processes in reverse order
        for name, process in reversed(list(self.processes.items())):
            try:
                print(f"  Stopping {name}...")
                self.add_log_entry('system', f"Stopping {name}")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f"  ✅ {name} stopped gracefully")
                    self.add_log_entry('system', f"{name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    print(f"  🔪 Force killing {name}...")
                    self.add_log_entry('system', f"Force killing {name}", "WARNING")
                    process.kill()
                    process.wait()
                    print(f"  ✅ {name} force stopped")
                    
            except Exception as e:
                print(f"  ❌ Error stopping {name}: {e}")
                self.add_log_entry('system', f"Error stopping {name}: {e}", "ERROR")
        
        # Stop any remaining temporal processes
        try:
            subprocess.run(['pkill', '-f', 'temporal server start-dev'], check=False)
            print(f"  ✅ Temporal server processes stopped")
            self.add_log_entry('system', "Temporal server processes stopped")
        except Exception as e:
            print(f"  ⚠️  Error stopping temporal processes: {e}")
            self.add_log_entry('system', f"Error stopping temporal processes: {e}", "WARNING")
        
        self.running = False
        print(f"{Colors.GREEN}✅ All services stopped{Colors.NC}")
        self.add_log_entry('system', "All services stopped successfully")

    def cleanup_all_services(self):
        """Clean up all running services with user confirmation"""
        print(f"{Colors.BLUE}🔍 Scanning for running services...{Colors.NC}")

        # Check for temporal processes (default command)
        try:
            result = subprocess.run(['pgrep', '-f', 'temporal server start-dev'], capture_output=True, text=True)
            temporal_pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except Exception:
            temporal_pids = []

        # Check for backend processes
        try:
            result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
            backend_pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except Exception:
            backend_pids = []

        # Check for worker processes
        try:
            result = subprocess.run(['pgrep', '-f', 'simple_chat_worker.py'], capture_output=True, text=True)
            worker_pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except Exception:
            worker_pids = []

        # Check for frontend processes
        try:
            result = subprocess.run(['pgrep', '-f', 'frontend/app.py'], capture_output=True, text=True)
            frontend_pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except Exception:
            frontend_pids = []

        services_found = []
        if temporal_pids: services_found.append(f"Temporal Server ({len(temporal_pids)} processes)")
        if backend_pids: services_found.append(f"Backend ({len(backend_pids)} processes)")
        if worker_pids: services_found.append(f"Worker ({len(worker_pids)} processes)")
        if frontend_pids: services_found.append(f"Frontend ({len(frontend_pids)} processes)")

        if not services_found:
            print(f"{Colors.GREEN}✅ No running services found{Colors.NC}")
            return

        print(f"{Colors.YELLOW}📋 Found running services:{Colors.NC}")
        for service in services_found:
            print(f"   • {service}")

        try:
            response = input(f"\n{Colors.CYAN}❓ Stop these services? (y/N): {Colors.NC}")
            if response.lower() in ['y', 'yes']:
                # Stop each service type
                all_pids = temporal_pids + backend_pids + worker_pids + frontend_pids
                for pid in all_pids:
                    if pid.strip():
                        try:
                            subprocess.run(['kill', '-TERM', pid.strip()], check=True)
                            print(f"{Colors.GREEN}✅ Stopped process {pid.strip()}{Colors.NC}")
                        except subprocess.CalledProcessError:
                            print(f"{Colors.YELLOW}⚠️  Could not stop process {pid.strip()}{Colors.NC}")

                print(f"{Colors.GREEN}✅ All services stopped{Colors.NC}")
            else:
                print(f"{Colors.YELLOW}👋 Cleanup cancelled{Colors.NC}")
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 Cleanup cancelled{Colors.NC}")

    def force_cleanup_all_services(self):
        """Force kill all running services without confirmation"""
        print(f"{Colors.BLUE}💥 Force killing all services...{Colors.NC}")

        # Kill all related processes
        processes_to_kill = [
            'temporal server start-dev',  # Default Temporal command
            'main.py',
            'simple_chat_worker.py',
            'frontend/app.py'
        ]

        killed_count = 0
        for process_pattern in processes_to_kill:
            try:
                result = subprocess.run(['pkill', '-f', process_pattern], capture_output=True, text=True)
                if result.returncode == 0:
                    killed_count += 1
                    print(f"{Colors.GREEN}✅ Killed processes matching: {process_pattern}{Colors.NC}")
                else:
                    print(f"{Colors.YELLOW}⚠️  No processes found for: {process_pattern}{Colors.NC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️  Error killing {process_pattern}: {e}{Colors.NC}")

        if killed_count > 0:
            print(f"{Colors.GREEN}✅ Force cleanup completed{Colors.NC}")
        else:
            print(f"{Colors.GREEN}✅ No processes were running{Colors.NC}")
    
    def run(self):
        """Main run method with signal handling"""
        def signal_handler(sig, frame):
            print(f"\n{Colors.YELLOW}📡 Received shutdown signal...{Colors.NC}")
            self.stop_all()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            if self.start_all():
                print(f"\n{Colors.BLUE}🔄 Services running... Press Ctrl+C to stop{Colors.NC}")
                # Keep the main thread alive
                while self.running:
                    time.sleep(1)
            else:
                print(f"{Colors.RED}❌ Failed to start all services{Colors.NC}")
                self.stop_all()
                sys.exit(1)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 Shutting down gracefully...{Colors.NC}")
            self.stop_all()
        except Exception as e:
            print(f"{Colors.RED}❌ Unexpected error: {e}{Colors.NC}")
            self.stop_all()
            sys.exit(1)

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("""
🚀 Obelisk Development Environment Manager

Usage: python start.py [options]

Options:
  --help, -h          Show this help message
  --cleanup           Clean up all running services and processes
  --force-cleanup     Force kill all services without confirmation

This script will:
1. Check if running in a virtual environment
2. Install uv and sync dependencies (if in venv)
3. Start Temporal server
4. Start backend server (main.py)
5. Start Temporal worker (simple_chat_worker.py)
6. Start frontend server (app.py)
7. Start log monitoring web server
8. Open browser tabs for all services

Services will be available at:
• Log Monitor:    http://localhost:8090
• Frontend:       http://localhost:3000
• Backend API:    http://localhost:8001
• Temporal UI:    http://localhost:8233 (default ports)

Press Ctrl+C to stop all services gracefully.
        """)
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == '--cleanup':
        manager = ProcessManager()
        print(f"{Colors.BLUE}🧹 Cleaning up all services...{Colors.NC}")
        manager.cleanup_all_services()
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--force-cleanup':
        manager = ProcessManager()
        print(f"{Colors.BLUE}💥 Force cleaning up all services...{Colors.NC}")
        manager.force_cleanup_all_services()
        return

    manager = ProcessManager()
    manager.run()

if __name__ == "__main__":
    main()
