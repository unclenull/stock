from datetime import datetime
import json
import random

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

def _sina_rsp_parser(rsp, server):
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
            val = float(slices[8])
        else:
            title = slices[0]
            if float(slices[1]) == 0:
                val = '-' # non-support
            else:
                val = float(slices[3])
        data.append([title[0:2], val])
    return data

sina = {
    'url_formatter': lambda codes: f"https://hq.sinajs.cn/rn={round(datetime.now().timestamp()*1000)}&list={codes}",
    'headers': {"Referer": "https://finance.sina.com.cn"},
    'code_converter': _sina_code_converter,
    'rsp_parser': _sina_rsp_parser
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

def _east_rsp_parser(rsp, server):
    data = []
    ls = json.loads(rsp.text[28:-2])['data']['diff']
    # import pdb; pdb.set_trace()
    for item in ls:
        data.append([item['f14'].replace(' ', '')[0:2], item['f3']])
    return data

east = {
    'url_formatter': lambda codes: f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={codes}&fields=f3,f14&cb=qa_wap_jsonpCB1737645019281",
    'headers': {"Referer": "https://guba.eastmoney.com/"},
    'code_converter': _east_code_converter,
    'rsp_parser': _east_rsp_parser
}


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

def _qq_rsp_parser(rsp, server):
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
        val = float(slices[32])
        data.append([title[0:2], val])
    return data

qq = {
    'url_formatter': lambda codes: f"https://qt.gtimg.cn/r=0.{random.randint(10**15, 10**16 - 1)}&q={codes}",
    'headers': {"Referer": "https://stockapp.finance.qq.com/"},
    'code_converter': _qq_code_converter,
    'rsp_parser': _qq_rsp_parser
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

def _xq_rsp_parser(rsp, server):
    data = []
    ls = json.loads(rsp.text)['data']
    # print(ls)
    # import pdb; pdb.set_trace()
    dataDict = {}
    for item in ls:
        dataDict[item['symbol']] = item['percent']
    for code in server['codes']:
        data.append(['?', dataDict[code]])
    return data

xq = {
    'url_formatter': lambda codes: f"https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={codes}",
    'headers': {"Referer": "https://xueqiu.com/"},
    'code_converter': _xq_code_converter,
    'rsp_parser': _xq_rsp_parser
}

Servers = (sina, east, qq, xq)
