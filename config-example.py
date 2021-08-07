# ##################需要配置的变量###################
username = '用户名'
passwd = '密码'
transmission_user_pw = 'user:passwd'  # transmission的用户名和密码，按照格式填入
linux_download_path = '<path_to_download_dir>'  # 下载路径
max_torrent_size = 512  # 最大文件大小，GB

# 程序运行的参数，我觉得调得挺好的了，但也可以自己改
CHECK_PAGE_NUM = 3          # 检查种子页的前多少页，一页大约需要3秒
UNFAITHFULNESS = -2.0       # 正倾向于换新种子，负倾向于保留旧种子
                            # 换言之，负关注做种比，正关注上传量
FREE_WT = 1.0               # 对 free、30down、50down 的 buff 大小
                            # 换言之，越大越关注做种比，越小越关注上传量

COST_RECOVERY_TIME = 7      # 几天之内不能回本（做种比达到1）的种子是绝不会下的
                            # 一周（7.0）已经是很松的条件了
RM_PEOTECT_TIME = 14        # 几天之内的种子不会被删除

LARGE_FILE_DEBUFF = ((60,0.1),(15,1.0))         # 大文件的 debuff，由点指定的分段线性函数
SMALL_FILE_DEBUFF = (( 0,0.0),( 2,1.0))         # 小文件的 debuff
SEED_NUM_DEBUFF = ((12,0.5),(6,0.6),(5,1.0))    # 有很多人做种时的 debuff

SEED_ID_KEEP_NUM = max_torrent_size//5          # 不检查最近的这么多种子，大约1T200个即可

# 程序临时文件存储路径
decaptcha_model = 'captcha_classifier.pkl'  # 验证码识别模型
cookies_save_path = 'ByrbtCookies.pickle'  # cookies保存路径
torrent_id_save_path = 'ByrbtTorrentIDs.pickle' # 存一些临时变量


assert all([LARGE_FILE_DEBUFF[i][0]>LARGE_FILE_DEBUFF[i+1][0] for i in range(len(LARGE_FILE_DEBUFF)-1)])
assert all([SMALL_FILE_DEBUFF[i][0]<SMALL_FILE_DEBUFF[i+1][0] for i in range(len(SMALL_FILE_DEBUFF)-1)])
assert all([SEED_NUM_DEBUFF[i][0]>SEED_NUM_DEBUFF[i+1][0] for i in range(len(SEED_NUM_DEBUFF)-1)])
