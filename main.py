import os
from pica import PicaUser
from progressbar import progressbar

import argparse


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

    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, choices=['search', 'category'])
    parser.add_argument('keyword', type=str)
    parser.add_argument('-n', type=int, default=1, help='下载数量')

    ns = parser.parse_args()

    if ns.command == 'search':
        for comic in user.search(ns.keyword, 1)[0:ns.n]:
            user.downloadComic(comic, wrap=progressbar)
    elif ns.command == 'category':
        comics = user.getCategoryPage(ns.keyword, page=1)
        if not comics:
            print(f'可选分类: {user.categories()}')
            exit(1)
        for comic in comics[0:ns.n]:
            user.downloadComic(comic, wrap=progressbar)
    else:
        raise RuntimeError
