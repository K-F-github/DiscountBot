from rethinkdb import RethinkDB 
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
import sys,traceback
import discountlib as dlib
r = RethinkDB()
sysstarttime = datetime.now()
with r.connect( "localhost", 28015) as conn: #google excel處理
	if r.now().day().run(conn) != r.db("line_notify_funny").table("option").get("intervalrenew").run(conn)["data"]: #每天把通知次數歸零
		r.db("line_notify_funny").table("data").insert(r.db("line_notify_funny").table("data").without("intervalarr"),conflict="replace").run(conn)
		r.db("line_notify_funny").table("option").get("intervalrenew").update({"data":r.now().day()}).run(conn)
	exceptid = r.db("line_notify_funny").table("option").get("exceptid").run(conn)["data"]
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
		if lineid in exceptid: #清除無用的id
			print("pass",lineid)
			r.db("line_notify_funny").table("data").get(lineid).delete().run(conn)
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
			searchproduct = []
			for i in range(6,100):
				if "此系統僅作為提示用，不擔負商品販售或是任何履約保證（包含系統可用、系統穩定性等保證）" in tds[i].text:
					enddataflag = i
					break
				if "上午" in tds[i].text or "下午" in tds[i].text:
					continue
				data = str(tds[i]).split("<br/>")
				for j in data:
					temp = dlib.removehtml(dlib.removehtml(j,"<div"),"<td").replace("</div>","").replace("</td>","").strip()
					if temp != "" and temp not in checktext:
						checktext.append(temp)
						temp = temp.replace("  "," ").split(" ")
						#print(temp)
						if len(temp) >= 2:
							try:
								if temp[0] == "searchmomo":
									searchproduct.append(["searchmomo"," ".join(temp[1:])])
								elif temp[0] == "searchpchome":
									searchproduct.append(["searchpchome"," ".join(temp[1:])])
								elif temp[0] == "searchptt":
									#searchproduct.append(["searchptt"," ".join(temp[1:])])
									pass
								else:
									price = int(temp[0])
									url = temp[1]
									if "https:" in url:
										if "pchome.com.tw" in url:
											url = url.split("?")[0]
										if "momoshop.com.tw" in url:
											momotop = url.index("i_code")
											momolast = url.find("&",momotop)
											if momolast != -1:
												url = url[:momolast]
										if "https://momo.dm/" in url:
											url = requests.get(url,headers=dlib.headers).url #縮寫型先轉換
										product.append([price,url," ".join(temp[2:])])
									else:
										if "網址有誤："+" ".join(temp) not in errormsg:
											print("error",url)
											print(temp)
											errormsg.append("網址有誤："+" ".join(temp))
							except Exception as ex:
								print("商品處理",ex)
								if "資料有誤："+" ".join(temp) not in errormsg:
									errormsg.append("資料有誤："+" ".join(temp))
			for i in errormsg:
				dlib.sendtoline(lineid,i)
			starttime = tds[enddataflag-2].text
			endtime = tds[enddataflag-1].text
			insertdata = {}
			insertdata["id"] = lineid
			insertdata["interval"] = int(timeflag)
			insertdata["starttime"] = starttime.replace("上午","AM").replace("下午","PM")
			insertdata["endtime"] = endtime.replace("上午","AM").replace("下午","PM")
			insertdata["product"] = product
			insertdata["searchproduct"] = searchproduct
			if datetime.strptime(insertdata["starttime"],"%p %I:%M:%S") > datetime.strptime(insertdata["endtime"],"%p %I:%M:%S"):
				dlib.sendtoline(lineid,"您填寫的時間有問題，請檢查資料，謝謝")
				writetodb = False
			if len(product)+len(searchproduct) == 0:
				res = r.db("line_notify_funny").table("data").get(lineid).delete().run(conn)
				if res["deleted"] == 1:
					dlib.sendtoline(lineid,"資料清空")
				writetodb = False
			if len(product)+len(searchproduct) >= 20:
				dlib.sendtoline(lineid,"資料太多了，請減少到20筆")
				writetodb = False
			if writetodb:
				resdb = r.db("line_notify_funny").table("data").insert(insertdata,conflict="update").run(conn)
				if resdb["inserted"] == 1:
					dlib.sendtoline(lineid,"資料新增成功\r\n監控產品數："+str(len(product))+"\r\n監控搜尋數:"+str(len(searchproduct)))
				if resdb["replaced"] == 1:
					dlib.sendtoline(lineid,"資料修改成功\r\n監控產品數："+str(len(product))+"\r\n監控搜尋數:"+str(len(searchproduct)))
		except Exception as ex:
			if "list index out of range" != str(ex):
				print(ex)
			if lineid.strip() != "":
				dlib.sendtoline(lineid)
		index += 1

with r.connect( "localhost", 28015) as conn: #爬蟲gogo
	print("do parser")
	searchproductmomo = {}
	searchproductpchome = {}
	searchptt = {}
	pchomeprod = {}
	momoproduct = {}
	uniqliprod = {}
	anotherproduct = [] #放一些額外添加的網址做單筆，以後量大再做匯集優化
	for i in r.db("line_notify_funny").table("data").run(conn):
		for j in i["product"]:
			temp = i.copy()
			temp["product"] = j
			if "pchome.com.tw" in j[1]:
				if j[1] not in pchomeprod.keys():
					pchomeprod[j[1]]=[]
				pchomeprod[j[1]].append(temp)
			if "momoshop.com.tw" in j[1]:
				if j[1] not in momoproduct.keys():
					momoproduct[j[1]]=[]
				momoproduct[j[1]].append(temp)
			if "https://www.uniqlo.com/tw/store/goods/" in j[1]:
				if j[1] not in uniqliprod.keys():
					uniqliprod[j[1]]=[]
				uniqliprod[j[1]].append(temp)
			if "https://buy.mi.com/tw/item/" in j[1] or "https://shopee.tw/product/" in j[1] or "https://www.watsons.com.tw/" in j[1]:
				anotherproduct.append([j[1],temp])
		for j in i["searchproduct"]:
			if j[1] not in searchproductmomo.keys() and j[0] == "searchmomo":
				searchproductmomo[j[1]]=[]
			if j[1] not in searchproductpchome.keys() and j[0] == "searchpchome":
				searchproductpchome[j[1]] = []
			if j[1] not in searchptt.keys() and j[0] == "searchptt":
				searchptt[j[1]] = []
			temp = i.copy()
			if j[0] == "searchmomo":
				searchproductmomo[j[1]].append(temp)
			if j[0] == "searchpchome":
				searchproductpchome[j[1]].append(temp)
			if j[0] == "searchptt":
				searchptt[j[1]].append(temp)
	#處理pchome
	print("pchomeprod length:",len(pchomeprod))
	result = dlib.pchomemulti(pchomeprod.keys())
	for i in pchomeprod:
		try:
			print(i.split("?")[0].split("/")[-1],end=" ")
			js = result.get(i.split("?")[0].split("/")[-1]+"-000")
			if js == None or js.get("Qty") == 0:
				print("未販售")
				continue
			money = result[i.split("?")[0].split("/")[-1]+"-000"]["Price"]["P"]
			print(js,money,end=" ")
			print("")
			for data in pchomeprod[i]: #取出有監控這個產品的人做比較
				if data["product"][0] > money:
					if data.get("intervalarr") == None:
						data["intervalarr"] = {}
					if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
						sendtext = "現在價格:"+str(money)+" \r\n已達到設定的條件："+" ".join(str(i) for i in data["product"])
						data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendtext)
						r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
		except Exception as ex:
			print("pachome parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	#處理momo
	print("momoproduct length:",len(momoproduct))
	for i in momoproduct:
		try:
			print(i,end=" ")
			money = dlib.momo(i)
			if money == "未販售":
				print("未販售")
				continue
			for data in momoproduct[i]:  #取出有監控這個產品的人做比較
				if data["product"][0] > money:
					if data.get("intervalarr") == None:
						data["intervalarr"] = {}
					if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
						sendtext = "現在價格:"+str(money)+" \r\n已達到設定的條件："+" ".join(str(i) for i in data["product"])
						data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendtext)
						r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
			print("")
		except Exception as ex:
			print("momo parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	print("searchproductmomo length:",len(searchproductmomo))
	for i in searchproductmomo:
		try:
			print(i,end=" ")
			result = dlib.momosearch(i)
			dbresult = r.db("line_notify_funny").table("searchdata").get(i).run(conn)
			if dbresult == None: #第一次建立資料 不發通知
				r.db("line_notify_funny").table("searchdata").insert({"id":i,"data":result}).run(conn)
			else:
				diffset = set(list(result.keys())) - set(list(dbresult["data"].keys()))
				sendmsg = ""
				for diff in diffset:
					sendmsg += "新增項目："+result[diff]["title"] + "\r\n 網址:"
					if "momoshop.com.tw" in result[diff]["href"]:
						sendmsg += result[diff]["href"] +"\r\n"
					else:
						sendmsg += " https://m.momoshop.com.tw/"+result[diff]["href"] +"\r\n"
				if len(diffset) != 0:
					for data in searchproductmomo[i]:
						if data.get("intervalarr") == None:
							data["intervalarr"] = {}
						if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
							data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendmsg)
							r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
					r.db("line_notify_funny").table("searchdata").get(i).update({"data":result}).run(conn)
		except Exception as ex:
			print("search parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	print("searchproductpchome length:",len(searchproductpchome))
	for i in searchproductpchome:
		try:
			print(i,end=" ")
			result = dlib.pchomeseatch(i)
			dbresult = r.db("line_notify_funny").table("searchdata").get(i).run(conn)
			if dbresult == None: #第一次建立資料 不發通知
				r.db("line_notify_funny").table("searchdata").insert({"id":i,"data":result}).run(conn)
			else:
				diffset = set(list(result.keys())) - set(list(dbresult["data"].keys()))
				sendmsg = ""
				for diff in diffset:
					sendmsg += "新增項目："+result[diff]["name"] + "\r\n 網址: https://24h.pchome.com.tw/prod/"+diff +"\r\n"
				if len(diffset) != 0:
					for data in searchproductpchome[i]:
						if data.get("intervalarr") == None:
							data["intervalarr"] = {}
						if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
							data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendmsg)
							r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
					r.db("line_notify_funny").table("searchdata").get(i).update({"data":result}).run(conn)
		except Exception as ex:
			print("search parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	#處理 uniqliprod
	print("uniqliprod length:",len(uniqliprod))
	for i in uniqliprod:
		try:
			print(i,end=" ")
			money = dlib.uniqlo(i)
			if money == "未販售":
				print("未販售")
				continue
			for data in uniqliprod[i]:  #取出有監控這個產品的人做比較
				if data["product"][0] > money:
					if data.get("intervalarr") == None:
						data["intervalarr"] = {}
					if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
						sendtext = "現在價格:"+str(money)+" \r\n已達到設定的條件："+" ".join(str(i) for i in data["product"])
						data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendtext)
						r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
			print("")
		except Exception as ex:
			print("uniqliprod parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	#處理 ptt
	"""print("ptt length:",len(searchptt))
	for i in searchptt:
		try:
			print(i,end=" ")
			result = dlib.pttparser(i)
			dbresult = r.db("line_notify_funny").table("searchdata").get(i).run(conn)
			if dbresult == None: #第一次建立資料 不發通知
				r.db("line_notify_funny").table("searchdata").insert({"id":i,"data":result}).run(conn)
			else:
				diffset = set(list(result.keys())) - set(list(dbresult["data"].keys()))
				sendmsg = ""
				for diff in diffset:
					sendmsg += "新增項目："+result[diff]["name"] + "\r\n 網址: https://24h.pchome.com.tw/prod/"+diff +"\r\n"
				if len(diffset) != 0:
					for data in searchproductpchome[i]:
						if data.get("intervalarr") == None:
							data["intervalarr"] = {}
						if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
							data["intervalarr"] = dlib.intervalcheck(data,i,data["id"],sendmsg)
							r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
					r.db("line_notify_funny").table("searchdata").get(i).update({"data":result}).run(conn)
		except Exception as ex:
			print("search parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
	"""
	#清除沒有需要搜尋的key
	print("clean search data")
	key = list(r.db("line_notify_funny").table("searchdata").get_field("id").run(conn))-searchproductmomo.keys()-searchproductpchome.keys()-searchptt.keys()
	for i in key:
		print(i,r.db("line_notify_funny").table("searchdata").get(i).delete().run(conn))
	#anotherproduct 搜尋多的產品 通用型
	print("anotherproduct length:",len(anotherproduct)) 
	for i in anotherproduct:
		try:
			print(i[0],end=" ")
			#一律只拿回金額
			if "https://buy.mi.com/tw/item/" in i[0]: 
				money = dlib.migo(i[0].split("/")[-1])
			if "https://shopee.tw/product/" in i[0]:
				money = dlib.shopee(i[0])
			if "https://www.watsons.com.tw/" in i[0]:
				money = dlib.watsons(i[0])
			if money == "未販售":
				print("未販售")
				continue
			else:
				print(money,end=" ")
			data = i[1] #取出有監控這個產品的人做比較
			if data["product"][0] > money:
				if data.get("intervalarr") == None:
					data["intervalarr"] = {}
				if datetime.strptime(data["starttime"],"%p %I:%M:%S").time() < datetime.now().time() and datetime.now().time() < datetime.strptime(data["endtime"],"%p %I:%M:%S").time():
					sendtext = "現在價格:"+str(money)+" \r\n已達到設定的條件："+" ".join(str(i) for i in data["product"])
					data["intervalarr"] = dlib.intervalcheck(data,i[0],data["id"],sendtext)
					r.db("line_notify_funny").table("data").get(data["id"]).update({"intervalarr":data["intervalarr"]}).run(conn)
			print("")
		except Exception as ex:
			print("anotherproduct parser:",ex)
			traceback.print_tb(sys.exc_info()[2])
			pass
print("time:",(datetime.now()-sysstarttime).total_seconds(),"秒")
