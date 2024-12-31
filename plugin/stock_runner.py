import os
import sys
import json
import time
import traceback
import atexit
from datetime import datetime
import requests
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from windows_toasts import Toast, WindowsToaster, ToastDisplayImage

folder = os.path.expanduser("~/.stock")
configFile = f"{folder}/.stock.cfg.json"
dataFile = f"{folder}/.stock.dat.json"
dataLockFile = f"{folder}/.stock.dat.lock"
logFile = f"{folder}/.stock.log"

Config = {}
Stock_codes = ''
Rests = []
OneObserver = None
Notified = []
JsonData = None
Indices = ''
LogFileHandle = open(logFile, 'w+', encoding="utf-8")

def log(msg):
    LogFileHandle.write(f"{datetime.now().strftime('%m-%d %H:%M')}: {msg}\n")
    LogFileHandle.flush()

def global_exception_handler(exctype, value, tb):
    # import pdb; pdb.set_trace()
    error = traceback.format_exception(exctype, value, tb)
    log(error)
    if exctype != KeyboardInterrupt:
        toast(error)
    if OneObserver:
        OneObserver.stop()
        OneObserver.join()

    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

def cleanup():
    LogFileHandle.close()

atexit.register(cleanup)

def readConfig():
    global Config, Stock_codes, Rests, Indices, Notified, JsonData

    with open(configFile, "r", encoding="utf-8") as f:
        try:
            Config = json.load(f)
        except:
            traceback.print_exc(file=logFile)
            return

    if len(Config["threshold"]['indices']) != len(Config['indices']):
        log("Indices and thresholds mismatch.")
        return

    if len(Config["codes"]):
        Stock_codes = Stock_codes[:-1]

    Indices = ','.join(Config['indices'])

    Notified = []
    if JsonData:
        JsonData = {"runner_pid": JsonData["runner_pid"], 'notified': []}

    Rests = Config["rest_dates"]
    for code in Config["codes"]:
        codeInt = int(code)
        if codeInt > 600000 and codeInt < 700000:
            Stock_codes += "1." + code + ","
        else:
            Stock_codes += "0." + code + ","

    return True


def retrieveStockData():
    codes = '' if not len(Stock_codes) else ',' + Stock_codes
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={Indices}{codes}&fields=f3,f14&cb=cb"
    log(f"Retrieve stock data for: {url}")
    try:
        rsp = requests.get(
            url,
            headers={"Referer": "https://guba.eastmoney.com/"},
        )
        if rsp.status_code == 200:
            data = []
            ls = json.loads(rsp.text[3:-2])['data']['diff']
            # import pdb; pdb.set_trace()
            for item in ls:
                data.append([item['f14'].replace(' ', '')[0:2], item['f3']])
            # log(f"Stock data retrieved: {json.dumps(data)}")

            return data
        else:
            log(f"Failed to retrieve stock data, status code: {rsp.status_code}")
            return str(rsp.status_code)
    except Exception as er:
        # import pdb; pdb.set_trace()
        log(f"Failed to retrieve stock data: {er}")
        return str(er)

def checkNotify(data):
    txts = []
    up = False
    down = False
    for i, (name, value) in enumerate(data):
        if i < 3:
            threshold = Config["threshold"]['indices'][i]
        elif value > 0:
            threshold = Config["threshold"]['up']
        else:
            threshold = Config["threshold"]['down']

        if i in Notified:
            continue

        if value  > 0 and value >= threshold:
            up = True
            txts.append(f"{name}: {value}")
            Notified.append(i)
        elif value <= 0 and value <= -threshold:
            down = True
            txts.append(f"{name}: {value}")
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

class ConfigFileEventHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(patterns=[configFile])
    def on_modified(self, event):
        readConfig()

if not readConfig():
    exit(1)

if inRest():
    tsData = os.path.getmtime(dataFile)
    # if os.path.getmtime(configFile) > tsData or \
    log(datetime.fromtimestamp(tsData).date() + ' ' + datetime.now().date())
    if datetime.fromtimestamp(tsData).date() != datetime.now().date():
        with open(dataFile, 'w', encoding="utf-8") as fData, open(dataLockFile, "w", encoding="utf-8") as fLock:
            fLock.write(' ')
            fLock.flush()

            data = {"runner_pid": os.getpid(), 'prices': retrieveStockData()}
            fData.write(json.dumps(data))
            log("Data updated.")
    log("Rest day, exit.")
    sys.exit(0)

event_handler = ConfigFileEventHandler()
OneObserver = Observer()
OneObserver.schedule(event_handler, os.path.dirname(configFile), recursive=False)
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

if os.path.exists(dataLockFile): # prevent reading empty data file
    os.remove(dataLockFile)

with open(dataFile, 'w', encoding="utf-8") as fData:
    time.sleep(0.1)
    with open(dataLockFile, "w", encoding="utf-8") as fLock:
        data_modified_date = datetime.fromtimestamp(os.path.getmtime(dataFile)).date()
        if data_modified_date == datetime.now().date() and "notified" in Data:
            Notified = Data["notified"]
        JsonData = {"runner_pid": os.getpid(), 'notified': Notified}
        while True:
            data = retrieveStockData()
            if type(data) is list:
                checkNotify(data)
            JsonData['prices'] = data

            fLock.write(' ')
            fLock.flush()
            # log(f"1 lock/data: {datetime.fromtimestamp(os.path.getmtime(dataLockFile)).strftime('%M:%S')}/{datetime.fromtimestamp(os.path.getmtime(dataFile)).strftime('%M:%S')}")

            fData.seek(0)
            fData.write(json.dumps(JsonData))
            fData.truncate()
            fData.flush()
            # log(f"2 lock/data: {datetime.fromtimestamp(os.path.getmtime(dataLockFile)).strftime('%M:%S')}/{datetime.fromtimestamp(os.path.getmtime(dataFile)).strftime('%M:%S')}")

            now = datetime.now().time()
            if now >= time_start1 and now <= time_end1 \
                    or now >= time_start2 and now <= time_end2:
                time.sleep(Config['delay'])
            else:
                log("Market inactive, exit.")
                break
