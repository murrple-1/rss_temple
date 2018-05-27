import importlib

from django.test import TestCase
from django.http.request import HttpRequest
from django.http.response import HttpResponse

import api.middleware.cors as cors

class CORSTestCase(TestCase):
    def test_allow_star(self):
        with self.settings(CORS_ALLOW_ORIGINS='*',
            CORS_ALLOW_METHODS='GET,POST,OPTIONS',
            CORS_ALLOW_HEADERS='Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization',
            CORS_EXPOSE_HEADERS='Date'):
            importlib.reload(cors)
            middleware = cors.CORSMiddleware(lambda request: HttpResponse('test content'))

            request = HttpRequest()
            request.META['HTTP_ORIGIN'] = 'http://example.com'

            response = middleware(request)

            self.assertEqual(response.content, b'test content')
            self.assertEqual(response['Access-Control-Allow-Origin'], '*')
            self.assertEqual(response['Access-Control-Allow-Methods'], 'GET,POST,OPTIONS')
            self.assertEqual(response['Access-Control-Allow-Headers'], 'Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization')
            self.assertEqual(response['Access-Control-Expose-Headers'], 'Date')

    def test_allow_str(self):
        with self.settings(CORS_ALLOW_ORIGINS='http://example.com',
            CORS_ALLOW_METHODS='GET,POST,OPTIONS',
            CORS_ALLOW_HEADERS='Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization',
            CORS_EXPOSE_HEADERS='Date'):
            importlib.reload(cors)
            middleware = cors.CORSMiddleware(lambda request: HttpResponse('test content'))

            request = HttpRequest()
            request.META['HTTP_ORIGIN'] = 'http://example.com'

            response = middleware(request)

            self.assertEqual(response.content, b'test content')
            self.assertEqual(response['Access-Control-Allow-Origin'], 'http://example.com')
            self.assertEqual(response['Access-Control-Allow-Methods'], 'GET,POST,OPTIONS')
            self.assertEqual(response['Access-Control-Allow-Headers'], 'Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization')
            self.assertEqual(response['Access-Control-Expose-Headers'], 'Date')

    def test_allow_list(self):
        with self.settings(CORS_ALLOW_ORIGINS=['http://example.com', 'http://test.com'],
            CORS_ALLOW_METHODS='GET,POST,OPTIONS',
            CORS_ALLOW_HEADERS='Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization',
            CORS_EXPOSE_HEADERS='Date'):
            importlib.reload(cors)
            middleware = cors.CORSMiddleware(lambda request: HttpResponse('test content'))

            request = HttpRequest()
            request.META['HTTP_ORIGIN'] = 'http://example.com'

            response = middleware(request)

            self.assertEqual(response.content, b'test content')
            self.assertEqual(response['Access-Control-Allow-Origin'], 'http://example.com')
            self.assertEqual(response['Access-Control-Allow-Methods'], 'GET,POST,OPTIONS')
            self.assertEqual(response['Access-Control-Allow-Headers'], 'Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization')
            self.assertEqual(response['Access-Control-Expose-Headers'], 'Date')

    def test_options(self):
        with self.settings(CORS_ALLOW_ORIGINS='*',
            CORS_ALLOW_METHODS='GET,POST,OPTIONS',
            CORS_ALLOW_HEADERS='Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization',
            CORS_EXPOSE_HEADERS='Date'):
            importlib.reload(cors)
            middleware = cors.CORSMiddleware(lambda request: HttpResponse('test content'))

            request = HttpRequest()
            request.method = 'OPTIONS'
            request.META['HTTP_ORIGIN'] = 'http://example.com'

            response = middleware(request)

            self.assertEqual(response.content, b'')
            self.assertEqual(response['Access-Control-Allow-Origin'], '*')
            self.assertEqual(response['Access-Control-Allow-Methods'], 'GET,POST,OPTIONS')
            self.assertEqual(response['Access-Control-Allow-Headers'], 'Pragma,Cache-Control,Content-Type,If-Modified-Since,Authorization')
            self.assertEqual(response['Access-Control-Expose-Headers'], 'Date')
