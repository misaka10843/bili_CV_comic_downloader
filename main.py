import argparse
import asyncio
import json
import os
import random
import re
import shutil
import time
from pathlib import Path

import requests
from bilibili_api import article
from cbz.comic import ComicInfo
from cbz.constants import PageType, YesNo, Manga, AgeRating, Format
from cbz.page import PageInfo

ID = []


def extract_images_from_json(data):
    images = []

    def traverse_children(children):
        for child in children:
            if child["type"] == "ImageNode" and "url" in child:
                if child["url"].startswith("https://i0.hdslb.com"):
                    images.append(child["url"])
            elif child["type"] == "TextNode":
                try:
                    text = child["text"]
                    image_urls = re.findall(r'https://i0.hdslb.com[^\s"]+', text)
                    images.extend(image_urls)
                except KeyError:
                    pass
            elif "children" in child:
                traverse_children(child["children"])

    traverse_children(data.get("children", []))
    return images


def get_downloaded_list(lid):
    global ID
    if not os.path.exists(f"{lid}.json"):
        return
    with open(f"{lid}.json", "r") as f:
        ID = json.load(f)


def save_downloaded_list(lid):
    with open(f"{lid}.json", "w") as f:
        json.dump(ID, f)


async def get_list(lid):
    id = []
    a = article.ArticleList(rlid=lid)
    info = await a.get_content()
    print(info['list']['name'])
    for item in info['articles']:
        id.append(item['id'])
    return id, info['list']['name']


async def get_co(id):
    a = article.Article(cvid=id)
    print(f"专栏cv号：{id}")
    await a.fetch_content()

    a = a.json()
    images = extract_images_from_json(a)
    print("图片列表：")
    print(images)
    cname = a['meta']['title']
    return images, cname


async def download(path, url):
    filename = path
    print(f"正在下载图片：{url}")
    if os.path.exists(filename):
        print(f"检测到已下载{filename}，跳过")
        return
    response = requests.get(url)
    if not response:
        print(f"图片下载失败，URL：{url}")
        print("建议稍后重试，防止因b站ban IP图片下载不完整")
        return
    with open(filename, "wb") as f:
        f.write(response.content)
    # 防止速率过高导致临时403
    sleep_time = random.randint(1, 2)
    time.sleep(sleep_time)


def c_cbz(path, title_name, cname, cbz_path):
    paths = list(Path(path).iterdir())
    pages = [
        PageInfo.load(
            path=path,
            type=PageType.FRONT_COVER if i == 0 else PageType.STORY
        )
        for i, path in enumerate(paths)
    ]

    comic = ComicInfo.from_pages(
        pages=pages,
        title=cname,
        series=title_name,
        language_iso='zh',
        format=Format.WEB_COMIC,
        black_white=YesNo.NO,
        manga=Manga.YES,
        age_rating=AgeRating.PENDING
    )
    try:
        cbz_path.write_bytes(comic.pack())
    except Exception as e:
        print(e)
        exit(1)
    shutil.rmtree(path)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--lid',
        help='专栏合集的id,例如https://www.bilibili.com/read/readlist/rl843588中843588')
    parser.add_argument(
        '--cbz',
        help='cbz文件夹位置')

    lid = parser.parse_args().lid
    cbz_path = parser.parse_args().cbz
    if lid is None:
        print("没有lid，请输入lid再进行下载")
        exit(1)
    get_downloaded_list(lid)
    id, title_name = await get_list(lid)
    title_name = title_name.replace(" ", "_").replace(":", "：").replace("?", "？")
    if ID:
        cindex = len(ID) + 1
    else:
        cindex = 1
    for x in id:
        if x in ID:
            print(f"{x} 已下载，跳过")
            continue
        index = 0
        images, cname = await get_co(x)
        print(f"正在下载：{cname}")
        cname = cname.replace(" ", "_").replace(":", "：").replace("?", "？")
        path = f"{os.path.abspath('.')}/download/{title_name}/{cindex}-{cname}"
        if not os.path.exists(path):
            os.makedirs(path)
        for image in images:
            ipath = f"{path}/{index}.jpg"
            await download(ipath, image)
            index += 1
        if not os.path.exists(f"{cbz_path}/{title_name}/"):
            os.makedirs(f"{cbz_path}/{title_name}/")
        cbz_fpath = Path(f'{cbz_path}/{title_name}/') / f'{cindex}-{cname}.cbz'
        c_cbz(path, title_name, cname, cbz_fpath)
        cindex += 1
        ID.append(x)
        save_downloaded_list(lid)


if __name__ == "__main__":
    asyncio.run(main())
