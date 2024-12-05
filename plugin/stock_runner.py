import os
import sys
import json
import time
from datetime import datetime
import requests
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

configFile = os.path.expanduser("~/.stock.cfg.json")
dataFile = os.path.expanduser("~/.stock.dat.json")
dataLockFile = os.path.expanduser("~/.stock.dat.lock")

stock_codes = ''
observer = None

def global_exception_handler(exctype, value, traceback):
    print(f"Unhandled exception: {value}")
    if observer:
        observer.stop()
        observer.join()
    sys.__excepthook__(exctype, value, traceback)

sys.excepthook = global_exception_handler

def readConfig():
    global stock_codes
    with open(configFile, "r", encoding="utf-8") as f:
        try:
            stock = json.load(f)
        except:
            errFile = os.path.expanduser("~/.stock.error")
            with open(errFile, "w", encoding="utf-8") as f:
                import traceback
                traceback.print_exc(file=f)
                return
    for code in stock["codes"]:
        codeInt = int(code)
        if codeInt < 600000:
            stock_codes += "s_sz" + code + ","
        elif codeInt < 800000:
            stock_codes += "s_sh" + code + ","
        else:
            stock_codes += "s_bj" + code + ","

    if not len(stock["codes"]):
        stock_codes = stock_codes[:-1]


def retrieveStockData():
    codes = '' if not len(stock_codes) else ',' + stock_codes
    try:
        rsp = requests.get(
            f"https://hq.sinajs.cn/rn={round(datetime.now().timestamp()*1000)}&list=s_sh000001,s_sz399001,s_sz399006{codes}",
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
            return data
        else:
            return str(rsp.status_code)
    except Exception as er:
        return str(er)


class ConfigFileEventHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(patterns=[configFile])
    def on_modified(self, event):
        readConfig()

readConfig()

event_handler = ConfigFileEventHandler()
observer = Observer()
observer.schedule(event_handler, os.path.dirname(configFile), recursive=False)
observer.start()

time_start1 = datetime.strptime("9:15", "%H:%M").time()
time_end1 = datetime.strptime("11:30", "%H:%M").time()
time_start2 = datetime.strptime("13:00", "%H:%M").time()
time_end2 = datetime.strptime("17:00", "%H:%M").time()
with open(dataFile, 'w', encoding="utf-8") as fData, open(dataLockFile, "w", encoding="utf-8") as fLock:
    jsonData = {"runner_pid": os.getpid()}
    while True:
        # import pdb; pdb.set_trace()
        data = retrieveStockData()
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
            time.sleep(5)
        else:
            break
