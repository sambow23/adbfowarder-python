import subprocess
import time
import threading
from pywinusb import hid

def get_adb_devices():
    output = subprocess.check_output(['adb', 'devices', '-l']).decode('utf-8')
    lines = output.strip().split('\n')[1:]
    devices = [
        line.split()[0] for line in lines
        if line.strip() and not line.startswith('* daemon')
    ]
    return devices

def forward_ports(device):
    print(f"Forwarding ports for device {device}...")
    subprocess.run(['adb', '-s', device, 'forward', 'tcp:9943', 'tcp:9943'])
    subprocess.run(['adb', '-s', device, 'forward', 'tcp:9944', 'tcp:9944'])
    print(f"Ports forwarded for device {device}")

def restart_adb_server():
    print("Restarting ADB server...")
    subprocess.run(['adb', 'kill-server'])
    subprocess.run(['adb', 'start-server'])
    print("ADB server restarted")

def wait_for_device():
    forwarded_device = None

    while True:
        devices = get_adb_devices()

        if not forwarded_device and devices:
            forwarded_device = devices[0]
            forward_ports(forwarded_device)

        elif forwarded_device and forwarded_device not in devices:
            print(f"Device {forwarded_device} disconnected, restarting ADB server.")
            forwarded_device = None
            restart_adb_server()

        time.sleep(10)

def on_usb_device_event(event_handler):
    if event_handler.event_type == 'DeviceArrival':
        print("USB device plugged in, restarting script.")
        restart_adb_server()

def main():
    device_thread = threading.Thread(target=wait_for_device)
    device_thread.start()

    all_devices = hid.find_all_hid_devices()
    for device in all_devices:
        device.set_raw_data_handler(on_usb_device_event)

    while True:
        user_input = input("Type 'done' to close the ADB server: ").strip().lower()
        if user_input == "done":
            subprocess.run(['adb', 'kill-server'])
            print("ADB server closed.")
            break

if __name__ == "__main__":
    main()
