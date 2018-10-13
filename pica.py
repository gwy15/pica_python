import hashlib
import hmac
import json
import time
import uuid
import requests
import os
import functools
from multiprocessing.dummy import Pool

proxies = None
if proxies:
    requests.packages.urllib3.disable_warnings()

SECRET_KEY = "~n}$S9$lGts=U)8zfL/R.PM9;4[3|@/CEsl~Kk!7?BYZ:BAa5zkkRBL7r|1/*Cr"
BASE_URL = "https://picaapi.picacomic.com/"

S_UUID = str(uuid.uuid4()).replace("-", "")
API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"


def requirLogin(func):
    @functools.wraps(func)
    def newfunc(self, *args, **kws):
        if not self.token:
            raise RuntimeError('未登录!')
        return func(self, *args, **kws)
    return newfunc


class PicaUser():
    def __init__(self, token=None, proxies=None):
        self.headers = {
            "api-key": API_KEY,
            "accept": "application/vnd.picacomic.com.v1+json",
            "app-channel": "3",
            "time": "0",
            "nonce": S_UUID,
            "signature": "0",
            "app-version": "2.1.0.4",
            "app-uuid": "418e56fb-60fb-352b-8fca-c6e8f0737ce6",
            "app-platform": "android",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/3.8.1",
            "app-build-version": "39"}
        self.token = token
        self.headers["authorization"] = token
        self.proxies = proxies

    # 网络部分
    @staticmethod
    def _signature(url, ts, method):
        # 计算签名
        raw = url.lstrip('/') + str(ts) + S_UUID + method + API_KEY
        raw = raw.lower()
        hc = hmac.new(SECRET_KEY.encode(), digestmod=hashlib.sha256)
        hc.update(raw.encode())
        return hc.hexdigest()

    def do(self, method, url, data=None):
        ts = int(time.time())
        self.headers["signature"] = self._signature(url, ts, method)
        self.headers["time"] = str(ts)

        func = {
            'GET': requests.get,
            'POST': requests.post
        }[method]

        return func(BASE_URL + url,
                    data=data, headers=self.headers,
                    proxies=self.proxies)

    def post(self, url, json):
        return self.do('POST', url, json)

    def get(self, url, data=None):
        return self.do('GET', url, data)

    # 接口部分
    @requirLogin
    def signin(self, email, pwd):
        '登陆'
        body = {"email": email, "password": pwd}
        res = self.post("/auth/sign-in", json.dumps(body)).json()
        self.token = res['data']['token']
        self.headers["authorization"] = self.token
        print('登陆成功')
        return

    @requirLogin
    def categories(self):
        '获取目录'
        res = self.get('/categories').json()
        return res['data']['categories']

    @requirLogin
    def getCategoryPage(self, ctgName, page):
        url = '/comics?page={page}&c={ctgName}&s=ua'.format(
            ctgName=ctgName, page=page)
        res = self.get(url).json()
        return res['data']['comics']['docs']

    @requirLogin
    def getComicWithId(self, comicId):
        url = '/comics/{comicId}'.format(comicId=comicId)
        res = self.get(url).json()
        comic = res['data']['comic']
        return comic

    @requirLogin
    def getComicEps(self, comicId):
        '获取话'
        url = '/comics/{comicId}/eps'.format(comicId=comicId)
        res = self.get(url).json()
        eps = res['data']['eps']
        docs = eps['docs']
        return docs

    @requirLogin
    def downloadComic(self, cid, path='download', wrap=None, threaded=True):
        comic = user.getComicWithId(cid)
        print('开始下载漫画 %s' % comic['title'])

        if not os.path.exists(path):
            os.mkdir(path)
        path = os.path.join(path, comic['title'])
        if not os.path.exists(path):
            os.mkdir(path)

        eps = sorted(user.getComicEps(comic['_id']), key=lambda i: i['order'])
        if len(eps) > 1:
            for index, ep in enumerate(eps):
                print('[%d/%d] 正在下载 %s 分话 %s' %
                      (index+1, len(eps), comic['title'], ep['title']))
                pos = os.path.join(path, str(ep['order']))
                user.downloadEpisode(
                    comic['_id'], ep['order'],
                    pos=pos, wrap=wrap, threaded=threaded)
        else:
            user.downloadEpisode(comic['_id'], eps[0]['order'],
                                 pos=path, wrap=wrap, threaded=threaded)
        print('漫画 %s 下载完毕' % comic['title'])

    @requirLogin
    def downloadEpisode(self, cid, order, pos='download', wrap=None, threaded=True):
        pages = self.getComicEpisodePages(cid, order)
        pages = wrap(pages) if wrap else pages

        if not os.path.exists(pos):
            os.mkdir(pos)

        def _do(page):
            media = page['media']
            data = user._getSinglePage(media['fileServer'],
                                       media['path'])
            with open(os.path.join(pos, media['originalName']), 'wb') as f:
                f.write(data)

        if threaded:
            for page in pages:
                _do(page)
        else:
            with Pool() as pool:
                pool.map(_do, pages)

    @requirLogin
    def _getSinglePage(self, filesever, path):
        '下载单页'
        url = filesever + "/static/" + path

        ts = int(time.time())
        self.headers["signature"] = self._signature(url, ts, 'GET')
        self.headers["time"] = str(ts)

        res = requests.get(url,
                           headers=self.headers,
                           proxies=self.proxies)

        return res.content

    @requirLogin
    def getComicEpisodePages(self, id, order):
        '获取总列表'
        docs = []
        page = 1
        while True:
            data = self._getComicEpisodePage(id, order, page)
            assert data['page'] == page
            docs += data['docs']
            if page == data['pages']:
                break
            else:
                page += 1

        assert data['total'] == len(docs)
        return docs

    @requirLogin
    def _getComicEpisodePage(self, id, order, page=1):
        '获取单页列表'
        url = '/comics/{comicId}/order/{order}/pages'.format(
            comicId=id, order=order)
        url += '?page={}'.format(page)
        res = self.get(url).json()
        return res['data']['pages']

    @requirLogin
    def search(self, key, page):
        from urllib.parse import urlencode
        url = "/comics/search?" + urlencode({
            'q': key,
            'page': page
        })
        res = self.get(url).json()
        return res['data']['comics']['docs']

