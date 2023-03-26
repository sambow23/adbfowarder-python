import os
import sys
import time
import threading
import servicemanager
import win32serviceutil
import win32service
import win32event
import subprocess
from pywinusb import hid

class AdbForwardingService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'AdbForwardingService'
    _svc_display_name_ = 'ADB Forwarding Service'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_alive = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_display_name_, ''))
        self.main()

    def get_adb_devices(self):
        output = subprocess.check_output(['adb', 'devices', '-l']).decode('utf-8')
        lines = output.strip().split('\n')[1:]
        devices = [
            line.split()[0] for line in lines
            if line.strip() and not line.startswith('* daemon')
        ]
        return devices

    def forward_ports(self, device):
        servicemanager.LogInfoMsg(f"Forwarding ports for device {device}...")
        subprocess.run(['adb', '-s', device, 'forward', 'tcp:9943', 'tcp:9943'])
        subprocess.run(['adb', '-s', device, 'forward', 'tcp:9944', 'tcp:9944'])
        servicemanager.LogInfoMsg(f"Ports forwarded for device {device}")

    def restart_adb_server(self):
        servicemanager.LogInfoMsg("Restarting ADB server...")
        subprocess.run(['adb', 'kill-server'])
        subprocess.run(['adb', 'start-server'])
        servicemanager.LogInfoMsg("ADB server restarted")

    def wait_for_device(self):
        forwarded_device = None

        while self.is_alive:
            devices = self.get_adb_devices()

            if not forwarded_device and devices:
                forwarded_device = devices[0]
                self.forward_ports(forwarded_device)

            elif forwarded_device and forwarded_device not in devices:
                servicemanager.LogInfoMsg(f"Device {forwarded_device} disconnected, restarting ADB server.")
                forwarded_device = None
                self.restart_adb_server()

            time.sleep(10)

    def on_usb_device_event(self, event_handler):
        if event_handler.event_type == 'DeviceArrival':
            servicemanager.LogInfoMsg("USB device plugged in, restarting script.")
            self.restart_adb_server()

    def main(self):
        device_thread = threading.Thread(target=self.wait_for_device)
        device_thread.start()

        all_devices = hid.find_all_hid_devices()
        for device in all_devices:
            device.set_raw_data_handler(self.on_usb_device_event)

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AdbForwardingService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AdbForwardingService)

