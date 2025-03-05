import os
import io
import sys
import json
import time
import traceback
import atexit
from datetime import datetime
import random
import requests
from requests.exceptions import Timeout
import errno
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from windows_toasts import Toast, WindowsToaster, ToastDisplayImage

from servers import Servers, NAME_PLACEHOLDER

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

folder = os.path.expanduser("~/.stock")
configFolder = f"{folder}/cfg" # can not monitor a single file
configFileName = "stock.cfg.json"
configFile = f"{configFolder}/{configFileName}"
dataFile = f"{folder}/stock.dat.json"
dataLockFile = f"{folder}/stock.dat.lock"
runnerFile = f"{folder}/stock.runner.pid"
logFile = f"{folder}/stock.log"

LogFileHandle = open(logFile, 'a', encoding="utf-8")
Pid = os.getpid()

Cfg_reading = False
Config = {}
Rests = []
OneObserver = None
Notified = []
JsonData = None
FirstRun = True
Server = None
Names = None

def log(msg):
    LogFileHandle.write(f"{datetime.now().strftime('%m-%d %H:%M:%S')}({time.time()})[{Pid}]: {msg}\n")
    LogFileHandle.flush()

def global_exception_handler(exctype, value, tb):
    # import pdb; pdb.set_trace()
    error = traceback.format_exception(exctype, value, tb)
    if Server:
        error = f'<{Server['headers']['Referer']}>\n{error}'
    log(error)
    if exctype != KeyboardInterrupt:
        toast(error)
    if OneObserver:
        OneObserver.stop()
        OneObserver.join()

    sys.__excepthook__(exctype, value, tb)


def cleanup():
    LogFileHandle.close()
    os.remove(runnerFile)

def readConfig():
    global Cfg_reading, Config, Rests, Notified, JsonData
    Cfg_reading = True

    with open(configFile, "r", encoding="utf-8") as f:
        try:
            Config = json.load(f)
        except:
            traceback.print_exc(file=logFile)
            return

    if len(Config["threshold"]['indices']) != len(Config['indices']):
        log("Indices and thresholds mismatch.")
        return

    if len(Config['indices']):
        for server in Servers:
            server['codes'] = [server['code_converter'](i, True) for i in Config['indices']]
    else:
        log("No indices configured.")
        return

    if len(Config['codes']):
        for server in Servers:
            server['codes'] += [server['code_converter'](i) for i in Config['codes']]
            server['codes_str'] = ','.join(server['codes'])
    else:
        log("No codes configured.")

    if not len(Servers[0]['codes']):
        raise Exception("No indices and codes configured.")

    Rests = Config["rest_dates"]
    if JsonData: # Config changed on the fly
        FirstRun = True
        Names = None
        Notified.clear()

    Cfg_reading = False
    return True


def retrieveStockData(number=False):
    global FirstRun, Server
    if FirstRun:
        FirstRun = False
        Server = Servers[0] # The first one returns full data
    else:
        if number:
            servers = [item for item in Servers if item['has_price']]  # Custom condition
        else:
            servers = Servers
        Server = random.choice(servers)
    # Server = Servers[3]

    # import pdb; pdb.set_trace()
    url = Server['url_formatter'](Server['codes_str'])
    # log(f"Retrieve from: {url}")
    try:
        rsp = requests.get(
            url,
            timeout=Config['delay'],
            headers={**Server['headers'], "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
        )
        # log(rsp.text)
        if rsp.status_code != 200:
            log(f"Failed to retrieve from ({url}): {rsp.status_code}")
            return str(rsp.status_code)
    except Timeout:
        msg = f"Request to {url} timed out."
        log(msg)
        return msg
    except Exception as er:
        log(f"Failed to retrieve from {url}: {repr(er)}")
        return repr(er)

    try:
        data = Server['rsp_parser'](rsp, Server, number)
        # import pdb; pdb.set_trace()
        # log(f"Parsed: {json.dumps(data)}")
        return data
    except Exception as er:
        # import pdb; pdb.set_trace()
        log(f"Failed to parse response from {url}: {repr(er)}")
        return repr(er)

def checkNotify(data):
    txts = []
    up = False
    down = False
    for i, (name, value) in enumerate(data):
        if value is None: # ???????
            url = Server['url_formatter'](Server['codes_str'])
            error = f'{name} has no value:\n{url}\n{str(data)}'
            error = f'<{Server['headers']['Referer']}>\n{error}'
            toast(error)
            log(error)
            continue
        if i in Notified:
            continue
        if type(value) is str: # '-'
            continue

        if i < len(Config['indices']):
            threshold = Config["threshold"]['indices'][i]
        elif value > 0:
            threshold = Config["threshold"]['up']
        else:
            threshold = Config["threshold"]['down']

        if value > 0 and value >= threshold:
            up = True
            txts.append(f"{name}: {value}")
            log("Notified: " + str(Notified))
            Notified.append(i)
        elif value <= 0 and value <= -threshold:
            down = True
            txts.append(f"{name}: {value}")
            log("Notified: " + str(Notified))
            Notified.append(i)

    if len(txts):
        if up and down:
            img = 'updown'
        elif up:
            img = 'up'
        elif down:
            img = 'down'
        script_dir = os.path.dirname(os.path.abspath(__file__))
        img = os.path.join(script_dir, img + '.png')
        toast(txts, img)

def toast(txts, img = None):
    # import pdb; pdb.set_trace()
    if type(txts) is str:
        txts = (txts,)
    toaster = WindowsToaster('Stock Runner')
    newToast = Toast()
    newToast.text_fields = txts
    # newToast.scenario = ToastScenario.IncomingCall
    if img:
        newToast.AddImage(ToastDisplayImage.fromPath(img))
    toaster.show_toast(newToast)

def inRest():
    today = datetime.now()
    weekday = today.isoweekday()
    key = today.strftime("%Y-%m-%d")
    return weekday > 5 or key in Rests

def delDataLockFile():
    if os.path.exists(dataLockFile):
        try:
            os.remove(dataLockFile)
        except PermissionError as e:
            if e.errno == errno.EACCES and "used by another process" in str(e):
                log(f"Runner sync failed.\n Error: {e}")

class ConfigFileEventHandler(FileSystemEventHandler):
    def __init__(self, debounce_time=1.0):
        self.debounce_time = debounce_time
        self.last_triggered = 0

    def on_modified(self, event):
        if not event.src_path.endswith(configFileName):
            return
        current_time = time.time()
        if current_time - self.last_triggered > self.debounce_time:
            self.last_triggered = current_time
            log('cfg updated')
            readConfig()

log(f"Stock runner starting")

if not readConfig():
    exit(1)

if len(sys.argv) > 1:
    FirstRun = False
    log = print
    print(retrieveStockData(sys.argv[1] == 'price'))
    exit(0)

sys.excepthook = global_exception_handler
atexit.register(cleanup)

if inRest():
    if os.path.exists(dataFile):
        tsData = os.path.getmtime(dataFile)
    else:
        tsData = 0

    # if os.path.getmtime(configFile) > tsData or \
    # log(datetime.fromtimestamp(tsData).strftime('%m-%d') + ' ' + datetime.now().strftime('%m-%d'))
    if datetime.fromtimestamp(tsData).date() != datetime.now().date():
        delDataLockFile()
        data = {'prices': retrieveStockData()}
        with open(dataLockFile, "w", encoding="utf-8") as fLock, open(dataFile, 'w', encoding="utf-8") as fData:
            fData.write(json.dumps(data, ensure_ascii=False))
            # log("Data updated.")
    log("Rest day, exit.")
    sys.exit(0)

event_handler = ConfigFileEventHandler()
OneObserver = Observer()
OneObserver.schedule(event_handler, configFolder, recursive=False)
OneObserver.start()


time_start1 = datetime.strptime("9:15", "%H:%M").time()
time_end1 = datetime.strptime("11:30", "%H:%M").time()
time_start2 = datetime.strptime("13:00", "%H:%M").time()
time_end2 = datetime.strptime("16:00", "%H:%M").time()

Data = {}
if os.path.exists(dataFile):
    with open(dataFile, 'r', encoding="utf-8") as fData:
        dataStr = fData.read()
        if dataStr:
            Data = json.loads(dataStr)
    data_modified_date = datetime.fromtimestamp(os.path.getmtime(dataFile)).date()
else:
    data_modified_date = 0

delDataLockFile()

with open(dataFile, 'w', encoding="utf-8") as fData:
    # log(f'Data opened')
    time.sleep(1) # getftime in vim returns seconds
    with open(dataLockFile, "w", encoding="utf-8") as fLock:
        if data_modified_date == datetime.now().date() and "notified" in Data:
            Notified = Data["notified"]
        JsonData = {'notified': Notified}
        while True:
            if Cfg_reading:
                time.sleep(1)
                continue
            data = retrieveStockData()
            if type(data) is list:
                if Names is None:
                    Names = [n for (n, _) in data]
                elif data[0][0] == NAME_PLACEHOLDER:
                    for i, (name, value) in enumerate(data):
                        data[i][0] = Names[i]
                
                checkNotify(data)

            JsonData['prices'] = data

            fLock.write(' ')
            fLock.flush()
            # log(f"1 lock/data: {datetime.fromtimestamp(os.path.getmtime(dataLockFile)).strftime('%H:%M:%S')}/{datetime.fromtimestamp(os.path.getmtime(dataFile)).strftime('%H:%M:%S')}")

            fData.seek(0)
            # import pdb; pdb.set_trace()
            # text = json.dumps(JsonData)
            # log(f"Data modified: {text}")
            # fData.write(text)

            fData.write(json.dumps(JsonData, ensure_ascii=False))
            fData.truncate()
            fData.flush()
            # log(f"Data modified: {os.path.getmtime(dataFile)}")
            # log(f"2 lock/data: {datetime.fromtimestamp(os.path.getmtime(dataLockFile)).strftime('%H:%M:%S')}/{datetime.fromtimestamp(os.path.getmtime(dataFile)).strftime('%H:%M:%S')}")

            now = datetime.now().time()
            if now >= time_start1 and now <= time_end1 \
                    or now >= time_start2 and now <= time_end2:
                time.sleep(random.randint(Config['delay']-2, Config['delay']))
            else:
                log("Market inactive, exit.")
                break
