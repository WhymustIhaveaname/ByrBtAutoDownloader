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
#和上一个版本兼容，上个版本不可设置 size_ratio
if 'SIZE_RATIO' not in globals():
    SIZE_RATIO=1.0

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

if osName == 'Windows':
    download_path = os.path.abspath(windows_download_path)
elif osName == 'Linux':
    download_path = os.path.abspath(linux_download_path)

# 进度条的格式
bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}"

def get_url(url):
    return 'https://byr.pt/%s'%(url,)

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

        img_url = get_url(login_soup.select('#nav_block > form > table > tr:nth-of-type(3) img')[0].attrs['src'])
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

def _calc_size_byr(size):
    """
        将文字形式的 xx MB 转换为以 GB 为单位的浮点数
        北邮人是1024派的, Linux 是 1000 派的, 所以 GB 会差 1-(1000/1024)**3=6.9%
    """
    size=size.strip().upper()
    if size.endswith("GB"):
        size=float(size[0:-2])*(1024**3)/(1000**3)
    elif size.endswith("MB"):
        size=float(size[0:-2])*(1024**2)/(1000**3)
    elif size.endswith("KB"):
        size=float(size[0:-2])*(1024**1)/(1000**3)
    elif size.endswith("TB"):
        size=float(size[0:-2])*(1024**4)/(1000**3)
    else:
        log("size format error: %s"%(size),l=2)
        size=(1024**3)/(1000**3)
    return size

def _calc_size(size):
    size=size.strip().upper()
    if size.endswith("GB"):
        size=float(size[0:-2])
    elif size.endswith("MB"):
        size=float(size[0:-2])/1000
    elif size.endswith("KB"):
        size=float(size[0:-2])/1000**2
    elif size.endswith("TB"):
        size=float(size[0:-2])*1000
    else:
        log("size format error: %s"%(size),l=2)
        size=(1024**3)/(1000**3)
    return size

def parse_torrent_info(table):
    """
        从北邮人的网页上获得种子信息
        决定下载哪个种子时会用到
    """
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
        torrent_info['file_size'] = _calc_size_byr(tds[6].text)
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

transmission_cmd='transmission-remote -n %s '%(transmission_user_pw)

def transmission_ls():
    """
        从 transmission 的命令输出中获得本地种子信息
        直接命令行 --ls 或者删除种子时会用到
        return: text_s is list of {'id': '153', 'done': '0%', 'size': '1GB', 'name': 'dadada'}
    """
    text=execCmd(transmission_cmd+'-l')
    text=text.split('\n')[1:-2] #去掉第一和最后两个（好像是标题啥的？）
    text_s=[]
    log("Collecting detail infos for existed seeds...",l=0)
    for t in tqdm(text,ncols=75,bar_format=bar_format):
        ts = t.split()
        torrent = {'id':ts[0],'done':ts[1],'name':ts[-1]}

        # 跳过不是北邮人的
        tracker_info=execCmd(transmission_cmd+"-t %s -it"%(torrent['id']))
        if any([("tracker.byr.cn" not in i and "tracker.byr.pt" not in i) for i in tracker_info.split("\n\n")]):
            continue

        detailed_info=execCmd(transmission_cmd+"-t %s -i"%(torrent['id'].strip("*")))
        try:
            # 跳过不在设置文件夹中的文件：那有可能是用户手动下的
            location_info=re.search("Location: (.+)",detailed_info).group(1)
            if not os.path.samefile(location_info,linux_download_path):
                continue

            # 获取作种时间
            #torrent['seed_time']=re.search("Seeding Time.+?([0-9]+) seconds",detailed_info)
            seed_t=re.search("Date added:(.+)",detailed_info) #Wed Jul 14 21:53:49 2021
            seed_t=time.strptime(seed_t.group(1).strip(),"%a %b %d %H:%M:%S %Y")
            seed_t=time.mktime(seed_t)
            torrent['seed_time']=(time.time()-seed_t)/86400 # in day

            # 种子大小
            torrent['size']=_calc_size(re.search("Total size:.+?\\((.+?)wanted\\)",detailed_info).group(1))

            # 做种比
            torrent['ratio']=re.search("Ratio: ([0-9\\.]+)",detailed_info)
            if torrent['ratio']:
                torrent['ratio']=float(torrent['ratio'].group(1))
            else:
                if "Ratio: None" in detailed_info:
                    torrent['ratio']=0.0
                else:
                    torrent['uploaded']=_calc_size(re.search("Uploaded: (.+?[B])",detailed_info).group(1))
                    torrent['ratio']=torrent['uploaded']/torrent['size']

            # 哈希: d897f7f91af135b6507c6e5c4995852ef3401319
            torrent['hash']=re.search("Hash: ([0-9a-f]+)",detailed_info).group(1)
            if len(torrent['hash'])!=40:
                log("Hash length incorret: %d %s\n%s"%(len(torrent['hash']),torrent['hash'],detailed_info),l=2)
        except Exception:
            log("parse transmission's ls failed:\n%s"%(detailed_info),l=3)
            continue
        text_s.append(torrent)
    return text_s

class AutoDown(ContextDecorator):
    def __init__(self):
        super(AutoDown,self).__init__()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        self.refresh()

        # 已经存在的种子的 seed_id, 不必须, 但可以根据它跳过一些不必要操作
        if os.path.exists(torrent_id_save_path):
            with open(torrent_id_save_path,'rb') as f:
                self.exist_torrent_ids=pickle.load(f)
        else:
            self.exist_torrent_ids=[]
        # 可能被移除的种子,由 remove_init 负责初始化
        self.rmable_seeds=None
        # 做种人数很少的列表, 由 remove 调用 get_seeding_nums 负责初始化
        self.seeding_nums=None
        # 已经存在的种子的详情
        self.local_torrents=transmission_ls()
        self.local_torrent_size=sum([i['size'] for i in self.local_torrents])
        # 本次运行大约要下这么大的文件
        self.remain_quota=max_torrent_size*(SIZE_RATIO/100.0)
        # 剩余容量(包含可能被删除的)
        self.remain_capacity=max_torrent_size

    def refresh(self):
        byrbt_cookies = load_cookie()
        self.cookie_jar = RequestsCookieJar()
        for k, v in byrbt_cookies.items():
            self.cookie_jar[k] = v

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

    def remove_init(self,print_flag=False):
        self.rmable_seeds=[]
        for i in self.local_torrents:
            if i['id'][-1]=="*": # 忽略未完成的 (后面有星号)
                continue
            if i['seed_time']<RM_PEOTECT_TIME:
                continue
            i['value']=i['ratio']/i['seed_time']
            i['deleted']=False
            self.rmable_seeds.append(i)

        rmable_size=sum([i['size'] for i in self.rmable_seeds])
        if rmable_size>max_torrent_size*(SIZE_RATIO/100.0)*5:
            # 删除每天做种率低的，做种率一样（通常因为都是0）删早的
            self.rmable_seeds.sort(key=lambda x: (x['value'],-x['seed_time']))
            self.rmable_avg_val=sum([i['value']*i['size'] for i in self.rmable_seeds])/rmable_size
        else:
            self.rmable_seeds=[]
            rmable_size=0
        self.remain_capacity=min(self.remain_capacity,max_torrent_size-self.local_torrent_size+rmable_size)

        if print_flag:
            log(["%.1f GB, %.2f day"%(i['value'],i['seed_time']) for i in self.rmable_seeds],l=0)
            log("rmable_size: %.2f, self.remain_capacity: %.2f"%(rmable_size,self.remain_capacity),l=0)
            log("self.rmable_avg_val: %.4f"%(self.rmable_avg_val),l=0)

    def get_seeding_nums(self,print_flag=False):
        """
            获取种子们还有几人在做种
            问题在于我不知道本地的种子的 id, 文件名也不一样, 大小也可能差 1 GB
            还需要在登陆时获得 userid
            可以通过比较 hash 确定种子
        """
        if 'user_id' not in globals():
            log("感谢您使用最新版脚本, 请将自己的 user_id 填入 config.py 以实现自动删除功能. 如何获取 user_id 以及具体的格式参见 config.example.py",l=2)
            sys.exit(1)
        log("正在初始化删除, 这可能需要一段时间",l=0)
        dict_re={}
        try:
            # https://byr.pt/getusertorrentlistajax.php?userid=311938&type=seeding
            seeding_url=get_url('getusertorrentlistajax.php?userid=%s&type=seeding'%(user_id))
            seeding_info=requests.get(seeding_url,cookies=self.cookie_jar,headers=self.headers)
            seeding_info=seeding_info.content.decode(seeding_info.encoding)
            seeding_info=BeautifulSoup(seeding_info,features='lxml')
            if seeding_info.table==None:
                log("北邮人上显示您现在没有任何做种, 请检查您的 user_id (%s) 和做种状态"%(user_id),l=2)
                return {}
            trs=[]
            for tr in seeding_info.table.find_all('tr',recursive=False)[1:]:
                tds=[i for i in tr.find_all('td',recursive=False)]
                tds[3]=tds[3].text.strip() # seeding number
                if not tds[3].isdecimal():
                    log("seeding num not decimal: %s\n%s"%(tds[3],tr.prettify()),l=2)
                if tds[3]=='1':
                    trs.append(tds)
            for tds in tqdm(trs,ncols=75,bar_format=bar_format):
                try:
                    time.sleep(0.5) #不请求太频繁是爬虫的美德
                    seed_detail=get_url(tds[1].a['href']) #details.php?id=317580&hit=1
                    seed_detail=requests.get(seed_detail,cookies=self.cookie_jar,headers=self.headers)
                    seed_detail=seed_detail.content.decode(seed_detail.encoding)
                    seed_detail=BeautifulSoup(seed_detail,features='lxml')
                    seed_detail=seed_detail.text
                    seed_hash=re.search("Hash码: ([0-9a-f]+)",seed_detail)
                    seed_hash=seed_hash.group(1)
                    if len(seed_hash)!=40:
                        log("seed_hash len incorrect? %s\n%s"%(seed_hash,tds[1]),l=2)
                    dict_re[seed_hash]=int(tds[3])
                except Exception:
                    log("error while getting seed hash",l=3)
        except Exception:
            log("error while getting seed number",l=3)
        if print_flag:
            log(dict_re,l=0)
            log("len(seeding_nums): %d"%(len(dict_re)),l=0)
        return dict_re

    def remove(self,target_size,neo_value):
        # 用于忽略我是唯一做种人的
        if self.seeding_nums==None:
            self.seeding_nums=self.get_seeding_nums()

        del_size=0
        for rm_info in self.rmable_seeds:
            if rm_info['deleted']:
                continue
            ucb=UNFAITHFULNESS*math.sqrt(math.log(rm_info['seed_time'])/rm_info['seed_time'])
            if neo_value+self.rmable_avg_val*ucb<rm_info['value']:
                continue
            if rm_info['hash'] in self.seeding_nums:
                log("本应删除但我是最后一个做种者了: %s"%(rm_info))
                continue

            log("正在删除 %s"%(rm_info,))
            res=execCmd(transmission_cmd+'-t %s --remove-and-delete'%(rm_info['id'],))
            if "success" not in res:
                log('删除失败：%s'%(res),l=2)
                continue
            time.sleep(0.5+rm_info['size']*0.5) # 等一会儿，等它删完
            if os.path.exists(os.path.join(download_path,rm_info['name'])):
                log('删除成功，但文件还在，您自己看看吧：\n%s'%(res),l=2)
                continue

            rm_info['deleted']=True
            del_size+=rm_info['size']
            if del_size>target_size:
                break
        self.local_torrent_size-=del_size
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
            self.exist_torrent_ids.append(torrent_id)
            return False

        with open(torrent_file_path, 'wb') as f:
            f.write(torrent.content)
        time.sleep(0.5)

        cmd_str = transmission_cmd+'-a "%s" -w %s'%(torrent_file_path,download_path)
        cmd_rt = execCmd(cmd_str)

        if "success" in cmd_rt:
            # 如果成功，输出是
            # localhost:9091/transmission/rpc/ responded: "success"
            self.exist_torrent_ids.append(torrent_id)
            log("添加种子文件至 Transmisson 成功")
            return True
        else:
            # 已知的失败原因
            # Error: invalid or corrupt torrent file
            log("添加种子文件至 Transmisson 失败！\n%s"%(cmd_rt),l=2)
            os.remove(torrent_file_path)
            return False

    def download_many(self,torrent_infos):
        # 认为值得下载的种子
        ok_infos=[]
        for i in torrent_infos:
            if i['seed_id'] in self.exist_torrent_ids:
                continue
            if i['seeding']<=0 or i['finished']<=0:
                continue

            # 计算种子的价值, i.e. 平均每天上传率可以增加多少
            # 基本公式是 i['value']=i['finished']/(i['live_time']*i['seeding'])
            # 下载中(downloading)虽然我赶不上上传, 但是说明种子很火, 所以我觉得比已完成(finished)更重要, 值得乘个 buff
            # live_time 是以天为单位的, 加二是避免除零错误和更倾向旧种子
            i['value']=(i['finished']+i['downloading']*1.5)/((i['live_time']+2.0)*(i['seeding']+i['downloading']+1))
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
        # 按价值排序
        ok_infos.sort(key=lambda x:x['value'],reverse=True)
        for ii,i in enumerate(ok_infos):
            if i['file_size']>self.remain_capacity:
                continue
            pretty_info="{seed_id: %s, file_size: %.3f, seeding: %d, downloading: %d, finished: %d, live_time: %.2f, value: %.4f, cat: %s, tag: %s, title: %s, sub_title: %s}"\
                        %(i['seed_id'],i['file_size'],i['seeding'],i['downloading'],i['finished'],i['live_time'],i['value'],i['cat'],i['tag'],i['title'],i['sub_title'])
            log('将要下载 #%d %s'%(ii,pretty_info))

            # 如果种子超大了, 需要执行一下清理
            if self.local_torrent_size+i['file_size']>max_torrent_size:
                if self.rmable_seeds==None:
                    log("磁盘空间不足 (%.3f GB)，将执行自动清理"%(self.local_torrent_size))
                    self.remove_init()
                    if i['file_size']>self.remain_capacity:
                        log("最大可能腾出 %.3f GB 空间, 小于此种子的 %.3f GB, 直接跳过"%(self.remain_capacity,i['file_size']))
                        continue
                # 想要移除总计这么大的种子
                target_size=self.local_torrent_size+i['file_size']-max_torrent_size
                # 真正被移除了的种子
                removed_size=self.remove(target_size,i['value'])
                if removed_size<target_size:
                    log("清理磁盘失败，跳过此种子")
                    self.remain_capacity=min(self.remain_capacity,i['file_size'])
                    continue

            # 真正的下载只需要一行
            if self.download_one(i['seed_id']):
                self.local_torrent_size+=i['file_size']
                self.remain_quota-=i['file_size']
                self.remain_capacity-=i['file_size']
            # 如果已经达到了一次要下的大小
            if self.remain_quota<=0:
                #log("reach remain_size (%.2f), quit"%(self.remain_quota))
                break
        return len(ok_infos)

    def scan_one_page(self,page):
        if page==0:
            url=get_url("torrents.php")
        else:
            url=get_url("torrents.php?inclbookmarked=0&pktype=0&incldead=0&spstate=0&page=%d"%(page))
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
        num_ok=0
        for i,j in [(0,1),(1,3),(3,5)]:
            num_ok+=self.scan_many_pages(CHECK_PAGE_NUM*i,CHECK_PAGE_NUM*j)
            if num_ok>CHECK_PAGE_NUM:
                break
            if self.remain_quota<=0:
                break

        with open(torrent_id_save_path,'wb') as f:
            self.exist_torrent_ids=pickle.dump(self.exist_torrent_ids[-SEED_ID_KEEP_NUM:],f)

    def ls():
        exist_seeds=transmission_ls()
        torrent_size=sum([i['size'] for i in exist_seeds])
        log("There are now %d seeds with total size %.3f GB (after fully downloaded)."%(len(exist_seeds),torrent_size))
        for i in exist_seeds:
            i['value']=i['ratio']/i['seed_time']
        tot_upload=sum([i['size']*i['ratio'] for i in exist_seeds])
        avg_ratio=sum([i['value']*i['size'] for i in exist_seeds])/torrent_size if torrent_size>0 else float('nan')
        log("Total upload: %.1f GB. Average value: %.2f (1/day)"%(tot_upload,avg_ratio))
        exist_seeds.sort(key=lambda x:x['seed_time'],reverse=False)
        exist_seeds.sort(key=lambda x:x['value'],reverse=True)
        pretty_text=["\t  id value   ratio stime size(GB) name",]
        pretty_text+=[
                "\t%4d %5.2f/d %5.1f %5.1f %6.1f   %s"%\
                (int(i['id']),i['ratio']/i['seed_time'],i['ratio'],i['seed_time'],i['size'],
                    (i['name'].encode('utf-8')[0:35]).decode())
            for i in exist_seeds]
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
        log(HELP_TEXT,l=0)
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
    # 以下是用于调试的选项
    elif action_str.endswith('snum'):
        AutoDown().get_seeding_nums(print_flag=True)
    elif action_str.endswith('rm'):
        AutoDown().remove_init(print_flag=True)
    else:
        log('invalid argument')
        log(HELP_TEXT,l=0)
