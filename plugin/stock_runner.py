import os
import json
import time
from datetime import datetime
import requests

configFile = os.path.expanduser("~/.stock.cfg.json")
dataFile = os.path.expanduser("~/.stock.dat.json")


def readConfig():
    with open(configFile, "r", encoding="utf-8") as f:
        try:
            stock = json.load(f)
        except:
            errFile = os.path.expanduser("~/.stock.error")
            with open(errFile, "w", encoding="utf-8") as f:
                import traceback

                traceback.print_exc(file=f)
                return
    stock_codes = ''
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

    return stock_codes


def retrieveStockData():
    try:
        rsp = requests.get(
            f"https://hq.sinajs.cn/rn={round(datetime.now().timestamp()*1000)}&list=s_sh000001,s_sz399001,s_sz399006,{stock_codes}",
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


stock_codes = readConfig()
if len(stock_codes):
    time_start1 = datetime.strptime("9:15", "%H:%M").time()
    time_end1 = datetime.strptime("11:30", "%H:%M").time()
    time_start2 = datetime.strptime("13:00", "%H:%M").time()
    time_end2 = datetime.strptime("15:00", "%H:%M").time()
    with open(dataFile, 'r+', encoding="utf-8") as file:
        data = file.read()
        if len(data) > 0:
            jsonData = json.loads(data)
        else:
            jsonData = {}
        while True:
            # import pdb; pdb.set_trace()
            data = retrieveStockData()
            jsonData['prices'] = data
            file.seek(0)
            file.write(json.dumps(jsonData))
            file.truncate()
            file.flush()

            now = datetime.now().time()
            if now >= time_start1 and now <= time_end1 \
                    or now >= time_start2 and now <= time_end2:
                time.sleep(5)
            else:
                break
