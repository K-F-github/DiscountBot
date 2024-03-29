import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
from urllib.parse import unquote
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

def pchomemulti(url):
	global pchomesession
	id =  list(i.split("?")[0].split("/")[-1] for i in url)
	data = {}
	for i in range(0,len(id),1000):
		text =  pchomesession.get("https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod?id=%s&fields=Price,Discount,ShipType,Qty&_callback=jsonpcb_prod"%(",".join(id[0+i:i+1000])),headers=headers).text
		top = text.index("jsonpcb_prod(")
		last = text.index(");}catch(e){if(window.console){console.log(e);}}",top)
		data = {**data, **json.loads(text[top+len("jsonpcb_prod("):last])}
	return data

def momo(url):
	id = url.split("i_code=")[1]
	text = requests.get("https://m.momoshop.com.tw/goods.momo?i_code=%s"%id,headers=headers).text
	momotop = text.find("<META property=\"product:price:amount\" content=\"")
	if momotop == -1:
		return "未販售"
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

def pchomeseatch(key):
	global pchomesession
	req =  pchomesession.get("https://ecshweb.pchome.com.tw/search/v3.3/all/results?q=%s&page=1&sort=sale/dc"%key,headers=headers)
	print("search:",key,req)
	data = {}
	if json.loads(req.text).get("prods") != None:
		for i in json.loads(req.text).get("prods"):
			data[i["Id"]] = i
	return data
	
def intervalcheck(data,i,lineid,sendtext): #判斷是否發訊息,並回傳存入至db的值
	if  data["intervalarr"].get(i) == None:
		data["intervalarr"][i] = 0
	if data["intervalarr"].get(i) == 0:
		sendtoline(lineid,sendtext)
	data["intervalarr"][i] += 1
	if  data["intervalarr"].get(i) >= data["interval"]:
		data["intervalarr"][i] = 0
	return data["intervalarr"]


def uniqlo(url):
	key = url.split("/")[-1]
	res = requests.get("https://www.uniqlo.com/tw/store/goods/%s"%key,headers=headers)
	print("search:",key,res,end=" ")
	searchword = "<script> var JSON_DATA = "
	momotop = res.text.find(searchword)
	if momotop == -1:
		return "未販售"
	momolast = res.text.index(";</script>",momotop)
	js = json.loads(res.text[momotop+len(searchword):momolast])
	js = js["GoodsInfo"]["goods"]["l2GoodsList"]
	price = 9999999999
	for i in js:
		if price > int(js[i]["L2GoodsInfo"]["cSalesPrice"]):
			price =int(js[i]["L2GoodsInfo"]["cSalesPrice"])
	print(str(price),end = " ")
	return price

def migo(item):
	res = requests.post("https://go.buy.mi.com/tw/comment/reviewheader",data={"from":"pc","commodity_id":item})
	print("search:",item,res,end=" ")
	js = json.loads(res.text)
	try:
		return int(js["data"]["commodity"]["price"])
	except:
		return "未販售"

def shopee(item):
	res = requests.get("https://shopee.tw/api/v4/item/get",params={"itemid":item.split("/")[-1].split("?")[0],"shopid":item.split("/")[-2]})
	print("search:",item,res,end=" ")
	js = json.loads(res.text)
	try:
		return int(int(js["data"]["price"])/100000)
	except:
		return "未販售"

def pttparser(urlid,recommend=None,q=None):
	#headers = {'Cookie':'over18=1'}
	params = ""
	data = {}
	url = "https://www.ptt.cc/bbs/%s/index.html"%(urlid)
	if recommend != None or q != None:
		if recommend != None:
			params = "recommend%3A"+recommend
		if q != None:
			params = "%s"%q
		if recommend != None and q != None:
			params = "recommend%3A"+recommend
			params += "+"+"+".join(q)
	if params != "":
		urlarr=[]
		for i in range(3):
			urlarr.append("https://www.ptt.cc/bbs/%s/search?page=%s&q=%s"%(urlid,i+1,params))
		for i in urlarr:
			res = requests.get(i, cookies={'over18': '1'})
				
	else:
		url = "https://www.ptt.cc/bbs/%s/index.html"%(urlid)
		for i in range(3):
			res = requests.get(url, cookies={'over18': '1'})
			if res.status_code == 200:
				Soup = BeautifulSoup(res.text,"html5lib")
				url = "https://www.ptt.cc"+Soup.select("#action-bar-container .btn-group-paging a")[1].attrs["href"]
				data.update(pttdata(res.text))
	return data

def pttdata(data):
	Soup = BeautifulSoup(data,"html5lib")
	result = {}
	for i in Soup.find_all(class_="r-ent"):
		if len(i.select("span")) != 0:
			grade = i.find("span").text
		else:
			grade = 0
		if len(i.select("a")) != 0:
			title = i.select("a")[0].text
			url = "https://www.ptt.cc"+i.select("a")[0].attrs["href"]
			result[url] = {}
			result[url]["grade"] = grade
			result[url]["title"] = title
	return result

def watsons(url):
	url = url.replace("https://www.watsons.com.tw/","").split("/")[:3]
	res = requests.get("https://www.watsons.com.tw/%s"%"/".join(url),headers=headers)
	print("search:",unquote(url[0]),res,end=" ")
	try:
		toptxt = "<div class=\"productPrice ng-star-inserted\">"
		top = res.text.index(toptxt)
		last = res.text.index("<",top+len(toptxt))
		return int(res.text[top:last].replace(toptxt,"").replace("$","").strip())
	except:
		return "未販售"

def yahooshop(url):
	res = requests.get("https://tw.buy.yahoo.com/gdsale/%s"%url.replace("https://tw.buy.yahoo.com/gdsale/","").split("/")[0],headers=headers)
	try:
		toptxt = "<script type=\"application/ld+json\">"
		top = res.text.index(toptxt)
		last = res.text.index("</script>",top+len(toptxt))
		js = json.loads(unquote(res.text[top:last].replace(toptxt,"")))
		print("search:",js[0]["name"],res,end=" ")
		return int(js[0]["offers"]["price"])
	except:
		return "未販售"

def lativ(url):
	res = requests.get("https://www.lativ.com.tw/Detail/%s"%url.replace("https://www.lativ.com.tw/Detail/","").split("/")[0],headers=headers)
	try:
		toptxt = "<script type=\"application/ld+json\">"
		top = res.text.index(toptxt)
		last = res.text.index("</script>",top+len(toptxt))
		js = json.loads(unquote(res.text[top:last].replace(toptxt,"")))
		print("search:",js["name"],res,end=" ")
		return int(js["offers"]["price"])
	except:
		return "未販售"
	
def etmall(url):
	res = requests.get("https://www.etmall.com.tw/i/%s"%url.replace("https://www.etmall.com.tw/i/","").split("/")[0],headers=headers)
	try:
		toptxt = "var ViewBag = "
		top = res.text.index(toptxt)
		last = res.text.index(";",top+len(toptxt))
		js = json.loads(unquote(res.text[top:last].replace(toptxt,"")))
		print("search:",js["TracingData"]["Name"],res,end=" ")
		return int(js["TracingData"]["SalePrice"])
	except:
		return "未販售"
