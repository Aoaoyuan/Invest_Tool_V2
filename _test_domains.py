
import requests
domains = ["https://push2his.eastmoney.com", "http://push2his.eastmoney.com"]
params = {"secid":"1.600085","fields1":"f1,f2,f3,f4,f5,f6",
          "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
          "klt":"101","fqt":"1","beg":"19970601","end":"20260706","lmt":"10000"}
headers = {"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com"}
for d in domains:
    try:
        r = requests.get(d + "/api/qt/stock/kline/get", params=params, headers=headers, timeout=15)
        j = r.json()
        kls = j.get("data",{}).get("klines",[])
        print(f"{d}: {len(kls)} klines")
        if kls:
            first = kls[0].split(",")[0]
            last = kls[-1].split(",")[0]
            print(f"  Range: {first} ~ {last}")
    except Exception as e:
        print(f"{d}: {type(e).__name__}")
