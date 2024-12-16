import subprocess
import sys

def start_celery_worker():
    try:
        subprocess.run(['celery', '-A', 'core', 'worker', '-l', 'info'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting Celery worker: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_celery_worker()
