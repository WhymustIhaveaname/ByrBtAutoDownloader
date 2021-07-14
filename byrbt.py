#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2020 July
# @Author  : smyyan & ghoskno & WhymustIhaveaname
# @Software: Sublime Text

import time,os,re,pickle,requests,platform,sys,traceback,math
from contextlib import ContextDecorator
from requests.cookies import RequestsCookieJar
from bs4 import BeautifulSoup
from config import *

# 判断平台
osName = platform.system()
if osName not in ('Linux',):
    raise Exception('not support this system : %s'%(osName,))

LOGLEVEL={0:"DEBUG",1:"INFO",2:"WARN",3:"ERR",4:"FATAL"}
LOGFILE=sys.argv[0].split(".")
LOGFILE[-1]="log"
LOGFILE=".".join(LOGFILE)

def log(msg,l=1,end="\n",logfile=LOGFILE):
    st=traceback.extract_stack()[-2]
    lstr=LOGLEVEL[l]
    #now_str="%s %03d"%(time.strftime("%y/%m/%d %H:%M:%S",time.localtime()),math.modf(time.time())[0]*1000)
    now_str="%s"%(time.strftime("%y/%m/%d %H:%M:%S",time.localtime()),)
    perfix="%s [%s,%s:%03d]"%(now_str,lstr,st.name,st.lineno)
    if l<3:
        tempstr="%s %s%s"%(perfix,str(msg),end)
    else:
        tempstr="%s %s:\n%s%s"%(perfix,str(msg),traceback.format_exc(limit=5),end)
    print(tempstr,end="")
    if l>=1:
        with open(logfile,"a") as f:
            f.write(tempstr)

# 常量
_BASE_URL = 'https://bt.byr.cn/'

if osName == 'Windows':
    download_path = os.path.abspath(windows_download_path)
elif osName == 'Linux':
    download_path = os.path.abspath(linux_download_path)

transmission_cmd='transmission-remote -n %s '%(transmission_user_pw)

def get_url(url):
    return _BASE_URL + url

def login():
    from decaptcha import DeCaptcha
    from PIL import Image
    from io import BytesIO
    decaptcha = DeCaptcha()
    decaptcha.load_model(decaptcha_model)
    url = get_url('login.php')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}

    session = requests.session()
    for i in range(3):
        login_content = session.get(url)
        login_soup = BeautifulSoup(login_content.text, 'lxml')

        img_url = _BASE_URL + login_soup.select('#nav_block > form > table > tr:nth-of-type(3) img')[0].attrs['src']
        img_file = Image.open(BytesIO(session.get(img_url).content))

        captcha_text = decaptcha.decode(img_file)
        post_data={"username":username, "password":passwd, "imagestring":captcha_text,"imagehash":img_url.split('=')[-1]}
        login_res = session.post(get_url('takelogin.php'), headers=headers,data=post_data)

        if '最近消息' in login_res.text:
            cookies = {k:v for k, v in session.cookies.items()}
            with open(cookies_save_path, 'wb') as f:
                pickle.dump(cookies, f)
            break
        log("failed the %dth try, retry in 3 seconds"%(i),l=2)
        time.sleep(3)
    else:
        raise Exception('Failed to get Cookies!')
    return cookies


def load_cookie():
    if os.path.exists(cookies_save_path):
        #log('正在加载 cookie...')
        with open(cookies_save_path, 'rb') as read_path:
            byrbt_cookies = pickle.load(read_path)
    else:
        log('未发现 %s，正在获取 cookie...'%(cookies_save_path,))
        byrbt_cookies = login()
    return byrbt_cookies


def _get_tag(tag):
    """可能的 tags
        'free', 'twoup', 'twoupfree', 'halfdown', 'twouphalfdown', 'thirtypercentdown'
        '免费' , '2x上传', '免费&2x上传', '50%下载' , '50%下载&2x上传' , '30%下载',
    """
    if len(tag)>0:
        return tag.split('_')[0] # 去掉最后的 _bg

def _calc_size(size):
    size=size.strip()
    if size.endswith("GB"):
        size=float(size[0:-2])
    elif size.endswith("TB"):
        size=float(size[0:-2])*1024
    elif size.endswith("MB"):
        size=float(size[0:-2])/1024
    elif size.endswith("KB"):
        size=float(size[0:-2])/1048576
    else:
        log("size format error: %s"%(size),l=2)
        size=0.0
    return size

def parse_torrent_info(table):
    assert isinstance(table, list)
    l_time=[("年",8760),("月",720),("天",24),("时",1),("分",1/60)]
    torrent_infos = []
    for item in table:
        # tds 是网页上每一列的列表
        # 依次是， 0    1    2   5       6   7     8     9
        #        类型、题目、评论、存活时间、大小、做种数、下载数、完成数、
        tds = item.select('td')

        main_td = tds[1].select('table > tr > td')[0] # 第一列是信息最丰富的，值得一个单独的名字
        is_seeding = len(main_td.select('img[src="pic/seeding.png"]')) > 0
        is_finished = len(main_td.select('img[src="pic/finished.png"]')) > 0
        if is_seeding or is_finished:
            continue

        torrent_info = {'is_new':False,'is_hot':False,'is_recommended':False, 'tag':''}

        title = main_td.text.split('\n')
        torrent_info['title'] = title[0]
        torrent_info['sub_title'] = title[1] if len(title) == 2 else ''

        href = main_td.select('a')[0].attrs['href']
        torrent_info['seed_id'] = re.findall(r'id=(\d+)&', href)[0]

        temp = set([font.attrs['class'][0] for font in main_td.select('b > font') if 'class' in font.attrs.keys()])
        if 'hot' in temp:
            torrent_info['is_hot'] = True
        if 'new' in temp:
            torrent_info['is_new'] = True
        if 'recommended' in temp:
            torrent_info['is_recommended'] = True

        if 'class' in tds[1].select('table > tr')[0].attrs.keys():
            torrent_info['tag'] = _get_tag(tds[1].select('table > tr')[0].attrs['class'][0])

        torrent_info['cat'] = tds[0].select('img')[0].attrs['title']
        torrent_info['file_size'] = _calc_size(tds[6].text)
        torrent_info['seeding'] = int(tds[7].text) if tds[7].text.isdigit() else -1
        torrent_info['downloading'] = int(tds[8].text) if tds[8].text.isdigit() else -1
        torrent_info['finished'] = int(tds[9].text) if tds[9].text.isdigit() else -1

        time=tds[5].text
        torrent_info['live_time'] = 1 # in hour, 1 in case sigularity
        for k,v in l_time:
            if k in time:
                time=time.split(k)
                torrent_info['live_time']+=int(time[0].strip())*v
                time=time[1].strip()
        torrent_infos.append(torrent_info)

    return torrent_infos

def execCmd(cmd):
    with os.popen(cmd) as r:
        text = r.read()
    return text

def transmission_ls():
    """text_s is list of {'id': '153', 'done': '0%', 'size': '1GB', 'name': 'dadada'}"""
    text=execCmd(transmission_cmd+'-l')
    text_s=[]
    for t in text.split('\n')[1:-2]: #去掉第一和最后两个
        ts = t.split()
        torrent = {'id':ts[0],'done':ts[1],'name':ts[-1]}

        tracker_info=os.popen(transmission_cmd+"-t %s -it"%(torrent['id'])).read()
        byr_flag=True
        for i in tracker_info.split("\n\n"):
            if "tracker.byr.cn" not in i:
                byr_flag=False
                break
        if not byr_flag:
            continue

        detailed_info=os.popen(transmission_cmd+"-t %s -i"%(torrent['id'].strip("*"))).read()
        try:
            location_info=re.search("Location: (.+)",detailed_info).group(1)
            if not os.path.samefile(location_info,linux_download_path):
                continue

            torrent['seed_time']=re.search("Seeding Time.+?([0-9]+) seconds",detailed_info)
            if torrent['seed_time']:
                torrent['seed_time']=int(torrent['seed_time'].group(1))/86400 # in day
            else:
                torrent['seed_time']=1.0

            torrent['ratio']=re.search("Ratio: ([0-9\\.]+)",detailed_info)
            if torrent['ratio']:
                torrent['ratio']=float(torrent['ratio'].group(1))
            else:
                assert "Ratio: None" in detailed_info
                torrent['ratio']=0.0

            torrent['size']=_calc_size(re.search("Total size:.+?\\((.+?)wanted\\)",detailed_info).group(1))
            torrent['size']=max(torrent['size'],1.0)
        except Exception:
            log("parse transmission_ls failed:\n%s"%(detailed_info),l=3)
            continue
        text_s.append(torrent)
    return text_s

class TorrentBot(ContextDecorator):
    def __init__(self):
        super(TorrentBot, self).__init__()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        if os.path.exists(torrent_id_save_path):
            with open(torrent_id_save_path,'rb') as f:
                self.existed_torrent=pickle.load(f)
        else:
            self.existed_torrent=[]
        self.refresh()

    def refresh(self):
        byrbt_cookies = load_cookie()
        self.cookie_jar = RequestsCookieJar()
        for k, v in byrbt_cookies.items():
            self.cookie_jar[k] = v

    def remove(self,target_size,neo_value):
        exist_seeds=[]
        for i in transmission_ls():
            if i['id'][-1]=="*": # 未完成的后面有星号
                continue
            if i['seed_time']<14: # 两周之内的
                continue
            i['value']=i['ratio']/i['seed_time']
            exist_seeds.append(i)
        if len(exist_seeds)==0:
            return False
        exist_seeds.sort(key=lambda x: x['seed_time'],reverse=True)
        exist_seeds.sort(key=lambda x: x['value'])
        value_avg=[i['value'] for i in exist_seeds]
        value_avg=sum(value_avg)/len(value_avg)
        log("average seed value: %.2f"%(value_avg))

        del_size=0
        while del_size<target_size or len(exist_seeds)==0:
            rm_info = exist_seeds.pop(0)
            ucb=math.sqrt(math.log(rm_info['seed_time'])/rm_info['seed_time'])
            if neo_value+value_avg*ucb<rm_info['value']:
                continue
            log("正在删除 %s"%(remove_info['name']))
            res = execCmd(transmission_cmd+'-t %s --remove-and-delete'%(rm_info['id'],))
            if "success" not in res:
                log('删除失败 %s'%(rm_info))
                continue
            if os.path.exists(os.path.join(download_path, rm_info['name'])):
                log('删除成功，但文件似乎还在 %s'%(rm_info['name']),l=2)
                continue
            del_size+=rm_info['size']
        if del_size>target_size:
            return True
        else:
            return False

    def download_one(self, torrent_id):
        download_url = get_url('download.php?id=%s'%(torrent_id))
        for i in range(2):
            try:
                torrent = requests.get(download_url,cookies=self.cookie_jar,headers=self.headers)
                torrent_file_name = re.search('filename="\\[BYRBT\\](.+?)"',torrent.headers['content-disposition'].encode('iso8859-1').decode('utf-8'))
                if torrent_file_name is not None:
                    torrent_file_name="[BYRBT-%s]%s"%(torrent_id,torrent_file_name.group(1))
                    break
            except Exception:
                log('下载种子文件失败',l=3)
                self.refresh()
        else:
            log('下载种子文件失败')
            return False

        torrent_file_path = os.path.join(download_path,torrent_file_name)
        if os.path.exists(torrent_file_path):
            log("种子文件已存在")
            self.existed_torrent.append(torrent_id)
            return False

        with open(torrent_file_path, 'wb') as f:
            f.write(torrent.content)
        cmd_str = transmission_cmd+'-a "%s" -w %s'%(torrent_file_path,download_path)
        ret_val = os.system(cmd_str)
        if ret_val == 0:
            self.existed_torrent.append(torrent_id)
            log("添加种子文件至 Transmisson 成功")
            return True
        else:
            log("添加种子文件至 Transmisson 失败！",l=2)
            os.remove(torrent_file_path)
            return True # 这个 True 是不要再继续下之后的种子的意思

    def download_many(self,torrent_infos,size_ratio=0.01):
        free_wt=1.0 #越大越关注上传比，越小越关注上传量
        ok_infos=[] #将要下载的种子
        for i in torrent_infos:
            if i['seed_id'] in self.existed_torrent:
                continue
            if i['seeding']<=0 or i['finished']<=0:
                continue

            i['value']=i['finished']/(i['live_time']*i['seeding']) # 平均每天上传率可以增加多少
            if 'twoup' in i['tag']:
                i['value']*=2
            if 'free' in i['tag']:
                i['value']*=(1+free_wt)
            elif 'halfdown' in i['tag']:
                i['value']*=(1+0.5*free_wt)
            elif 'thirtypercentdown' in i['tag']:
                i['value']*=(1+0.7*free_wt)

            # 我不想下太大的文件
            if i['file_size']>50:
                i['value']*=0.5
            elif i['file_size']>30:
                i['value']*=0.7
            elif i['file_size']>20:
                i['value']*=0.8
            # 也不想下太小的文件
            if i['file_size']<0.5:
                i['value']*=0.3
            elif i['file_size']<0.8:
                i['value']*=0.5
            elif i['file_size']<1.0:
                i['value']*=0.7

            if i['value']>1/30: # 一个月回本
                ok_infos.append(i)

        ok_infos.sort(key=lambda x:x['value'],reverse=True)
        if len(ok_infos)==0:
            return 0

        exist_seeds=transmission_ls()
        torrent_size=sum([i['size'] for i in exist_seeds])
        remain_size=max_torrent_size*size_ratio # 每次下磁盘空间百分之一的种子，一天执行四次的话，一个月换一次血，真合理
        for ii,i in enumerate(ok_infos):
            s_temp='%d: %s %.2fGB value=%.2f(during%.1fdays) %s'%(ii,i['seed_id'],i['file_size'],i['value'],i['live_time'],i['title'])
            log('将要下载： %s'%(s_temp))
            if torrent_size+i['file_size']>max_torrent_size:
                log("磁盘空间不足(%.1fGB)，将执行自动清理"%(torrent_size))
                if not self.remove(torrent_size+i['file_size']-max_torrent_size,i['value']):
                    log("清理磁盘失败，跳过此种子")
                    continue
            if self.download_one(i['seed_id']):
                torrent_size+=i['file_size']
                remain_size-=i['file_size']
            if remain_size<0:
                break
        return len(ok_infos)

    def scan_one_page(self,page):
        if page==0:
            url="https://bt.byr.cn/torrents.php"
        else:
            url="https://bt.byr.cn/torrents.php?inclbookmarked=0&pktype=0&incldead=0&spstate=0&page=%d"%(page)
        try:
            getemp=requests.get(url,cookies=self.cookie_jar,headers=self.headers).content
            torrents_soup = BeautifulSoup(getemp,features='lxml')
            torrent_table = torrents_soup.select('.torrents > form > tr')[1:] #<table class="torrents" blabla>
            return parse_torrent_info(torrent_table)
        except Exception:
            log("获取失败： %s"%(url),l=2)
            self.refresh()
            return []

    def scan_many_pages(self,pstart,pend):
        log("正在扫描第 %d 至 %d 页"%(pstart,pend))
        torrent_infos=self.scan_one_page(pstart)
        for i in range(pstart+1,pend):
            time.sleep(2)
            torrent_infos+=self.scan_one_page(i)
        log("浏览了 %d 页，获得了 %d 组种子信息"%(pend-pstart,len(torrent_infos)))
        num_ok=self.download_many(torrent_infos)
        return num_ok

    def start(self):
        num_ok=self.scan_many_pages(0,check_page)
        if num_ok<=check_page: # 如果前几页看得上的种子不多，就往后再翻几页
            self.scan_many_pages(check_page,3*check_page)
        with open(torrent_id_save_path,'wb') as f:
            self.existed_torrent=pickle.dump(self.existed_torrent[-50:],f)


HELP_TEXT="""
    byrbt bot:
        挑选北邮人上最受欢迎、最被需要的种子做种
    usage:
        --main    run main program
        --help    print this message
"""

if __name__ == '__main__':
    #log(TorrentBot().scan_many_pages(70,80))
    #raise Exception
    if len(sys.argv)<2:
        log(HELP_TEXT,l=0)
        action_str=input("$ ")
    else:
        action_str=sys.argv[1]

    if action_str.endswith('help'):
        log(HELP_TEXT)
    elif action_str.endswith('main'):
        byrbt_bot=TorrentBot()
        byrbt_bot.start()
    elif action_str.endswith('remove'):
        byrbt_bot=TorrentBot()
        byrbt_bot.remove(max_torrent_size*0.2,-100.0)
    else:
        log('invalid argument')
        log(HELP_TEXT,l=0)