#!/usr/bin/env python3
"""
App-Company Lookup: 在应用宝(sj.qq.com)搜索App并提取开发商/运营商信息。

用法:
    python3 search_app.py <app_name> [--limit N] [--detail]

示例:
    python3 search_app.py "伊对" --detail
    python3 search_app.py "红娘视频相亲" --detail --limit 5
"""

import sys
import json
import argparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright 未安装，请运行: pip3 install playwright && python3 -m playwright install chromium", file=sys.stderr)
    sys.exit(1)


def create_browser():
    """创建浏览器实例"""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return p, browser, context


def search_and_get_details(keyword: str, limit: int = 5, get_detail: bool = False):
    """
    在应用宝搜索并获取App信息。
    
    实际上应用宝详情页的 __NEXT_DATA__ 中已经包含完整的App信息,
    所以可以从搜索页直接提取, 不需要逐个打开详情页。
    """
    p, browser, context = create_browser()
    results = []

    try:
        page = context.new_page()
        search_url = f"https://sj.qq.com/search?q={keyword}"

        print(f"🔍 在应用宝搜索: {keyword}", file=sys.stderr)
        page.goto(search_url, timeout=10000)
        page.wait_for_timeout(2000)

        # 从搜索页的 __NEXT_DATA__ 直接提取结构化数据
        next_data_el = page.query_selector("script#__NEXT_DATA__")
        if next_data_el:
            data = json.loads(next_data_el.inner_text())
            components = (
                data.get("props", {})
                .get("pageProps", {})
                .get("dynamicCardResponse", {})
                .get("data", {})
                .get("components", [])
            )
            for comp in components:
                items = comp.get("data", {}).get("itemData", [])
                for item in items:
                    pkg = item.get("pkg_name", "")
                    name = item.get("name", "")
                    if not pkg or not name:
                        continue

                    app_info = {
                        "name": name,
                        "package_name": pkg,
                        "detail_url": f"https://sj.qq.com/appdetail/{pkg}",
                    }

                    if get_detail:
                        app_info["developer"] = item.get("developer", "未知")
                        app_info["operator"] = item.get("operator", "未知")
                        app_info["icp_number"] = item.get("icp_number", "未知")
                        app_info["icp_entity"] = item.get("icp_entity", "未知")
                        app_info["version"] = item.get("version_name", "未知")
                        size = item.get("apk_size", 0)
                        app_info["size"] = f"{int(size) / (1024*1024):.1f}MB" if size else "未知"
                        app_info["category"] = item.get("cate_name", item.get("cate_name_new", "未知"))
                        app_info["download_num"] = item.get("download_num", "未知")

                    results.append(app_info)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        # 如果 __NEXT_DATA__ 没数据，fallback到DOM解析
        if not results:
            links = page.query_selector_all("a[href*='/appdetail/']")
            seen = set()
            for link in links:
                href = link.get_attribute("href") or ""
                if "/appdetail/" not in href:
                    continue
                pkg = href.split("/appdetail/")[-1].split("?")[0].split("#")[0]
                if not pkg or pkg in seen:
                    continue
                seen.add(pkg)
                name = link.inner_text().strip().split("\n")[0].strip()
                if not name or len(name) > 50:
                    name = pkg
                results.append({
                    "name": name,
                    "package_name": pkg,
                    "detail_url": f"https://sj.qq.com/appdetail/{pkg}"
                })
                if len(results) >= limit:
                    break

        page.close()

        # 如果需要详情但从搜索页拿不到 developer，逐个打开详情页
        if get_detail:
            for app in results:
                if app.get("developer") in (None, "未知", ""):
                    detail = _get_detail_from_page(context, app["package_name"])
                    app.update(detail)

    except Exception as e:
        print(f"WARNING: 搜索失败: {e}", file=sys.stderr)
    finally:
        browser.close()
        p.stop()

    return results


def _get_detail_from_page(context, package_name: str) -> dict:
    """访问详情页获取App信息"""
    detail = {}
    page = context.new_page()
    url = f"https://sj.qq.com/appdetail/{package_name}"

    try:
        page.goto(url, timeout=10000)
        page.wait_for_timeout(2000)

        next_data_el = page.query_selector("script#__NEXT_DATA__")
        if next_data_el:
            data = json.loads(next_data_el.inner_text())
            components = (
                data.get("props", {})
                .get("pageProps", {})
                .get("dynamicCardResponse", {})
                .get("data", {})
                .get("components", [])
            )
            for comp in components:
                items = comp.get("data", {}).get("itemData", [])
                for item in items:
                    if item.get("pkg_name") == package_name:
                        detail["developer"] = item.get("developer", "未知")
                        detail["operator"] = item.get("operator", "未知")
                        detail["icp_number"] = item.get("icp_number", "未知")
                        detail["icp_entity"] = item.get("icp_entity", "未知")
                        detail["version"] = item.get("version_name", "未知")
                        size = item.get("apk_size", 0)
                        detail["size"] = f"{int(size) / (1024*1024):.1f}MB" if size else "未知"
                        detail["category"] = item.get("cate_name", item.get("cate_name_new", "未知"))
                        detail["download_num"] = item.get("download_num", "未知")
                        break
    except Exception as e:
        print(f"  WARNING: 获取 {package_name} 详情失败: {e}", file=sys.stderr)
    finally:
        page.close()

    return detail


def main():
    parser = argparse.ArgumentParser(description="应用宝App搜索与开发商查询")
    parser.add_argument("keyword", help="搜索关键词（App名称）")
    parser.add_argument("--limit", type=int, default=5, help="最大返回结果数（默认5）")
    parser.add_argument("--detail", action="store_true", help="同时获取每个App的开发商/运营商详情")
    args = parser.parse_args()

    results = search_and_get_details(args.keyword, limit=args.limit, get_detail=args.detail)

    if not results:
        print(json.dumps({"keyword": args.keyword, "count": 0, "results": []}, ensure_ascii=False))
        sys.exit(0)

    output = {
        "keyword": args.keyword,
        "count": len(results),
        "results": results
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
