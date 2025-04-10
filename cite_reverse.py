#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
import random
import threading
from queue import Queue

# 添加线程锁，确保输出不会混乱
print_lock = threading.Lock()
write_lock = threading.Lock()
request_lock = threading.Lock()

# 队列用于限制请求频率
request_queue = Queue()

# 不同的User-Agent列表，模拟不同的浏览器
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36 Edg/96.0.1054.29",
]

# 自适应请求间隔（秒）
MIN_REQUEST_INTERVAL = 3  # 最小间隔时间
MAX_REQUEST_INTERVAL = 15  # 最大间隔时间
CURRENT_INTERVAL = MIN_REQUEST_INTERVAL  # 当前间隔时间


# 创建请求控制线程
def request_controller():
    """控制请求频率的线程函数"""
    global CURRENT_INTERVAL
    last_request_time = 0

    while True:
        # 从队列中获取请求
        req_func, args, kwargs, result_queue = request_queue.get()

        # 计算需要等待的时间
        now = time.time()
        # 随机化等待时间，避免固定模式
        wait_time = max(
            0, last_request_time + CURRENT_INTERVAL + random.uniform(-1, 1) - now
        )

        if wait_time > 0:
            time.sleep(wait_time)

        # 执行请求
        try:
            result = req_func(*args, **kwargs)
            result_queue.put((True, result))
            # 请求成功，可以适当减少间隔时间
            CURRENT_INTERVAL = max(MIN_REQUEST_INTERVAL, CURRENT_INTERVAL * 0.95)
        except Exception as e:
            result_queue.put((False, e))
            # 请求失败，增加间隔时间
            if "429" in str(e) or "Too Many Requests" in str(e):
                CURRENT_INTERVAL = min(MAX_REQUEST_INTERVAL, CURRENT_INTERVAL * 1.5)
                with print_lock:
                    print(f"遇到限流，增加请求间隔至 {CURRENT_INTERVAL:.2f} 秒")

        last_request_time = time.time()
        request_queue.task_done()


# 启动请求控制线程
controller_thread = threading.Thread(target=request_controller, daemon=True)
controller_thread.start()


def controlled_request(req_func, *args, **kwargs):
    """将请求放入队列，由控制线程执行"""
    result_queue = Queue()
    request_queue.put((req_func, args, kwargs, result_queue))
    success, result = result_queue.get()
    if success:
        return result
    else:
        raise result  # 重新抛出异常


def parse_bib_file(file_path):
    """解析BibTeX文件，返回一个条目列表"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 正则表达式匹配BibTeX条目
    pattern = r"(@\w+\{[^@]+\})"
    entries = re.findall(pattern, content, re.DOTALL)
    return entries


def extract_entry_info(entry):
    """从BibTeX条目中提取关键信息"""
    # 提取条目类型和引用标识符
    type_key_match = re.match(r"@(\w+)\{([^,]+),", entry)
    if not type_key_match:
        return None

    entry_type, cite_key = type_key_match.groups()

    # 提取作者
    author_match = re.search(r"author\s*=\s*\{([^}]+)\}", entry)
    author = author_match.group(1) if author_match else ""

    # 提取标题
    title_match = re.search(r"title\s*=\s*\{([^}]+)\}", entry)
    title = title_match.group(1) if title_match else ""
    # 清理多行标题
    title = re.sub(r"\s+", " ", title)

    # 提取URL
    url_match = re.search(r"url\s*=\s*\{([^}]+)\}", entry)
    url = url_match.group(1) if url_match else ""

    return {
        "entry_type": entry_type,
        "cite_key": cite_key,
        "author": author,
        "title": title,
        "url": url,
        "full_entry": entry,
    }


def make_request(url, headers=None, timeout=30):
    """执行HTTP请求的实际函数"""
    if headers is None:
        # 随机选择一个User-Agent
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def search_dblp(author, title):
    """在DBLP上搜索论文，返回BibTeX条目"""
    # 构建搜索查询
    query = f"{title} {author.split(' and ')[0]}"  # 使用标题和第一作者
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://dblp.org/search?q={encoded_query}"

    try:
        # 发送请求
        with print_lock:
            print(f"  正在排队搜索DBLP: {search_url}")
            print(f"  当前请求间隔: {CURRENT_INTERVAL:.2f} 秒")

        response = controlled_request(make_request, search_url)

        # 解析HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # 查找搜索结果
        result_items = soup.select(".publ-list .entry")
        if not result_items:
            with print_lock:
                print("  未找到搜索结果")
            return None

        with print_lock:
            print(f"  找到 {len(result_items)} 个搜索结果")

        # 获取第一个结果的BibTeX链接
        for item in result_items:
            # 检查是否存在BibTeX链接
            bibtex_link = item.select_one('nav.publ a[href*="bibtex"]')
            if bibtex_link:
                bibtex_url = bibtex_link["href"]
                # 确保URL是完整的
                if not bibtex_url.startswith("http"):
                    if bibtex_url.startswith("/"):
                        bibtex_url = f"https://dblp.org{bibtex_url}"
                    else:
                        bibtex_url = f"https://dblp.org/{bibtex_url}"

                with print_lock:
                    print(f"  获取BibTeX: {bibtex_url}")

                # 在访问BibTeX链接前再等待一下
                time.sleep(random.uniform(1, 3))

                # 获取BibTeX内容
                bibtex_response = controlled_request(make_request, bibtex_url)
                bibtex_soup = BeautifulSoup(bibtex_response.text, "html.parser")
                bibtex_content = bibtex_soup.select_one("#bibtex-section pre")

                if bibtex_content:
                    return bibtex_content.text

        with print_lock:
            print("  未找到BibTeX内容")
        return None

    except Exception as e:
        with print_lock:
            print(f"  搜索DBLP时出错: {e}")
        return None


def replace_entry_with_dblp(arxiv_entry, dblp_entry):
    """
    用DBLP条目替换arXiv条目，但保留原始的cite_key
    """
    if not dblp_entry:
        return arxiv_entry

    # 提取arXiv条目的cite_key
    arxiv_info = extract_entry_info(arxiv_entry)
    if not arxiv_info:
        return arxiv_entry

    cite_key = arxiv_info["cite_key"]

    # 替换DBLP条目中的cite_key
    dblp_entry_new = re.sub(r"@(\w+)\{([^,]+),", f"@\\1{{{cite_key},", dblp_entry)

    return dblp_entry_new


def process_entry(entry, output_file):
    """处理单个引用条目的函数"""
    info = extract_entry_info(entry)

    if not info:
        with write_lock:
            with open(output_file, "a", encoding="utf-8") as f_out:
                f_out.write(entry + "\n\n")
        return

    # 处理所有条目，无论是否为arXiv
    with print_lock:
        print(f"处理条目: {info['cite_key']}")

    # 搜索DBLP
    dblp_entry = search_dblp(info["author"], info["title"])

    with write_lock:
        with open(output_file, "a", encoding="utf-8") as f_out:
            if dblp_entry:
                with print_lock:
                    print(f"  找到DBLP匹配: 替换条目")
                new_entry = replace_entry_with_dblp(entry, dblp_entry)
                f_out.write(new_entry + "\n\n")
            else:
                with print_lock:
                    print(f"  未找到DBLP匹配: 保留原条目并添加注释")
                # 添加注释说明未找到匹配
                comment = f"% WARNING: 未在DBLP中找到匹配的条目: {info['cite_key']}。建议人工重新检查。\n"
                f_out.write(comment + entry + "\n\n")


def main(input_file="test.bib", output_file="test_new.bib"):
    print(f"开始处理文件 {input_file}...")

    # 解析BibTeX文件
    entries = parse_bib_file(input_file)
    print(f"找到 {len(entries)} 条引用条目")

    # 创建新文件（清空原有内容）
    with open(output_file, "w", encoding="utf-8"):
        pass

    # 顺序处理条目，不使用多线程
    for i, entry in enumerate(entries):
        print(f"处理条目 {i+1}/{len(entries)}")
        try:
            process_entry(entry, output_file)
        except Exception as e:
            print(f"处理条目时出错: {e}")
            # 出错时增加延迟
            time.sleep(random.uniform(10, 20))

    print(f"处理完成。新文件已保存为 {output_file}")


if __name__ == "__main__":
    main(input_file="cite.bib", output_file="cite_new.bib")
