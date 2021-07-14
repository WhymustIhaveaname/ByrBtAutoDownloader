# ##################需要配置的变量###################
username = '用户名'
passwd = '密码'
transmission_user_pw = 'user:passwd'  # transmission的用户名和密码，按照格式填入
linux_download_path = '<path_to_download_dir>'  # 下载路径
max_torrent_size = 512  # 最大文件大小，GB
check_page = 3   # 检查种子页前多少页

# ##################################################
decaptcha_model = 'captcha_classifier.pkl'  # 验证码识别模型
cookies_save_path = 'ByrbtCookies.pickle'  # cookies保存路径
torrent_id_save_path = 'ByrbtTorrentIDs.pickle' # 存一些临时变量