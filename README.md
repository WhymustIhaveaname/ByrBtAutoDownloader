# brybt_bot

**上一个作者 [lipssmycode/byrbt_bot](https://github.com/lipssmycode/byrbt_bot) 不强调这个机器人会删除文件，一上来连警告都没有就把我1个T的文件给删了！！！
而且原来仓库代码质量低、README 英文和汉字之间没空格、issue 没人理，我决定放弃原来的仓库，慢慢重写全部代码。**

- [x] 更新 requirements.txt、README
- [x] 移动配置至 config.py，与主要逻辑分离
- [x] 重写 spaghetti codes、解决代码复用低的问题、lipssmycode 不会用一行 list 的语法导致程序变长和可读性降低
- [x] 删除文件的问题：只会删除 linux_download_path 下并且所有 tracker 都是北邮人的文件
- [x] 改为限制总大小而不是文件数
- [x] 降低请求失败重试次数至3或者2，失败两三次就得了，默认是 5 太烦人了
- [x] 清除无用命令，那些可以用网页控制台的命令有必要再写一遍吗？而且好多代码竟然不是复用的！
- [x] 重命名部分函数，原来所有函数都是 get 开头，改成更具有意义的 select、parse 等
- [x] 增加日志机制
- [x] 重写下载种子的逻辑：按种子平均每天增加作种率期望排序，不同的 free 加不同的 buff，下最受欢迎的
- [x] 重写空间满时删除种子的逻辑：按我做种以来平均每天的上传比排序，使用 MCTS 中的 UCB 算法删没人要的
- [x] 获取更多页的种子而不仅仅是第一页
- [x] 删除没用的神经网络文件
- [x] 解决种子下载名字不对的问题：byr 的 headers 是用 iso8859-1 编码的，requests 会试图用 utf-8 解码，导致很多乱码。
可怜的 lipssmycode 并不能解决这个问题，只能把乱码都忽略，最后就出现了一堆点组成的文件名——因为只有点不会被忽略。
- [ ] 进行广泛的测试

**更新：我发现上一个作者 lipssmycode 基本上就是个贼。
主体代码都来自 [Jason2031/byrbt_bot](https://github.com/Jason2031/byrbt_bot)，
她隐藏 fork 痕迹，淡化原仓库的贡献，甚至最后的鸣谢都没有带原作者 Jason2031 的名字。
还把协议 从 GPL 换成了 MIT，这都是非常不道德的。
最让我生气的还是她的代码质量太低了，读她的代码就像手榴弹在大脑中爆炸一样上头。**

### Features

- [x] 支持识别验证码登录（感谢 [bumzy/decaptcha](https://github.com/bumzy/decaptcha) 项目）
- [x] 支持下载种子(感谢 [Jason2031/byrbt_bot](https://github.com/Jason2031/byrbt_bot) 项目)
- [x] 支持自动寻找合适的种子：下载最能提高做种率的（最受大家欢迎且做种人数不那么多的）种子
- [x] 支持自动删除旧种子，下载新种子：使用 UCB 算法决定何时换新种子
- [x] 支持使用 Transmission Web 管理种子
- [x] 有效压榨硬盘空间：在不超过 max_torrent_size 的情况下把最后一点缝隙挤满

<a href="https://bt.byr.cn/promotionlink.php?key=2fa9cf9b8c919fd2c6f72076f6e2ccde"><img src="https://bt.byr.cn/pic/prolink.png" alt="这张北邮人的图片教育网v6才能加载出来"></a>

<table>
    <tr>
        <th width=50%><img src="https://raw.githubusercontent.com/WhymustIhaveaname/ByrBtAutoDownloader/main/images/terminal.png"/></th>
        <th width=50%><img src="https://raw.githubusercontent.com/WhymustIhaveaname/ByrBtAutoDownloader/main/images/web.png"/></th>
    </tr>
    <tr>
        <th>命令行输出 (又改了几版现在更好看了)</th>
        <th>Transmission Web 管理界面</th>
    </tr>
</table>

### Usage

* 安装相应依赖包

   ```shell
   python3 -m pip install -r requirements.txt
   ```

* 安装 Transmission

   [Transmission 搭建笔记](https://github.com/WhymustIhaveaname/Transmission-Block-Xunlei/blob/main/%E6%90%AD%E5%BB%BA%E7%AC%94%E8%AE%B0.md)

* 复制 config-example.py 至 config.py，并更改以下信息。

    **注意 download_path 不要填自己正在用的文件夹，里面的文件可能会被删除！**

    ```python
    username = '用户名'
    passwd = '密码'
    transmission_user_pw = 'user:passwd'  # transmission 的用户名和密码，按照格式填入
    linux_download_path = '<path_to_download_dir>'  # 下载路径
    max_torrent_size = 512  # 最大文件大小，GB
    ```

* 启动！

   ```shell
   python3 byrbt.py --help
   python3 byrbt.py --main
   ```

* 使用 crontab 重复执行脚本

    我的 crontab 是

    ```
    25 */6 * * * cd /home/dAlembert/byrbt_bot && ./byrbt.py --main
    ```

    意思是整除 6 的小时的第 25 分钟执行。
    每次执行大约会换掉 max_torrent_size 1% 的东西，所以建议一天执行四次，这样就是一个月换一遍，完美。
    更多信息见 [使用crontab重复执行脚本](https://github.com/WhymustIhaveaname/TsinghuaTunet#%E4%BD%BF%E7%94%A8crontab%E9%87%8D%E5%A4%8D%E6%89%A7%E8%A1%8C%E8%84%9A%E6%9C%AC)。

### Acknowledgements

* [lipssmycode/byrbt_bot](https://github.com/lipssmycode/byrbt_bot)
~~虽然她代码质量很低并且删了我1个T文件，但是爬虫的部分的确节约了我的时间。~~
lipssmycode 基本上就是个贼。
主体代码都来自 [Jason2031](https://github.com/Jason2031)，
她隐藏 fork 痕迹，淡化原仓库的贡献，甚至最后的鸣谢都没有带原作者 Jason2031 的名字。
* [Jason2031/byrbt_bot](https://github.com/Jason2031/byrbt_bot)
* [bumzy/decaptcha](https://github.com/bumzy/decaptcha)
