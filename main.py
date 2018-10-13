import os
from pica import PicaUser
from progressbar import progressbar


def getUser():
    if os.path.exists('token.txt'):
        with open('token.txt', 'r') as f:
            token = f.read()
        user = PicaUser(token)
    else:
        user = PicaUser()
        user.signin(input('用户名: '), input('密码: '))
        with open('token.txt', 'w') as f:
            f.write(user.token)
    return user


if __name__ == "__main__":
    user = getUser()

    # 下载搜索关键词
    key, page = '', 1
    for comic in user.search(key, page):
        user.downloadComic(comic, wrap=progressbar)

    # 下载整个分类的一页
    ctg = ''
    for comic in user.getCategoryPage(ctg, page=1):
        user.downloadComic(comic, wrap=progressbar)
