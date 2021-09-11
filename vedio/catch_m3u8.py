# -- coding: utf-8 --
import os
import re
import sys
import uuid

import requests
import argparse
from m3u8 import M3U8
import multiprocessing
import shutil
from vedio.util import getResponse, HEADERS, TIMEOUT

CRYPTO_ENABLE = True
try:
    from Crypto.Cipher import AES
except ImportError as e:
    CRYPTO_ENABLE = False
    print('Import Crypto error!')


def downloadTsFiles(ts_list, tmp_dir, process_id):
    cookies = None
    session = requests.Session()
    for i, ts_url in enumerate(ts_list):
        print('%d, download %s, index:%d/%d, %s' % (process_id, os.path.basename(tmp_dir), i, len(ts_list), ts_url))
        retry_times = 100
        tmp_file = os.path.join(tmp_dir, ts_url.rsplit('/', 1)[-1])
        if os.path.exists(tmp_file):
            continue

        while retry_times > 0:
            ret_sucess, cookies = downloadTs(ts_url, tmp_file, session, cookies)
            retry_times -= 1
            if ret_sucess:
                break


def downloadTs(ts_url, tmp_file, session, cookies=None):
    try:
        resp = session.get(
            ts_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            cookies=cookies,
        )
        if cookies is None:
            cookies = session.cookies

        with open(tmp_file, 'wb') as f:
            f.write(resp.content)
        return True, cookies
    except Exception as e:
        Warning('Error:%s' % str(e))
        return False, cookies
        # raise ConnectionError('Error:%s' % str(e))


def decryptFiles(ts_urls, tmp_dir, encrypt_method, key_str):
    key_bytes = bytes(key_str, 'utf-8')
    if 'AES' in encrypt_method:
        cryptor = AES.new(key_bytes, AES.MODE_CBC, None)
    else:
        raise NotImplementedError('%s has not implented yet!' % encrypt_method)

    for i, ts_url in enumerate(ts_urls):
        tmp_file = os.path.join(tmp_dir, ts_url.rsplit('/', 1)[-1])
        decrypt_file = os.path.join(tmp_dir, 'decrypt_' + ts_url.rsplit('/', 1)[-1])
        if not os.path.exists(tmp_file):
            raise FileNotFoundError('Some files fail to download, try again!')
        with open(tmp_file, 'rb') as f_encrypt:
            encrypt_content = f_encrypt.read()

        with open(decrypt_file, 'wb') as f:
            f.write(cryptor.decrypt(encrypt_content))


def downM3u8Video(url, out_dir, out_name, process_num):
    out_path = os.path.join(out_dir, out_name)
    tmp_dir = os.path.join(out_dir, os.path.splitext(os.path.basename(out_name))[0])
    if os.path.exists(out_path) and not os.path.exists(tmp_dir):
        # 该任务已完成下载
        print('Input name is existed:%s!' % out_name)
        return

    m3u8_info = M3U8(url)
    ts_len = len(m3u8_info.ts_urls)
    print('ts length:%d' % ts_len)

    if ts_len > 0:
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        process_list = []
        per_process_num = int(ts_len / process_num)

        # 启用多进程下载视频
        for i in range(process_num):
            id_start = i * per_process_num
            id_end = (i + 1) * per_process_num
            if i == process_num - 1:
                id_end = ts_len
            cur_process = multiprocessing.Process(
                target=downloadTsFiles, args=(m3u8_info.ts_urls[id_start:id_end], tmp_dir, i))
            cur_process.start()
            # search_ip(ip_prefix, database, table_name, ip_start, ip_end, i)
            process_list.append(cur_process)

        for process_item in process_list:
            process_item.join()

        # 若有加密，尝试解密文件
        if CRYPTO_ENABLE and m3u8_info.encrypt_method:
            print('encrypt method:%s' % m3u8_info.encrypt_method)
            print('key uri:%s' % m3u8_info.key_uri)
            key_str = getResponse(m3u8_info.key_uri)
            decryptFiles(m3u8_info.ts_urls, tmp_dir, m3u8_info.encrypt_method, key_str)

        print('Merging to one file:%s' % out_path)
        with open(out_path, 'wb') as f_out:
            for i, ts_url in enumerate(m3u8_info.ts_urls):
                tmp_file = os.path.join(tmp_dir, ts_url.rsplit('/', 1)[-1])
                decrypt_file = os.path.join(tmp_dir, 'decrypt_' + ts_url.rsplit('/', 1)[-1])
                dst_file = decrypt_file if CRYPTO_ENABLE and m3u8_info.encrypt_method is not None else tmp_file

                if not os.path.exists(dst_file):
                    print('Some files fail to download or decrypt, try again!')
                    return

                with open(dst_file, 'rb') as f:
                    f_out.write(f.read())

        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', type=str, help='')
    parser.add_argument('out_name', type=str, help='max pages number')
    parser.add_argument('name_index', type=int, help='the index of video')
    parser.add_argument('--process_num', type=int, default=8, help='max pages number')

    args = parser.parse_args()
    return args


M3U8_URL_REGEX = r'https:\\*/\\*/[\\\w\-_\.]+[\\\w\-\.,@?^=%&:/~\+#]*\.m3u8'
CHROME_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'}
# python catch_m3u8.py url 保存名称 起始序号
if __name__ == '__main__':
    urls = [
        'https://www.tkb800.life/view_video.html?batch=c9d3657c37e436713e2f068604de9573&u=480p_17083',




        ]

    for url in urls:
        r = requests.get(url, headers=CHROME_HEADERS)
        html = r.text

        matchs = re.findall(M3U8_URL_REGEX, html)
        if not matchs:
            print("获取m3db地址失败。")
            continue

        m3u8_url = matchs[0]
        m3u8_url = eval(repr(m3u8_url).replace('\\', ''))
        print("开始下载：%s" % m3u8_url)

        # args = parseArgs()
        # url = args.url
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(root_path, 'm3u8_download')
        # out_name = args.out_name
        process_num = 8

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        if os.path.isfile(m3u8_url):
            # 连续下载多个路径的视频
            with open(m3u8_url, 'r') as f_url:
                url_list = f_url.readlines()
            for url_idx, url_line in enumerate(url_list):
                save_name = uuid.uuid4().hex + '.mp4'
                downM3u8Video(url_line.strip(), out_dir, save_name, process_num)
        else:
            save_name = uuid.uuid4().hex + '.mp4'
            downM3u8Video(m3u8_url, out_dir, save_name, process_num)
