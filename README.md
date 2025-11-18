# Citation Map - 学术引用地图

一个可视化Google Scholar作者引用网络的Web应用，展示全球学术引用分布。

## 功能特点

- 输入Google Scholar个人主页URL，自动分析作者信息
- 获取作者所有论文的引用数据
- 提取引用作者的姓名和所属机构
- 在世界地图上可视化引用者的地理分布
- 统计引用数据，包括总引用次数、H指数等

## 技术栈

- **后端**: Python Flask
- **数据抓取**: scholarly (Google Scholar API)
- **地理编码**: geopy + OpenStreetMap Nominatim
- **前端**: HTML5, CSS3, JavaScript
- **地图可视化**: Leaflet.js

## 安装

1. 克隆项目：
```bash
git clone <repository-url>
cd citation-map
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 运行

启动应用：
```bash
python app.py
```

然后在浏览器中打开：http://localhost:5000

## 使用方法

1. 打开Google Scholar (https://scholar.google.com)
2. 搜索你想分析的学者
3. 点击学者姓名进入个人主页
4. 复制浏览器地址栏的URL（格式如：`https://scholar.google.com/citations?user=XXXXXX`）
5. 粘贴到应用的输入框中
6. 设置分析参数（论文数量、每篇论文最大引用数）
7. 点击"开始分析"

## 注意事项

- 由于需要抓取Google Scholar数据，分析过程可能需要几分钟
- Google Scholar可能有访问频率限制，请勿过于频繁使用
- 地理编码使用免费的OpenStreetMap服务，有一定的请求限制
- 部分作者可能没有公开的机构信息

## API端点

### POST /api/analyze

分析Google Scholar作者的引用数据。

**请求体**:
```json
{
  "url": "https://scholar.google.com/citations?user=XXXXXX",
  "max_papers": 5,
  "max_citations": 10
}
```

**响应**:
```json
{
  "author": {
    "name": "作者姓名",
    "affiliation": "所属机构",
    "citations": 1000,
    "h_index": 20
  },
  "publications": [...],
  "citing_authors": [...],
  "locations": [
    {
      "institution": "机构名称",
      "lat": 40.7128,
      "lng": -74.0060,
      "count": 5,
      "authors": ["作者1", "作者2"]
    }
  ]
}
```

## 许可证

MIT License
