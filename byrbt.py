#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2020 July
# @Author  : smyyan & ghoskno & WhymustIhaveaname
# @Software: Sublime Text

import time,os,re,pickle,requests,platform,sys,traceback,math
from contextlib import ContextDecorator
from requests.cookies import RequestsCookieJar
from bs4 import BeautifulSoup
from tqdm import tqdm
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
        size=float(size[0:-2])*1000.0
    elif size.endswith("MB"):
        size=float(size[0:-2])/1000.0
    elif size.endswith("KB"):
        size=float(size[0:-2])/100000.0
    else:
        log("size format error: %s"%(size),l=2)
        size=1.0
    return size

def parse_torrent_info(table):
    assert isinstance(table, list)
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

        torrent_info = {'tag':''}

        title = main_td.text.split('\n')
        torrent_info['title'] = title[0]
        torrent_info['sub_title'] = title[1] if len(title) == 2 else ''

        href = main_td.select('a')[0].attrs['href']
        torrent_info['seed_id'] = re.findall(r'id=(\d+)&', href)[0]

        if 'class' in tds[1].select('table > tr')[0].attrs.keys():
            torrent_info['tag'] = _get_tag(tds[1].select('table > tr')[0].attrs['class'][0])

        torrent_info['cat'] = tds[0].select('img')[0].attrs['title']
        torrent_info['file_size'] = _calc_size(tds[6].text)
        torrent_info['seeding'] = int(tds[7].text) if tds[7].text.isdigit() else -1
        torrent_info['downloading'] = int(tds[8].text) if tds[8].text.isdigit() else 0
        torrent_info['finished'] = int(tds[9].text) if tds[9].text.isdigit() else -1

        time=tds[5].text
        torrent_info['live_time'] = 0.0 # in day
        for k,v in [("年",365),("月",30),("天",1),("时",1/24),("分",1/1440)]:
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
    log("Collecting detail infos for existed seeds...",l=0)
    for t in tqdm(text.split('\n')[1:-2],ncols=75,bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'): #去掉第一和最后两个
        ts = t.split()
        torrent = {'id':ts[0],'done':ts[1],'name':ts[-1]}

        tracker_info=os.popen(transmission_cmd+"-t %s -it"%(torrent['id'])).read()
        if any(["tracker.byr.cn" not in i for i in tracker_info.split("\n\n")]):
            continue

        detailed_info=os.popen(transmission_cmd+"-t %s -i"%(torrent['id'].strip("*"))).read()
        try:
            location_info=re.search("Location: (.+)",detailed_info).group(1)
            if not os.path.samefile(location_info,linux_download_path):
                continue

            #torrent['seed_time']=re.search("Seeding Time.+?([0-9]+) seconds",detailed_info)
            seed_t=re.search("Date added:(.+)",detailed_info) #Wed Jul 14 21:53:49 2021
            seed_t=time.strptime(seed_t.group(1).strip(),"%a %b %d %H:%M:%S %Y")
            seed_t=time.mktime(seed_t)
            torrent['seed_time']=(time.time()-seed_t)/86400 # in day

            torrent['ratio']=re.search("Ratio: ([0-9\\.]+)",detailed_info)
            if torrent['ratio']:
                torrent['ratio']=float(torrent['ratio'].group(1))
            else:
                assert "Ratio: None" in detailed_info
                torrent['ratio']=0.0

            torrent['size']=_calc_size(re.search("Total size:.+?\\((.+?)wanted\\)",detailed_info).group(1))
        except Exception:
            log("parse transmission's ls failed:\n%s"%(detailed_info),l=3)
            continue
        text_s.append(torrent)
    return text_s

class AutoDown(ContextDecorator):
    def __init__(self):
        super(AutoDown,self).__init__()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        self.rmable_seeds=None
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

    def remove_init(self,tls):
        self.rmable_seeds=[]
        for i in tls:
            if i['id'][-1]=="*": # 忽略未完成的 (后面有星号)
                continue
            if i['seed_time']<RM_PEOTECT_TIME:
                continue
            i['value']=i['ratio']/i['seed_time']
            i['deleted']=False
            self.rmable_seeds.append(i)
        rmable_size=sum([i['size'] for i in self.rmable_seeds])
        if rmable_size>max_torrent_size/3:
            self.rmable_avg_val=sum([i['value']*i['size'] for i in self.rmable_seeds])/rmable_size
            # 删除每天做种率低的，做种率一样（通常因为都是0）删早的
            self.rmable_seeds.sort(key=lambda x: x['seed_time'],reverse=True)
            self.rmable_seeds.sort(key=lambda x: x['value'])
        else:
            self.rmable_seeds=[]
        #log(["%.1f, %.2f"%(i['seed_time'],i['value']) for i in self.rmable_seeds],l=0)
        #log(rmable_size,l=0)
        #log("average seed value: %.2f"%(self.rmable_avg_val),l=0)

    def remove(self,target_size,neo_value):
        del_size=0
        for rm_info in self.rmable_seeds:
            if rm_info['deleted']:
                continue
            ucb=UNFAITHFULNESS*math.sqrt(math.log(rm_info['seed_time'])/rm_info['seed_time'])
            if neo_value+self.rmable_avg_val*ucb<rm_info['value']:
                continue

            #log("%.2f+%.2f>%.2f"%(neo_value,self.rmable_avg_val*ucb,rm_info['value']))
            log("正在删除 %s"%(rm_info,))
            res=execCmd(transmission_cmd+'-t %s --remove-and-delete'%(rm_info['id'],))
            if "success" not in res:
                log('删除失败：%s'%(res),l=2)
                continue
            if os.path.exists(os.path.join(download_path,rm_info['name'])):
                log('删除失败，但文件还在：%s'%(res),l=2)
                continue

            del_size+=rm_info['size']
            rm_info['deleted']=True
            #log("removed %.2f of %.2f"%(del_size,target_size))
            if del_size>target_size:
                break
        return del_size

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

    def piecewise_linear(pts,x):
        if len(pts)<2:
            return 1.0
        if x>pts[0][0]>pts[1][0] or x<pts[0][0]<pts[1][0]:
            return pts[0][1]
        for i in range(len(pts)-1):
            if pts[i][0]>=x>pts[i+1][0] or pts[i][0]<=x<pts[i+1][0]:
                return ((pts[i][0]-x)*pts[i+1][1]+(x-pts[i+1][0])*pts[i][1])/(pts[i][0]-pts[i+1][0])
        else:
            return 1.0

    def download_many(self,torrent_infos,size_ratio=0.01):
        ok_infos=[] #将要下载的种子
        for i in torrent_infos:
            if i['seed_id'] in self.existed_torrent:
                continue
            if i['seeding']<=0 or i['finished']<=0:
                continue

            # 计算平均每天上传率可以增加多少
            # downloading is more important than finished, so *1.5
            # live_time +2.0 to avoid sigularity and to preference old seeds
            # there will be one more seeding after I downloaded, so seeding +1
            i['value']=(i['finished']+i['downloading']*1.5)/((i['live_time']+2.0)*(i['seeding']+1))
            if 'twoup' in i['tag']:
                i['value']*=2
            # free tag's buff, FREE_WT defaults to 1.0
            if 'free' in i['tag']:
                i['value']*=(1+FREE_WT)
            elif 'halfdown' in i['tag']:
                i['value']*=(1+0.5*FREE_WT)
            elif 'thirtypercentdown' in i['tag']:
                i['value']*=(1+0.7*FREE_WT)

            i['value']*=AutoDown.piecewise_linear(SEED_NUM_DEBUFF,i['seeding'])
            i['value']*=AutoDown.piecewise_linear(LARGE_FILE_DEBUFF,i['file_size'])
            i['value']*=AutoDown.piecewise_linear(SMALL_FILE_DEBUFF,i['file_size'])

            if i['value']>1/COST_RECOVERY_TIME:
                ok_infos.append(i)

        if len(ok_infos)==0:
            return 0

        ok_infos.sort(key=lambda x:x['value'],reverse=True)
        exist_seeds=transmission_ls()
        torrent_size=sum([i['size'] for i in exist_seeds])
        remain_size=max_torrent_size*size_ratio # 每次下磁盘空间百分之一的种子，一天执行四次的话，一个月换一次血，真合理
        rmable_size=max_torrent_size #可能被清理空间的上限
        for ii,i in enumerate(ok_infos):
            if i['file_size']>rmable_size:
                continue
            #s_temp='#%d: %s %.2fGB value is %.2f during %.1f day(s) %s'%(ii,i['seed_id'],i['file_size'],i['value'],i['live_time'],i['title'])
            log('将要下载 #%d %s'%(ii,i))
            if torrent_size+i['file_size']>max_torrent_size:
                if self.rmable_seeds==None:
                    log("磁盘空间不足(%.1fGB)，将执行自动清理"%(torrent_size))
                    self.remove_init(exist_seeds)
                target_size=torrent_size+i['file_size']-max_torrent_size
                removed_size=self.remove(target_size,i['value'])
                torrent_size-=removed_size
                if removed_size<target_size:
                    log("清理磁盘失败，跳过此种子")
                    rmable_size=min(rmable_size,i['file_size'])
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
        num_ok=self.scan_many_pages(0,CHECK_PAGE_NUM)
        if num_ok<=CHECK_PAGE_NUM: # 如果前几页看得上的种子不多，就往后再翻几页
            self.scan_many_pages(CHECK_PAGE_NUM,3*CHECK_PAGE_NUM)
        with open(torrent_id_save_path,'wb') as f:
            self.existed_torrent=pickle.dump(self.existed_torrent[-SEED_ID_KEEP_NUM:],f)

    def ls():
        exist_seeds=transmission_ls()
        torrent_size=sum([i['size'] for i in exist_seeds])
        log("There are now %d seeds with total size %.1f GB (after fully downloaded)."%(len(exist_seeds),torrent_size))
        for i in exist_seeds:
            i['value']=i['ratio']/i['seed_time']
        tot_upload=sum([i['size']*i['ratio'] for i in exist_seeds])
        avg_ratio=sum([i['value']*i['size'] for i in exist_seeds])/torrent_size
        log("Total upload: %.1f GB. Average value: %.2f"%(tot_upload,avg_ratio))
        exist_seeds.sort(key=lambda x:x['seed_time'],reverse=False)
        exist_seeds.sort(key=lambda x:x['value'],reverse=True)
        pretty_text=["\t  id value   ratio stime size(GB) name",]
        pretty_text+=["\t%4d %5.2f/d %5.1f %5.1f %6.1f   %s"\
                        %(int(i['id']),i['ratio']/i['seed_time'],i['ratio'],i['seed_time'],i['size'],i['name']) for i in exist_seeds]
        pretty_text="\n".join(pretty_text)
        log("Sorted by value:\n%s"%(pretty_text),l=0)

HELP_TEXT="""
    ByrBt Auto-Downloader:
        挑选北邮人上最受欢迎、最被需要的种子做种
    usage:
        --main    run main program
        --help    print this message
        --ls      list details of seeds managed by this programme"""

if __name__ == '__main__':
    if len(sys.argv)<2:
        log(HELP_TEXT)
        action_str=input("$ ")
    else:
        action_str=sys.argv[1]

    if action_str.endswith('help'):
        log(HELP_TEXT,l=0)
    elif action_str.endswith('main'):
        try:
            byrbt_bot=AutoDown()
            byrbt_bot.start()
        except Exception:
            log("",l=3)
    elif action_str.endswith('ls'):
        AutoDown.ls()
    elif action_str.endswith('rm'):
        AutoDown().remove_init(transmission_ls())
    else:
        log('invalid argument')
        log(HELP_TEXT,l=0)
