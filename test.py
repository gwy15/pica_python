import unittest
import logging

import pica


class PicaTest(unittest.TestCase):
    def setUp(self):
        with open('token.txt', 'r') as f:
            token = f.read()
        self.user = pica.PicaUser(token)
        self.user.logger.setLevel(logging.WARNING)

    def getComic(self):
        comic = pica.Comic({
            '_id': '5bc16f4925bd2443c61a0077',
            'title': 'test',
            'pagesCount': 1,
            'epsCount': 1,
            'thumb': {
                'fileServer': 'https://localhost',
                'path': '1.jpg',
                'originalName': '1.jpg'
            }
        })
        return comic

    def testCategories(self):
        self.assertIn('Cosplay', self.user.categories())

    def testCategoryPage(self):
        comics = self.user.getCategoryPage('Cosplay', 1)
        for comic in comics:
            self.assertIsInstance(comic, pica.Comic)

    def testGetComicEps(self):
        comic = self.getComic()
        eps = self.user.getComicEps(comic)
        self.assertEqual(len(eps), 1)
        ep = eps[0]
        self.assertIsInstance(ep, pica.ComicEpisode)
        self.assertEqual(ep.order, 1)
        self.assertEqual(ep.title, '第1集')

    def testDownloadComic(self):
        comic = self.user.getComicWithId('5b92203a1d74c17aef2f3405')
        self.assertIsInstance(comic, pica.Comic)
        self.assertEqual(comic.epsCount, 1)
        self.assertEqual(comic.pagesCount, 12)

        self.user.downloadComic(comic, path='test')

    def testSearch(self):
        comics = self.user.search('Hana Bunny')
        self.assertEqual(len(comics), 1)
        comic = comics[0]
        self.assertIsInstance(comic, pica.Comic)
        self.assertEqual(comic.epsCount, 1)
        self.assertEqual(comic.pagesCount, 12)


if __name__ == '__main__':
    unittest.main()
