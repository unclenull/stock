from datetime import datetime
import json
import random

NAME_PLACEHOLDER = '?'
VAL_PLACEHOLDER = '-'

def _qq_code_converter(code, isIndex=False):
    if isIndex:
        if not code.isdigit():
            defs = {
                "HSI": 'r_hk'
            }
            if code in defs:
                return f"{defs[code]}{code}"
            else:
                raise Exception(f"Unknown code: {code}")
        else:
            if code.startswith('000'):
                return "sh" + code
            elif code.startswith('399'):
                return "sz" + code
            else:
                return "bj" + code

    codeInt = int(code)
    if codeInt < 600000:
        return "sz" + code
    elif codeInt < 800000:
        return "sh" + code
    else:
        return "bj" + code

def _qq_rsp_parser(rsp, server, price):
    data = []
    ls = rsp.text.split("\n")
    # print(ls)
    # import pdb; pdb.set_trace()
    for item in ls:
        if item == "":
            continue
        slices = item.split("=")[1][1:].split("~")
        # import pdb; pdb.set_trace()
        title = slices[1]
        val = float(slices[3 if price else 32])
        data.append([title[0:2], val])
    return data

qq = {
    'url_formatter': lambda codes: f"https://qt.gtimg.cn/r=0.{random.randint(10**15, 10**16 - 1)}&q={codes}",
    'headers': {"Referer": "https://stockapp.finance.qq.com/"},
    'code_converter': _qq_code_converter,
    'rsp_parser': _qq_rsp_parser,
    'has_price': True,
}
def _sina_code_converter(code, isIndex=False):
    if isIndex:
        if not code.isdigit():
            defs = {
                "HSI": 'rt_hk'
            }
            if code in defs:
                return f"{defs[code]}{code}"
            else:
                raise Exception(f"Unknown code: {code}")
        else:
            if code.startswith('000'):
                return "s_sh" + code
            elif code.startswith('399'):
                return "s_sz" + code
            else:
                return "s_bj" + code

    codeInt = int(code)
    if codeInt < 600000:
        return "s_sz" + code
    elif codeInt < 800000:
        return "s_sh" + code
    else:
        return "s_bj" + code

def _sina_rsp_parser(rsp, server, price):
    data = []
    ls = rsp.text.split("\n")
    # print(ls)
    # import pdb; pdb.set_trace()
    for item in ls:
        if item == "":
            continue
        slices = item.split("=")[1][1:].split(",")
        if len(slices) > 8:
            title = slices[1]
            val = float(slices[6 if price else 8])
        else:
            title = slices[0]
            if float(slices[1]) == 0:
                val = VAL_PLACEHOLDER # non-support
            else:
                val = float(slices[1 if price else 3])
        data.append([title[0:2], val])
    return data

sina = {
    'url_formatter': lambda codes: f"https://hq.sinajs.cn/rn={round(datetime.now().timestamp()*1000)}&list={codes}",
    'headers': {"Referer": "https://finance.sina.com.cn"},
    'code_converter': _sina_code_converter,
    'rsp_parser': _sina_rsp_parser,
    'has_price': True,
}


def _east_code_converter(code, isIndex=False):
    if isIndex:
        if not code.isdigit():
            defs = {
                "HSI": '100'
            }
            if code in defs:
                return f"{defs[code]}.{code}"
            else:
                raise Exception(f"Unknown code: {code}")
        else:
            if code.startswith('000'):
                return "1." + code
            else:
                return "0." + code

    codeInt = int(code)
    if codeInt > 600000 and codeInt < 700000:
        return "1." + code
    else:
        return "0." + code

def _east_rsp_parser(rsp, server, price):
    data = []
    ls = json.loads(rsp.text[28:-2])['data']['diff']
    # import pdb; pdb.set_trace()
    for item in ls:
        data.append([item['f14'], item['f2' if price else 'f3']])
    return data

east = {
    'url_formatter': lambda codes: f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={codes}&fields=f2,f3,f14&cb=qa_wap_jsonpCB1737645019281",
    'headers': {"Referer": "https://guba.eastmoney.com/"},
    'code_converter': _east_code_converter,
    'rsp_parser': _east_rsp_parser,
    'has_price': True,
}


def _xq_code_converter(code, isIndex=False):
    if isIndex:
        if not code.isdigit():
            defs = {
                "HSI": 'HK'
            }
            if code in defs:
                return f"{defs[code]}{code}"
            else:
                raise Exception(f"Unknown code: {code}")
        else:
            if code.startswith('000'):
                return "SH" + code
            elif code.startswith('399'):
                return "SZ" + code
            else:
                return "BJ" + code

    codeInt = int(code)
    if codeInt < 600000:
        return "SZ" + code
    elif codeInt < 800000:
        return "SH" + code
    else:
        return "BJ" + code

def _xq_rsp_parser(rsp, server, price):
    data = []
    ls = json.loads(rsp.text)['data']
    # print(ls)
    # import pdb; pdb.set_trace()
    dataDict = {}
    for item in ls:
        dataDict[item['symbol']] = item['current' if price else 'percent']
    for code in server['codes']:
        data.append([NAME_PLACEHOLDER, dataDict[code]])
    return data

xq = {
    'url_formatter': lambda codes: f"https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={codes}",
    'headers': {"Referer": "https://xueqiu.com/"},
    'code_converter': _xq_code_converter,
    'rsp_parser': _xq_rsp_parser,
    'has_price': True,
}


def _cls_code_converter(code, isIndex=False):
    if isIndex:
        if not code.isdigit():
            defs = {
                "HSI": 'HK'
            }
            if code in defs:
                return f"{defs[code]}{code}"
            else:
                raise Exception(f"Unknown code: {code}")
        else:
            if code.startswith('000'):
                return "sh" + code
            elif code.startswith('399'):
                return "sz" + code
            else:
                return code + ".BJ"

    codeInt = int(code)
    if codeInt < 600000:
        return "sz" + code
    elif codeInt < 800000:
        return "sh" + code
    else:
        return code + ".BJ"

def _cls_rsp_parser(rsp, server, _):
    data = []
    dc = json.loads(rsp.text)['data']
    # print(ls)
    # import pdb; pdb.set_trace()
    for code in server['codes']:
        if code in dc:
            data.append([NAME_PLACEHOLDER, round(dc[code] * 100, 2)])
        else:
            data.append([NAME_PLACEHOLDER, VAL_PLACEHOLDER])
    return data

cls = {
    'url_formatter': lambda codes: f"https://x-quote.cls.cn/quote/stock/refresh?secu_codes={codes}&app=CailianpressWeb&os=web&sv=8.4.6&sign=9f8797a1f4de66c2370f7a03990d2737",
    'headers': {"Referer": "https://www.cls.cn/"},
    'code_converter': _cls_code_converter,
    'rsp_parser': _cls_rsp_parser,
    'has_price': False,
}

def _sohu_code_converter(code, isIndex=False):
    if isIndex:
        return ('zs_' + code) if code.isdigit() else ''
    else:
        return 'cn_' + code

def _sohu_rsp_parser(rsp, server, price):
    data = []
    ls = json.loads(rsp.text[10:-3])[1:]
    # import pdb; pdb.set_trace()
    for item in ls:
        if len(item):
            data.append([item[1], item[2] if price else item[3][0:-1]])
        else:
            data.append([NAME_PLACEHOLDER, VAL_PLACEHOLDER])
    return data


sohu = {
    'url_formatter': lambda codes: f"http://s.m.sohu.com/newstocklistq?code={codes}&_={round(datetime.now().timestamp()*1000)}",
    'headers': {"Referer": "http://s.m.sohu.com/h5apps/t/mystock.html"},
    'code_converter': _sohu_code_converter,
    'rsp_parser': _sohu_rsp_parser,
    'has_price': True,
}
Servers = (east, qq, sina, xq, cls, sohu)
