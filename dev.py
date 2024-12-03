import os
import subprocess
import sys
from pathlib import Path
import time
import signal
import platform

class DevServer:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.sass_dir = self.base_dir / 'static' / 'sass'
        self.css_dir = self.base_dir / 'static' / 'css'
        self.processes = []
        self.is_windows = platform.system() == 'Windows'
        
        # Create css directory if it doesn't exist
        self.css_dir.mkdir(exist_ok=True)
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        try:
            subprocess.run(
                ['node-sass', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=self.is_windows
            )
        except FileNotFoundError:
            print("❌ node-sass not found. Please install it using:")
            print("npm install -g node-sass")
            sys.exit(1)
    
    def compile_sass(self):
        """Initial SASS compilation"""
        print("\n📦 Compiling SASS files...")
        try:
            input_file = self.sass_dir / 'app.scss'
            output_file = self.css_dir / 'app.css'
            
            result = subprocess.run([
                'node-sass',
                str(input_file),
                str(output_file),
                '--output-style', 'expanded'
            ], shell=self.is_windows, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ SASS compilation successful")
            else:
                print(f"❌ Error compiling SASS: {result.stderr}")
                sys.exit(1)
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Error compiling SASS: {e}")
            sys.exit(1)
    
    def start_sass_watch(self):
        """Start SASS watcher"""
        print("\n👀 Starting SASS watcher...")
        sass_watcher = subprocess.Popen([
            'node-sass',
            '--watch',
            str(self.sass_dir),
            '--output', str(self.css_dir),
            '--output-style', 'expanded'
        ], shell=self.is_windows)
        self.processes.append(sass_watcher)
        print("✅ SASS watcher started")
    
    def start_livereload_server(self):
        """Start LiveReload server"""
        print("\n🔄 Starting LiveReload server...")
        livereload = subprocess.Popen([
            sys.executable,
            'manage.py',
            'livereload',
            '--settings=core.settings'
        ], shell=self.is_windows)
        self.processes.append(livereload)
        print("✅ LiveReload server started")
    
    def start_django_server(self):
        """Start Django development server"""
        print("\n🚀 Starting Django development server...")
        django_server = subprocess.Popen([
            sys.executable,
            'manage.py',
            'runserver',
            '--settings=core.settings'
        ], shell=self.is_windows)
        self.processes.append(django_server)
        print("✅ Django server started")
    
    def cleanup(self, signum, frame):
        """Clean up processes on exit"""
        print("\n\n🛑 Shutting down development server...")
        for process in self.processes:
            if self.is_windows:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)])
            else:
                process.terminate()
        
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if not self.is_windows:
                    process.kill()
        
        print("👋 Development server stopped")
        sys.exit(0)
    
    def run(self):
        """Run development environment"""
        self.check_dependencies()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        # Initial SASS compilation
        self.compile_sass()
        
        # Start all processes
        self.start_livereload_server()
        time.sleep(2)  # Give LiveReload server time to start
        self.start_sass_watch()
        self.start_django_server()
        
        print("\n🌟 Development environment is ready!")
        print("📝 SASS file: static/sass/app.scss")
        print("💻 Django server: http://127.0.0.1:8000")
        print("🔄 LiveReload enabled")
        print("\nPress Ctrl+C to stop all processes")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.cleanup(None, None)

if __name__ == '__app__':
    server = DevServer()
    server.run()