# 引用替换工具

这个工具用于将BibTeX文件中的引用条目替换为从DBLP获取的正式发表的论文引用。

## 功能特点

- 自动解析BibTeX文件中的所有引用条目
- 根据论文标题和作者在DBLP上搜索对应的正式发表版本
- 保留原始引用标识符(cite_key)，仅替换内容
- 智能请求控制，避免DBLP请求限制
- 对于未找到匹配的条目，添加警告注释并保留原始条目

## 安装依赖

运行以下命令安装所需的Python依赖：

```bash
pip install requests beautifulsoup4
```

## 使用方法

### 基本用法

```bash
python cite_reverse.py
```

默认情况下，程序会读取`cite.bib`文件并生成`cite_new.bib`作为输出。

### 自定义输入输出文件

修改`cite_reverse.py`末尾的`main`函数调用：

```python
if __name__ == "__main__":
    main(input_file="你的输入文件.bib", output_file="你的输出文件.bib")
```

## 工作原理

1. 解析BibTeX文件中的所有条目
2. 对每个条目，提取作者和标题信息
3. 使用这些信息在DBLP上搜索对应的正式发表版本
4. 如果找到匹配，用DBLP条目替换原始条目，但保留原始的cite_key
5. 如果未找到匹配，保留原始条目并添加警告注释

## 高级特性

- **自适应请求间隔**：程序会根据DBLP的响应动态调整请求间隔，以避免被限制访问
- **随机User-Agent**：每次请求使用不同的浏览器标识，减少被识别为爬虫的可能性
- **请求队列控制**：所有请求通过队列控制，确保平滑的请求频率

## 示例

原始条目：
```
@misc{1401.0514,
  author = {Chris J. Maddison and Daniel Tarlow},
  title = {Structured Generative Models of Natural Source Code},
  year = {2014},
  primaryClass = {cs.PL cs.LG stat.ML},
  url = {https://arxiv.org/abs/1401.0514}
}
```

替换后的条目：
```
@inproceedings{1401.0514,
  author       = {Chris J. Maddison and
                  Daniel Tarlow},
  title        = {Structured Generative Models of Natural Source Code},
  booktitle    = {Proceedings of the 31th International Conference on Machine Learning,
                  {ICML} 2014, Beijing, China, 21-26 June 2014},
  series       = {{JMLR} Workshop and Conference Proceedings},
  volume       = {32},
  pages        = {649--657},
  publisher    = {JMLR.org},
  year         = {2014},
  url          = {http://proceedings.mlr.press/v32/maddison14.html},
  timestamp    = {Wed, 29 May 2019 08:41:45 +0200},
  biburl       = {https://dblp.org/rec/conf/icml/MaddisonT14.bib},
  bibsource    = {dblp computer science bibliography, https://dblp.org}
}
```

## 注意事项

- 程序可能不总是找到正确的匹配，建议手动检查替换结果
- 处理大型BibTeX文件时可能需要较长时间，因为需要限制请求频率
- 对于未在DBLP找到匹配的条目，会保留原始条目并添加警告注释
- 如果频繁使用可能会被DBLP暂时封禁IP，此时可以等待一段时间后再尝试 