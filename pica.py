import hashlib
import hmac
import json
import time
import uuid
import os
import logging
import functools
from typing import List
from multiprocessing.dummy import Pool

import requests
import progressbar


SECRET_KEY = "~n}$S9$lGts=U)8zfL/R.PM9;4[3|@/CEsl~Kk!7?BYZ:BAa5zkkRBL7r|1/*Cr"
BASE_URL = "https://picaapi.picacomic.com/"

S_UUID = str(uuid.uuid4()).replace("-", "")
API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"


class PicaObject(object):
    def __init__(self, VO):
        self._id = VO['_id']
        self.title = VO['title']


class Comic(PicaObject):
    def __init__(self, VO):
        super().__init__(VO)

        self.pagesCount = VO['pagesCount']
        self.epsCount = VO['epsCount']
        self.thumb = VO['thumb']['fileServer'] + \
            '/static/' + VO['thumb']['path']
        self.thumbOriginalName = VO['thumb']['originalName']

    def __repr__(self):
        return f'<Comic {self.title} {self.epsCount} eps {self.pagesCount} pages>'


class ComicEpisode(PicaObject):
    def __init__(self, VO):
        super().__init__(VO)

        self.order = VO['order']

    def __repr__(self):
        return f'<ComicEpisode No.{self.order} {self.title}>'


def requirLogin(func):
    @functools.wraps(func)
    def newfunc(self, *args, **kws):
        if not self.token:
            raise RuntimeError('未登录!')
        return func(self, *args, **kws)
    return newfunc


class ResourceNotFound(RuntimeError):
    pass


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
        self.getLogger()

    def getLogger(self, debug=False):
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False
        formatter = logging.Formatter(
            fmt=f'(%(asctime)s) - [%(levelname)s] %(message)s',
            datefmt='%y-%m-%d %H:%M:%S')

        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG if debug else logging.INFO)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        handler = logging.FileHandler('pica.log', encoding='utf8')
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.logger.setLevel(logging.DEBUG)

    # 网络部分
    @staticmethod
    def _signature(url, ts, method):
        '计算签名'
        raw = url.lstrip('/') + str(ts) + S_UUID + method + API_KEY
        raw = raw.lower()
        hc = hmac.new(SECRET_KEY.encode(), digestmod=hashlib.sha256)
        hc.update(raw.encode())
        return hc.hexdigest()

    def do(self, method, url, data):
        self.logger.debug(f'{method} {url}, data={data}')
        ts = int(time.time())
        self.headers["signature"] = self._signature(url, ts, method)
        self.headers["time"] = str(ts)

        func = {
            'GET': requests.get,
            'POST': requests.post
        }[method]

        res = func(BASE_URL + url,
                   data=data, headers=self.headers,
                   proxies=self.proxies)

        # 状态码判断
        if not res.status_code == 200:
            raise RuntimeError(res.json()['message'])

        # 判断 404
        try:
            # 404 Error 返回 200 状态码
            if '404 Not Found' in res.text:
                raise ResourceNotFound('404 Error')
        except ResourceNotFound:  # 404
            raise
        except Exception:  # 无法解码
            pass

        # 尝试 json 解析
        try:
            data = res.json()
            return data
        except json.JSONDecodeError:  # 返回的不是 json
            raise RuntimeError(res.content)

    def post(self, url, data):
        return self.do('POST', url, data)

    def get(self, url, data=None):
        return self.do('GET', url, data)

    # 接口部分
    def signin(self, email, pwd):
        self.logger.debug(f'用户 {email} 登陆')
        body = {"email": email, "password": pwd}
        res = self.post("/auth/sign-in", json.dumps(body))
        self.token = res['data']['token']
        self.headers["authorization"] = self.token
        self.logger.info('登陆成功')
        return

    @requirLogin
    def categories(self) -> List[str]:
        self.logger.debug('获取分类')
        res = self.get('/categories')
        categories = res['data']['categories']
        self.logger.debug(f'分类: {categories}')
        return [item['title'] for item in categories]

    @requirLogin
    def getCategoryPage(self, ctgName, page=1) -> List[Comic]:
        self.logger.debug(f'获取分类 {ctgName} 第 {page} 页')
        url = '/comics?page={page}&c={ctgName}&s=ua'.format(
            ctgName=ctgName, page=page)
        res = self.get(url)
        docs = res['data']['comics']['docs']
        return [Comic(doc) for doc in docs]

    @requirLogin
    def getComicWithId(self, comicID) -> Comic:
        self.logger.debug(f'获取漫画 ID {comicID} 信息')
        url = f'/comics/{comicID}'
        res = self.get(url)
        return Comic(res['data']['comic'])

    @requirLogin
    def getComicEps(self, comic: Comic) -> List[ComicEpisode]:
        self.logger.debug(f'获取漫画 {comic} 的分话信息')
        url = '/comics/{comicID}/eps'.format(comicID=comic._id)
        res = self.get(url)
        eps = res['data']['eps']['docs']
        return [ComicEpisode(ep) for ep in eps]

    @requirLogin
    def downloadComic(self, comic: Comic, path='download', wrap=None, threaded=True):
        self.logger.debug(f'下载漫画 {comic}, 路径 {path}, 多线程 {threaded}')

        if not os.path.exists(path):
            os.mkdir(path)
        path = os.path.join(path, comic.title)
        if not os.path.exists(path):
            os.mkdir(path)

        self.logger.info(f'开始下载漫画 {comic}')
        eps = sorted(self.getComicEps(comic), key=lambda i: i.order)

        if len(eps) > 1:
            for index, ep in enumerate(eps):
                self.logger.info(
                    f'[{index+1}/{len(eps)}] 正在下载 {comic} 分话 {ep}')
                pos = os.path.join(path, str(ep.title))
                self.downloadEpisode(
                    comic, ep.order,
                    pos=pos, wrap=wrap, threaded=threaded)
        else:
            self.downloadEpisode(
                comic, eps[0].order,
                pos=path, wrap=wrap, threaded=threaded)
        self.logger.info(f'漫画 {comic} 下载完毕')

    @requirLogin
    def downloadEpisode(self, comic: Comic, order=1, pos='download', wrap=None, threaded=True):
        self.logger.debug(
            f'下载整话，漫画 {comic} 第 {order} 话，下载位置 {pos}，多线程 {threaded}')
        assert order <= comic.epsCount
        pages = self.getComicEpisodePages(comic, order)

        if not os.path.exists(pos):
            os.mkdir(pos)

        def _do(page):
            media = page['media']
            fn = os.path.join(pos, media['originalName'])
            if os.path.exists(fn):
                return

            data = self._getSinglePage(media['fileServer'],
                                       media['path'])
            with open(fn + '.tmp', 'wb') as f:
                f.write(data)
            os.rename(fn + '.tmp', fn)

        if not threaded:
            pages = wrap(pages) if wrap else pages
            for page in pages:
                _do(page)
        else:
            if wrap:
                bar = progressbar.ProgressBar(max_value=len(pages))

                def __do(page):
                    _do(page)
                    bar.value += 1
                    bar.update(bar.value)

                bar.start()
                with Pool() as pool:
                    pool.map(__do, pages)
                bar.finish()
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

        self.logger.debug(f'下载单页 {url}')
        res = requests.get(url,
                           headers=self.headers,
                           proxies=self.proxies)
        try:
            text = res.text
            if '404 Not Found' in text:
                self.logger.warning('资源 404 啦')
                raise ResourceNotFound('资源 404 啦')
        except ResourceNotFound:
            raise
        except Exception:
            pass

        if res.status_code != 200:
            raise RuntimeError(res.json())

        return res.content

    @requirLogin
    def getComicEpisodePages(self, comic, order):
        self.logger.debug(f'获取漫画 {comic} 第 {order} 话的图片信息')
        docs = []
        page = 1
        while True:
            data = self._getComicEpisodePage(comic, order, page)
            assert data['page'] == page
            docs += data['docs']
            if page == data['pages']:
                break
            else:
                page += 1

        assert data['total'] == len(docs)
        self.logger.debug(f'共计 {len(docs)} 图片')
        return docs

    @requirLogin
    def _getComicEpisodePage(self, comic, order, page=1):
        self.logger.debug(f'获取漫画 {comic} 第 {order} 话 第 {page} 页信息')
        url = f'/comics/{comic._id}/order/{order}/pages?page={page}'
        res = self.get(url)
        pages = res['data']['pages']
        self.logger.debug(f'本页共计 {len(pages)} 张图片')
        return pages

    @requirLogin
    def search(self, key, page=1) -> List[Comic]:
        self.logger.debug(f'搜索关键词 {key} 第 {page} 页')
        from urllib.parse import urlencode
        url = "/comics/search?" + urlencode({
            'q': key,
            'page': page
        })
        res = self.get(url)['data']['comics']['docs']
        return [Comic(item) for item in res]
