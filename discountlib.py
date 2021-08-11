import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
headers = {"user-agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}
pchomesession = requests.Session()
pchomesession.get("https://shopping.pchome.com.tw/",headers=headers)
def removehtml(text,htmltag):
	if htmltag in text:
		index1 = text.index(htmltag)
		index2 = text.index(">",index1)+1
		text = text[index2:]
		return removehtml(text,htmltag)
	return text

def sendtoline(key,i="資料有錯誤.請檢查資料謝謝"):
	print(i)
	return True
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
	global pchomesession
	id = url.split("?")[0].split("/")[-1]
	req =  pchomesession.get("https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod/%s&fields=Price,Discount,ShipType,Qty&_callback=json"%id,headers=headers)
	text = req.text
	top = text.index("json(")
	last = text.index(")",top)
	js = json.loads(text[top+5:last])
	for i in js:
		price = js[i]["Price"]["P"]
		print(str(js[i]),end=" ")
		if js[i]["Qty"] == 0:
			return "未販售"
		else:
			return price

def momo(url):
	id = url.split("i_code=")[1]
	text = requests.get("https://m.momoshop.com.tw/goods.momo?i_code=%s"%id,headers=headers).text
	momotop = text.index("<META property=\"product:price:amount\" content=\"")
	momolast = text.index("\">",momotop)
	price = int(text[momotop:momolast].split("content=\"")[1].replace(",",""))
	print(str(price),end = " ")
	return price

def momosearch(key):
	res = requests.get("https://m.momoshop.com.tw/search.momo?searchKeyword=%s&couponSeq=&cpName=&searchType=1&cateLevel=-1&cateCode=-1&ent=k&_imgSH=fourCardStyle"%key,headers=headers)
	print("search:",key,res)
	Soup = BeautifulSoup(res.text,"html5lib")
	item = Soup.select(".goodsItemLi")
	result = {}
	for i in item:
		tag = 0
		if len(i.select(".publishInfo")) != 0: #是書籍 切換a點到2
			tag = 2
		tid = "_".join(list(i.select("a")[tag].attrs.values()))
		result[tid] = i.select("a")[tag].attrs
	return result

def intervalcheck(data,i,lineid,sendtext): #判斷是否發訊息,並回傳存入至db的值
	if  data["intervalarr"].get(i) == None:
		data["intervalarr"][i] = 0
	if data["intervalarr"].get(i) == 0:
		sendtoline(lineid,sendtext)
	data["intervalarr"][i] += 1
	if  data["intervalarr"].get(i) >= data["interval"]:
		data["intervalarr"][i] = 0
	return data["intervalarr"]
