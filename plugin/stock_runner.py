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

configFile = os.path.expanduser("~/.stock.cfg.json")
dataFile = os.path.expanduser("~/.stock.dat.json")
dataLockFile = os.path.expanduser("~/.stock.dat.lock")
logFile = os.path.expanduser("~/.stock.log")

Config = {}
Stock_codes = ''
Rests = []
OneObserver = None
Notified = []
LogFileHandle = open(logFile, 'w+', encoding="utf-8")

def log(msg):
    LogFileHandle.write(f"{datetime.now().strftime('%m-%d %H:%M')}: {msg}\n")
    LogFileHandle.flush()

def global_exception_handler(exctype, value, tb):
    # import pdb; pdb.set_trace()
    log(f"Exception: {exctype}, {value}")
    if exctype != KeyboardInterrupt:
        toast(traceback.format_exception(exctype, value, tb))
    if OneObserver:
        OneObserver.stop()
        OneObserver.join()

    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

def cleanup():
    LogFileHandle.close()

atexit.register(cleanup)

def readConfig():
    global Config
    global Stock_codes
    global Rests
    with open(configFile, "r", encoding="utf-8") as f:
        try:
            Config = json.load(f)
        except:
            errFile = os.path.expanduser("~/.stock.error")
            with open(errFile, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
                return
    Rests = Config["rest_dates"]
    for code in Config["codes"]:
        codeInt = int(code)
        if codeInt < 600000:
            Stock_codes += "s_sz" + code + ","
        elif codeInt < 800000:
            Stock_codes += "s_sh" + code + ","
        else:
            Stock_codes += "s_bj" + code + ","

    if len(Config["codes"]):
        Stock_codes = Stock_codes[:-1]


def retrieveStockData():
    codes = '' if not len(Stock_codes) else ',' + Stock_codes
    url = f"https://hq.sinajs.cn/rn={round(datetime.now().timestamp()*1000)}&list=s_sh000001,s_sz399001,s_sz399006{codes}"
    # log(f"Retrieve stock data for: {url}")
    try:
        rsp = requests.get(
            url,
            headers={"Referer": "https://finance.sina.com.cn"},
        )
        if rsp.status_code == 200:
            data = []
            ls = rsp.text.split("\n")
            for item in ls:
                if item == "":
                    continue
                item = item[23:].split(",")
                data.append([item[0][0:2], float(item[3])])
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

readConfig()

# import pdb; pdb.set_trace()
if inRest():
    with open(dataFile, 'w', encoding="utf-8") as fData:
        jsonData = {"runner_pid": os.getpid(), 'prices': retrieveStockData()}
        fData.write(json.dumps(jsonData))
    log("Rest day, exit.")
    sys.exit(0)

event_handler = ConfigFileEventHandler()
OneObserver = Observer()
OneObserver.schedule(event_handler, os.path.dirname(configFile), recursive=False)
OneObserver.start()


time_start1 = datetime.strptime("9:15", "%H:%M").time()
time_end1 = datetime.strptime("11:30", "%H:%M").time()
time_start2 = datetime.strptime("13:00", "%H:%M").time()
time_end2 = datetime.strptime("15:00", "%H:%M").time()

Data = {}
if os.path.exists(dataFile):
    with open(dataFile, 'r', encoding="utf-8") as fData:
        dataStr = fData.read()
        if dataStr:
            Data = json.loads(dataStr)
with open(dataFile, 'w', encoding="utf-8") as fData, open(dataLockFile, "w", encoding="utf-8") as fLock:
    data_modified_time = os.path.getmtime(dataFile)
    data_modified_date = datetime.fromtimestamp(data_modified_time).date()
    if data_modified_date == datetime.now().date() and "notified" in Data:
        Notified = Data["notified"]
    jsonData = {"runner_pid": os.getpid(), 'notified': Notified}
    while True:
        # import pdb; pdb.set_trace()
        data = retrieveStockData()
        checkNotify(data)
        jsonData['prices'] = data

        fLock.write('')
        fLock.flush()

        fData.seek(0)
        fData.write(json.dumps(jsonData))
        fData.truncate()
        fData.flush()

        now = datetime.now().time()
        if now >= time_start1 and now <= time_end1 \
                or now >= time_start2 and now <= time_end2:
            time.sleep(Config['delay'])
        else:
            log("Market inactive, exit.")
            break
