from rethinkdb import RethinkDB 
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
r = RethinkDB()
def removehtml(text,htmltag):
	if htmltag in text:
		index1 = text.index(htmltag)
		index2 = text.index(">",index1)+1
		text = text[index2:]
		return removehtml(text,htmltag)
	return text

def sendtoline(key,i="資料有錯誤.請檢查資料謝謝"):
	try:
		sendheaders = {
		"Authorization": "Bearer " + key,
		"Content-Type": "application/x-www-form-urlencoded"
		}
		params = {"message":i }
		res = requests.post("https://notify-api.line.me/api/notify",headers=sendheaders, params=params)
		print(res.text)
	except:
		pass
	
def pchome(url):
	id = url.split("?")[0].split("/")[-1]
	headers = {"user-agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}
	text=  requests.get("https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod/%s&fields=Price,Discount&_callback=json"%id).text
	top = text.index("json(")
	last = text.index(")",top)
	js = json.loads(text[top+5:last])
	for i in js:
		price = js[i]["Price"]["P"]
		print(url,str(price))
		return price

def momo(url):
	headers = {"user-agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}
	id = url.split("i_code=")[1]
	text = requests.get("https://m.momoshop.com.tw/goods.momo?i_code=%s"%id,headers=headers).text
	momotop = text.index("<META property=\"product:price:amount\" content=\"")
	momolast = text.index("\">",momotop)
	price = int(text[momotop:momolast].split("content=\"")[1].replace(",",""))
	print(url,str(price))
	return price
	
with r.connect( "localhost", 28015) as conn: #google excel處理
	excelurl = r.db("line_notify_funny").table("option").get("excelurl").run(conn)["data"]
	res = requests.get(excelurl)
	gidindex1 = res.text.index("gridId")
	gidindex2 = res.text.index(",",gidindex1)
	gid = res.text[gidindex1:gidindex2].split(":")[1]
	Soup = BeautifulSoup(res.text,"html5lib")
	index = 1
	while True:
		tr = Soup.select("#"+gid+"R"+str(index))
		if len(tr) != 1:
			break
		tds = tr[0].parent()
		lineid = tds[3].text
		if lineid == "":
			index += 1
			continue
		print("處理",lineid)
		try:
			timeflag = tds[5].text.replace("每","").replace("小時","")
			enddataflag = 0
			writetodb = True
			product = []
			errormsg = []
			checktext = []
			for i in range(6,100):
				if "此系統僅作為提示用，不擔負商品販售或是任何履約保證（包含系統可用、系統穩定性等保證）" in tds[i].text:
					enddataflag = i
					break
				if "上午" in tds[i].text or "下午" in tds[i].text:
					continue
				data = str(tds[i]).split("<br/>")
				for j in data:
					temp = removehtml(removehtml(j,"<div"),"<td").replace("</div>","").replace("</td>","").strip()
					if temp != "" and temp not in checktext:
						checktext.append(temp)
						temp = temp.split(" ")
						if len(temp) >= 2:
							try:
								price = int(temp[0])
								url = temp[1]
								if "https:" in url:
									if "pchome.com.tw" in url:
										url = url.split("?")[0]
									if "momoshop.com.tw" in url:
										momotop = url.index("i_code")
										momolast = url.index("&",momotop)
										url = url[:momolast]
									product.append([price,url," ".join(temp[2:])])
								else:
									if "網址有誤："+" ".join(temp) not in errormsg:
										errormsg.append("網址有誤："+" ".join(temp))
							except Exception as ex:
								print("商品處理",ex)
								if "資料有誤："+" ".join(temp) not in errormsg:
									errormsg.append("資料有誤："+" ".join(temp))
			for i in errormsg:
				sendtoline(lineid,i)
			starttime = tds[enddataflag-2].text
			endtime = tds[enddataflag-1].text
			insertdata = {}
			insertdata["id"] = lineid
			insertdata["interval"] = int(timeflag)
			insertdata["starttime"] = starttime.replace("上午","AM").replace("下午","PM")
			insertdata["endtime"] = endtime.replace("上午","AM").replace("下午","PM")
			insertdata["product"] = product
			if datetime.strptime(insertdata["starttime"],"%p %I:%M:%S") > datetime.strptime(insertdata["endtime"],"%p %I:%M:%S"):
				sendtoline(lineid,"您填寫的時間有問題，請檢查資料，謝謝")
				writetodb = False
			if len(product) == 0:
				r.db("line_notify_funny").table("data").get(lineid).delete().run(conn)
				sendtoline(lineid,"資料清空")
				writetodb = False
			if len(product) >= 10:
				sendtoline(lineid,"資料太多了，請減少到十筆")
				writetodb = False
			if writetodb:
				resdb = r.db("line_notify_funny").table("data").insert(insertdata,conflict="update").run(conn)
				if resdb["inserted"] == 1:
					sendtoline(lineid,"資料新增成功")
				if resdb["replaced"] == 1:
					sendtoline(lineid,"資料修改成功")
		except Exception as ex:
			if "list index out of range" != str(ex):
				print(ex)
			if lineid.strip() != "":
				sendtoline(lineid)
		index += 1

with r.connect( "localhost", 28015) as conn: #爬蟲gogo
	print("do parser")
	allproduct = {}
	for i in r.db("line_notify_funny").table("data").run(conn):
		for j in i["product"]:
			if j[1] not in allproduct.keys():
				allproduct[j[1]]=[]
			temp = i.copy()
			temp["product"] = j
			allproduct[j[1]].append(temp)
	print("allproduct length:",len(allproduct))
	for i in allproduct:
		try:
			if "pchome.com.tw" in i:
				money =  pchome(i)
			if "momoshop.com.tw" in i:
				money = momo(i)
			alldata = allproduct[i]
			for data in alldata:
				if data["product"][0] > money:
					if data.get("intervalarr") == None:
						data["intervalarr"] = {}
					if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
						if  data["intervalarr"].get(i) == None:
							data["intervalarr"][i] = 0
						if data["intervalarr"].get(i) == 0:
							sendtext = "現在價格:"+str(money)+" \r\n已達到設定的條件："+" ".join(str(i) for i in data["product"])
							sendtoline(data["id"],sendtext)
						data["intervalarr"][i] += 1
						if  data["intervalarr"].get(i) >= data["interval"]:
							data["intervalarr"][i] = 0
						r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
		except Exception as ex:
			print("parser:",ex)
			pass
	print("finish")
