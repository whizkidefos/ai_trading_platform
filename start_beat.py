import subprocess
import sys

def start_celery_beat():
    try:
        subprocess.run(['celery', '-A', 'core', 'beat', '-l', 'info'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting Celery beat: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_celery_beat()
