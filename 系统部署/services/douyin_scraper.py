"""
抖音账号爬虫服务 - 使用 Playwright (需手动验证) 或 Requests 获取账号信息
需要先安装: playwright install (或使用已安装的 Chrome)
"""
import os
import json
import logging
import re
import requests

logger = logging.getLogger(__name__)


def get_douyin_account_info(url, use_browser=False):
    """获取抖音账号信息

    Args:
        url: 抖音账号主页链接
        use_browser: 是否使用浏览器（需要手动验证）

    Returns:
        dict: 账号信息
    """
    # 如果需要浏览器模式
    if use_browser:
        return get_douyin_with_browser(url)

    # 先尝试用 requests（无头模式）
    real_url = resolve_short_url(url)
    logger.info(f"[douyin_scraper] 真实URL: {real_url}")

    sec_uid = extract_sec_uid(real_url)
    if not sec_uid:
        logger.warning(f"[douyin_scraper] 无法从URL提取 sec_uid: {real_url}")
        return get_douyin_with_browser(url)  # 自动切换到浏览器模式

    # 尝试多种 API 获取账号信息
    info = fetch_account_info_by_sec_uid(sec_uid)

    if not info:
        info = fetch_from_web_page(real_url)

    # 如果仍然失败，提示用户使用浏览器模式
    if not info:
        logger.warning("[douyin_scraper] requests 方式失败，请使用浏览器模式手动验证")
        return None

    return info


def get_douyin_with_browser(url):
    """使用浏览器获取抖音账号信息（需要手动验证）

    打开 Chrome 浏览器，让用户手动完成验证后获取账号信息
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("请安装 playwright: pip install playwright")
        return None

    # 先解析短链接
    real_url = resolve_short_url(url)
    logger.info(f"[douyin_scraper] 浏览器模式，解析后URL: {real_url}")

    try:
        with sync_playwright() as p:
            # 使用已安装的 Chrome
            browser = p.chromium.launch(
                headless=False,  # 非无头模式，显示浏览器窗口
                executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                args=['--disable-blink-features=AutomationControlled']
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = context.new_page()

            # 访问抖音账号主页 - 增加超时时间
            logger.info(f"[douyin_scraper] 打开浏览器，访问: {real_url}")
            try:
                page.goto(real_url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                logger.warning(f"[douyin_scraper] 页面加载超时，继续尝试: {e}")
                # 继续尝试获取内容

            # 等待一会儿让页面渲染
            page.wait_for_timeout(3000)

            # 检查是否遇到验证码
            if is_verification_page(page):
                logger.info("[douyin_scraper] 检测到验证码，请手动完成验证...")
                print("\n" + "="*50)
logger.debug("请在浏览器中完成验证后，回到终端按回车继续...")
                print("="*50 + "\n")

                # 等待用户手动验证完成
                input("完成后按回车继续...")

            # 等待页面加载完成
            page.wait_for_timeout(2000)

            # 方法1: 尝试从页面标题获取昵称
            title = page.title()
            logger.info(f"[douyin_scraper] 页面标题: {title}")

            # 尝试从页面 DOM 获取用户信息
            info = None

            # 方法2: 使用 JavaScript 从页面提取数据
            try:
                # 尝试多种方式获取用户信息
                js_result = page.evaluate(r'''
                    () => {
                        const result = {};

                        // 方法1: 从页面标题提取 (格式: "昵称的抖音 - 抖音")
                        const pageTitle = document.title || '';
                        console.log('页面标题:', pageTitle);
                        const titleMatch = pageTitle.match(/^(.+?)的抖音/);
                        if (titleMatch && titleMatch[1]) {
                            result.nickname = titleMatch[1].trim();
                            console.log('从标题提取到昵称:', result.nickname);
                        }

                        // 方法2: 尝试从页面元数据获取
                        if (!result.nickname) {
                            const ogTitle = document.querySelector('meta[property="og:title"]');
                            if (ogTitle && ogTitle.content) {
                                const match = ogTitle.content.match(/^(.+?)的抖音/);
                                if (match) {
                                    result.nickname = match[1].trim();
                                }
                            }
                        }

                        // 方法3: 查找页面中的昵称元素
                        if (!result.nickname) {
                            const selectors = [
                                '[class*="user-name"]', '[class*="nickname"]',
                                '[class*="userName"]', '[class*="Name"]',
                                'h1[class*="name"]', 'span[class*="name"]'
                            ];
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.textContent) {
                                    const text = el.textContent.trim();
                                    if (text && text.length > 0 && text.length < 50) {
                                        result.nickname = text;
                                        console.log('从元素提取到昵称:', result.nickname, '选择器:', sel);
                                        break;
                                    }
                                }
                            }
                        }

                        // 方法4: 从页面 RENDER_DATA 中提取粉丝数和简介
                        try {
                            const renderDataEl = document.getElementById('RENDER_DATA');
                            if (renderDataEl) {
                                const renderData = JSON.parse(decodeURIComponent(renderDataEl.getAttribute('data-dc')));
                                console.log('找到RENDER_DATA');
                                console.log('RENDER_DATA结构:', JSON.stringify(renderData).slice(0, 2000));

                                // 尝试多种数据结构路径
                                let userData = null;
                                if (renderData.user) userData = renderData.user;
                                else if (renderData.userInfo) userData = renderData.userInfo;
                                else if (renderData.anchorInfo) userData = renderData.anchorInfo;

                                if (userData) {
                                    console.log('userData数据:', JSON.stringify(userData).slice(0, 1000));
                                    if (!result.nickname && userData.nickname) {
                                        result.nickname = userData.nickname;
                                        console.log('从RENDER_DATA提取到昵称:', result.nickname);
                                    }
                                    // 尝试多种粉丝数字段名
                                    const followerFields = ['followerCount', 'follower_count', 'fansCount', 'fans_count', 'mplatform_followers_count', 'followersCount'];
                                    for (const field of followerFields) {
                                        if (userData[field] !== undefined && userData[field] > 0) {
                                            result.follower_count = userData[field];
                                            console.log('从RENDER_DATA提取到粉丝数:', result.follower_count, '字段:', field);
                                            break;
                                        }
                                    }
                                    if (userData.signature || userData.desc) {
                                        result.bio = userData.signature || userData.desc;
                                        console.log('从RENDER_DATA提取到简介:', result.bio);
                                    }
                                }
                            }
                        } catch(e) {
                            console.log('RENDER_DATA提取失败:', e);
                        }

                        // 方法5: 从页面 JSON-LD 或其他脚本标签中提取
                        try {
                            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                            for (const script of scripts) {
                                try {
                                    const data = JSON.parse(script.textContent);
                                    if (data.author) {
                                        if (!result.nickname && data.author.name) {
                                            result.nickname = data.author.name;
                                        }
                                    }
                                } catch(e) {}
                            }
                        } catch(e) {}

                        // 方法6: 从页面链接中提取粉丝数（备选）
                        // 优先尝试直接查找粉丝数元素
                        const followerSelectors = [
                            '[class*="follower"] span', '[class*="fans"] span',
                            '[class*="Folower"]', '[class*="Fans"]',
                            '[data-e2e="follow"]', '[data-e2e="fans"]',
                            'span[class*="count"]'
                        ];
                        for (const sel of followerSelectors) {
                            const els = document.querySelectorAll(sel);
                            for (const el of els) {
                                const text = el.textContent.trim();
                                // 匹配数字，可能带万/亿
                                if (text.match(/[\d.]+[万万亿]?/)) {
                                    let count = text.match(/([\d.]+)[万万亿]?/)?.[1] || text;
                                    let num = parseFloat(count);
                                    if (text.includes('万')) num *= 10000;
                                    else if (text.includes('亿')) num *= 100000000;
                                    if (num > 100) {  // 忽略小数字
                                        result.follower_count = Math.round(num);
                                        console.log('从DOM元素提取到粉丝数:', result.follower_count, '文本:', text);
                                        break;
                                    }
                                }
                            }
                            if (result.follower_count > 100) break;
                        }

                        // 如果仍然没有获取到有效粉丝数，尝试从页面文本中提取
                        if (!result.follower_count || result.follower_count < 100) {
                            // 查找包含数字的元素，可能包含粉丝数
                            const allElements = document.querySelectorAll('*');
                            for (const el of allElements) {
                                const text = el.textContent || '';
                                // 匹配 "XX万粉丝" 或 "XX粉丝" 格式
                                const match = text.match(/([\d.]+[万万亿]?)\s*粉丝/);
                                if (match && text.length < 30) {
                                    let count = match[1];
                                    // 转换万为单位
                                    if (count.includes('万')) {
                                        count = parseFloat(count) * 10000;
                                    } else if (count.includes('亿')) {
                                        count = parseFloat(count) * 100000000;
                                    }
                                    result.follower_count = Math.round(parseFloat(count));
                                    console.log('从元素文本提取到粉丝数:', result.follower_count);
                                    break;
                                }
                            }
                        }

                        // 方法7: 查找简介元素
                        if (!result.bio) {
                            const bioSelectors = [
                                '[class*="signature"]', '[class*="bio"]',
                                '[class*="desc"]', '[class*="description"]',
                                '[class*="Signature"]', '[class*="Bio"]',
                                '[itemprop="description"]', 'meta[name="description"]'
                            ];
                            for (const sel of bioSelectors) {
                                const el = document.querySelector(sel);
                                if (el) {
                                    const text = (el.textContent || el.getAttribute('content') || '').trim();
                                    if (text && text.length > 0 && text.length < 500) {
                                        result.bio = text;
                                        console.log('从元素提取到简介:', result.bio, '选择器:', sel);
                                        break;
                                    }
                                }
                            }
                        }

                        console.log('最终提取结果:', JSON.stringify(result));
                        return result;
                    }
                ''')

                logger.info(f"[douyin_scraper] JS返回结果: {js_result}")

                if js_result and js_result.get('nickname'):
                    info = {
                        'nickname': js_result.get('nickname', ''),
                        'bio': js_result.get('bio', ''),
                        'avatar_url': js_result.get('avatar_url', ''),
                        'fans_count': format_count(js_result.get('follower_count', 0)),
                        'following_count': format_count(js_result.get('following_count', 0)),
                    }
                    logger.info(f"[douyin_scraper] JS提取成功: {info.get('nickname')}")
            except Exception as e:
                logger.warning(f"[douyin_scraper] JS提取失败: {e}")

            # 如果 JS 提取失败，尝试从 HTML 提取
            if not info or not info.get('nickname'):
                html = page.content()
                logger.info(f"[douyin_scraper] 页面长度: {len(html)}")
                info = extract_user_from_html(html)

            browser.close()

            if info and info.get('nickname'):
                logger.info(f"[douyin_scraper] 浏览器模式获取成功: {info.get('nickname', 'unknown')}")
                return info
            else:
                logger.error("[douyin_scraper] 从页面提取用户信息失败")
                return None

    except Exception as e:
        logger.error(f"[get_douyin_with_browser] 浏览器模式失败: {e}")
        return None


def is_verification_page(page):
    """检查是否需要验证码"""
    try:
        # 检查页面是否有验证码相关元素
        selectors = [
            '.verify', '#verify', '.captcha',
            '[class*="verify"]', '[class*="captcha"]',
            'text=验证', 'text=请点击', 'text=滑动验证'
        ]

        for selector in selectors[:4]:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except:
                continue

        # 检查页面标题或 URL
        title = page.title().lower()
        url = page.url.lower()

        if '验证' in title or 'verify' in url:
            return True

        return False
    except:
        return False


def resolve_short_url(url):
    """解析抖音短链接或分享链接，返回真实的主页链接"""
    # 从文本中提取抖音链接
    url_match = re.search(r'https?://v\.douyin\.com/[a-zA-Z0-9]+', url)
    if url_match:
        url = url_match.group(0)

    # 处理 iesdouyin.com 分享链接
    if 'iesdouyin.com' in url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.douyin.com/'
            }
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            resolved = response.url
            logger.info(f"[resolve_short_url] iesdouyin.com 解析: {url} -> {resolved}")
            # 转换为 douyin.com 格式，并确保是 /user/ 格式而不是 /share/user/
            if 'iesdouyin.com' in resolved:
                resolved = resolved.replace('iesdouyin.com', 'douyin.com')
            # 转换 /share/user/ 为 /user/
            if '/share/user/' in resolved:
                resolved = resolved.replace('/share/user/', '/user/')
            return resolved
        except Exception as e:
            logger.warning(f"[resolve_short_url] 解析 iesdouyin.com 失败: {e}")
            # 尝试直接转换
            result = url.replace('iesdouyin.com', 'douyin.com')
            if '/share/user/' in result:
                result = result.replace('/share/user/', '/user/')
            return result

    # 检查是否是短链接
    if 'v.douyin.com' not in url:
        # 也处理 /share/user/ 格式
        if '/share/user/' in url:
            return url.replace('/share/user/', '/user/')
        return url

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/'
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        resolved = response.url
        # 转换 /share/user/ 为 /user/
        if '/share/user/' in resolved:
            resolved = resolved.replace('/share/user/', '/user/')
        return resolved
    except Exception as e:
        logger.warning(f"[resolve_short_url] 解析短链接失败: {e}")
        return url


def extract_sec_uid(url):
    """从抖音主页链接中提取 sec_uid"""
    # 尝试从 URL 中匹配 sec_uid=xxx 或 /user/ 后面跟的数字/字母
    patterns = [
        r'sec_uid=([^&]+)',
        r'/user/([^/?]+)',
        r'short\.html\?[\w-]+=([^&]+)',  # 短链接格式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            sec_uid = match.group(1)
            # 验证是否为有效的 sec_uid（以 IW 开头或类似格式）
            if sec_uid and len(sec_uid) > 10:
                return sec_uid
    
    return None


def fetch_account_info_by_sec_uid(sec_uid):
    """通过 sec_uid 获取账号信息 - 尝试多种 API"""
    
    # 方法1: 使用抖音网页版用户信息接口
    apis = [
        {
            'url': 'https://www.douyin.com/aweme/v1/web/anchor/user/',
            'params': {'sec_uid': sec_uid}
        },
        {
            'url': 'https://www.douyin.com/aweme/v1/web/user/profile/other/',
            'params': {'sec_user_id': sec_uid}
        },
        {
            'url': 'https://www.douyin.com/aweme/v2/web/user/info/',
            'params': {'sec_uid': sec_uid}
        }
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.douyin.com/',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    
    for api in apis:
        try:
            logger.info(f"[douyin_scraper] 尝试 API: {api['url']}")
            response = requests.get(api['url'], headers=headers, params=api['params'], timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[douyin_scraper] API响应: {json.dumps(data)[:500]}")
                
                # 检查是否有有效数据
                if data.get('status_code', 1) == 0:
                    info = parse_user_data(data)
                    if info:
                        return info
                        
        except Exception as e:
            logger.warning(f"[douyin_scraper] API {api['url']} 失败: {e}")
            continue
    
    return None


def fetch_from_web_page(url):
    """从抖音网页直接抓取用户信息"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.warning(f"[fetch_from_web_page] 请求失败: {response.status_code}")
            return None
        
        html = response.text
        
        # 尝试从页面提取用户信息 JSON
        info = extract_user_from_html(html)
        
        if info:
            logger.info(f"[douyin_scraper] 从网页提取成功: {info.get('nickname', 'unknown')}")
            return info
            
    except Exception as e:
        logger.error(f"[fetch_from_web_page] 失败: {e}")
    
    return None


def extract_user_from_html(html):
    """从页面 HTML 中提取用户信息"""
    info = {}

    try:
        # 尝试匹配 JSON 格式的用户数据
        # 抖音页面通常在 <script id="RENDER_DATA"> 或类似位置包含初始数据

        # 方法1: 查找 JSON 数据 - 更宽松的模式
        json_patterns = [
            r'\{[^{}]*"userInfo"[^{}]*\{[^{}]*"info"[^{}]*\{[^}]+\}[^}]*\}[^}]*\}',
            r'"userInfo"\s*:\s*\{[^}]*\}',
            r'\{[^{}]*"user_status"[^{}]*"user_info"[^{}]*\{[^}]+\}[^}]*\}',
            r'\{[^{}]*"user"[^{}]*\{[^}]*"nickname"[^}]+\}[^}]*\}',
        ]

        for json_pattern in json_patterns:
            match = re.search(json_pattern, html, re.DOTALL)
            if match:
                try:
                    import json as json_module
                    json_str = match.group(0)
                    json_str = json_str.replace('\\/', '/')

                    # 尝试解析
                    data = json_module.loads(json_str)

                    # 多种数据结构尝试
                    user = None
                    if 'userInfo' in data and 'info' in data['userInfo']:
                        user = data['userInfo']['info']
                    elif 'userInfo' in data:
                        user = data['userInfo']
                    elif 'user_info' in data:
                        user = data['user_info']
                    elif 'user' in data:
                        user = data['user']

                    if user:
                        info = {
                            'nickname': user.get('nickname', ''),
                            'bio': user.get('signature', ''),
                            'avatar_url': '',
                            'fans_count': format_count(user.get('follower_count', 0)),
                            'following_count': format_count(user.get('following_count', 0)),
                            'likes_count': format_count(user.get('total_favorited_count', 0)),
                        }

                        # 处理头像
                        avatar = user.get('avatar_url')
                        if avatar:
                            if isinstance(avatar, str):
                                info['avatar_url'] = avatar
                            elif isinstance(avatar, dict):
                                info['avatar_url'] = avatar.get('url_list', [''])[0] if avatar.get('url_list') else ''
                            elif isinstance(avatar, list) and avatar:
                                info['avatar_url'] = avatar[0]

                        if info.get('nickname'):
                            logger.info(f"[extract_user_from_html] 从JSON提取成功: {info['nickname']}")
                            return info
                except Exception as e:
                    logger.warning(f"[extract_user_from_html] JSON解析失败: {e}")
                    continue

        # 方法2: 提取用户信息区域，然后在该区域内提取字段
        # 尝试找到用户信息区域的边界
        user_info_region = None

        # 尝试找到 userInfo 或 user 对象的区域
        user_obj_match = re.search(r'("userInfo"\s*:\s*\{[^}]+\})|"user"\s*:\s*\{[^}]+\}', html, re.DOTALL)
        if user_obj_match:
            # 扩展搜索范围，获取更多上下文
            start_pos = max(0, user_obj_match.start() - 50)
            end_pos = min(len(html), user_obj_match.end() + 2000)
            user_info_region = html[start_pos:end_pos]
            logger.info(f"[extract_user_from_html] 找到用户信息区域，长度: {len(user_info_region)}")

        if not user_info_region:
            # 如果没找到用户信息区域，使用整个HTML但限制长度
            user_info_region = html[:50000]  # 只使用前50000个字符

        # 在用户信息区域内提取昵称
        for pattern in [r'"nickname"\s*:\s*"([^"]+)"', r'"nick"\s*:\s*"([^"]+)"']:
            nick_match = re.search(pattern, user_info_region)
            if nick_match:
                info['nickname'] = nick_match.group(1)
                logger.info(f"[extract_user_from_html] 找到昵称: {info['nickname']}")
                break

        # 在用户信息区域内提取简介
        for pattern in [r'"signature"\s*:\s*"([^"]+)"', r'"bio"\s*:\s*"([^"]+)"', r'"desc"\s*:\s*"([^"]+)"']:
            sig_match = re.search(pattern, user_info_region)
            if sig_match:
                info['bio'] = sig_match.group(1)
                logger.info(f"[extract_user_from_html] 找到简介: {info['bio'][:50]}...")
                break

        # 在用户信息区域内提取粉丝数 - 优先匹配较大的数字
        follower_numbers = []
        for pattern in [r'"followerCount"\s*:\s*(\d+)', r'"follower_count"\s*:\s*(\d+)']:
            follower_match = re.search(pattern, user_info_region)
            if follower_match:
                num = int(follower_match.group(1))
                follower_numbers.append(num)
                logger.info(f"[extract_user_from_html] 找到粉丝数字段: {num}")

        # 取最大的数字（通常是最准确的粉丝数）
        if follower_numbers:
            info['fans_count'] = format_count(max(follower_numbers))
            logger.info(f"[extract_user_from_html] 最终粉丝数: {info['fans_count']}")

        # 在用户信息区域内提取关注数
        for pattern in [r'"followingCount"\s*:\s*(\d+)', r'"following_count"\s*:\s*(\d+)']:
            following_match = re.search(pattern, user_info_region)
            if following_match:
                info['following_count'] = format_count(following_match.group(1))
                break

        # 在用户信息区域内提取头像
        for pattern in [r'"avatarUrl"\s*:\s*"([^"]+)"', r'"avatar_url"\s*:\s*"([^"]+)"']:
            avatar_match = re.search(pattern, user_info_region)
            if avatar_match:
                info['avatar_url'] = avatar_match.group(1)
                break

        # 在用户信息区域内提取获赞数
        for pattern in [r'"totalFavoritedCount"\s*:\s*(\d+)', r'"total_favorited_count"\s*:\s*(\d+)']:
            likes_match = re.search(pattern, user_info_region)
            if likes_match:
                info['likes_count'] = format_count(likes_match.group(1))
                break

        if info.get('nickname'):
            logger.info(f"[extract_user_from_html] 从区域提取成功: {info['nickname']}")
            return info

        # 方法3: 尝试查找页面标题中的昵称（通常是最后手段）
        title_match = re.search(r'<title>([^<]+?)的抖音主页</title>', html)
        if title_match:
            info['nickname'] = title_match.group(1)
            logger.info(f"[extract_user_from_html] 从标题提取成功: {info['nickname']}")
            return info

        logger.warning(f"[extract_user_from_html] 无法从页面提取用户信息")
        return None

    except Exception as e:
        logger.error(f"[extract_user_from_html] 提取失败: {e}")
        return None


def parse_user_data(data):
    """解析抖音返回的用户数据"""
    try:
        # 尝试多种数据结构
        user = None
        
        if 'user_info' in data:
            user = data['user_info']
        elif 'userInfo' in data:
            if 'info' in data['userInfo']:
                user = data['userInfo']['info']
            else:
                user = data['userInfo']
        elif 'data' in data and 'user' in data['data']:
            user = data['data']['user']
        elif 'data' in data and 'user_info' in data['data']:
            user = data['data']['user_info']
        
        if not user:
            return None
        
        info = {
            'nickname': user.get('nickname', ''),
            'bio': user.get('signature', ''),  # 简介
            'avatar_url': '',
            'fans_count': format_count(user.get('follower_count', 0)),
            'following_count': format_count(user.get('following_count', 0)),
            'likes_count': format_count(user.get('total_favorited_count', 0)),
            'ip_location': user.get('ip_location', ''),
            'gender': '男' if user.get('gender') == 1 else ('女' if user.get('gender') == 2 else ''),
            'constellation': user.get('constellation', ''),
            'personality_tags': user.get('custom_verify', ''),
        }
        
        # 处理头像
        avatar = user.get('avatar_url')
        if avatar:
            if isinstance(avatar, str):
                info['avatar_url'] = avatar
            elif isinstance(avatar, dict):
                info['avatar_url'] = avatar.get('url_list', [''])[0] if avatar.get('url_list') else ''
            elif isinstance(avatar, list) and avatar:
                info['avatar_url'] = avatar[0]
        
        return info if info['nickname'] else None
        
    except Exception as e:
        logger.error(f"[parse_user_data] 解析失败: {e}")
        return None


def format_count(count):
    """格式化数字（如 10000 -> 1万）"""
    if not count:
        return '0'

    try:
        count = int(count)
    except (ValueError, TypeError):
        return '0'

    if count >= 100000000:
        return f"{count / 100000000:.1f}亿"
    elif count >= 10000:
        return f"{count / 10000:.1f}万"
    else:
        return str(count)


def get_douyin_video_info(url, use_browser=False):
    """获取抖音视频/图文内容信息

    Args:
        url: 抖音视频/图文链接
        use_browser: 是否使用浏览器（需要手动验证）

    Returns:
        dict: 视频/图文信息
    """
    # 如果需要浏览器模式
    if use_browser:
        return get_douyin_video_with_browser(url)

    # 先尝试用 requests（无头模式）
    real_url = resolve_short_url(url)
    logger.info(f"[douyin_scraper] 视频真实URL: {real_url}")

    # 尝试从网页提取视频信息
    info = fetch_video_from_web_page(real_url)

    if not info:
        logger.warning("[douyin_scraper] requests 方式获取视频信息失败，尝试浏览器模式")
        return get_douyin_video_with_browser(url)

    return info


def get_douyin_video_with_browser(url):
    """使用浏览器获取抖音视频/图文信息（需要手动验证）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("请安装 playwright: pip install playwright")
        return None

    # 先解析短链接
    real_url = resolve_short_url(url)
    logger.info(f"[douyin_scraper] 浏览器模式获取视频，URL: {real_url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                args=['--disable-blink-features=AutomationControlled']
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = context.new_page()

            logger.info(f"[douyin_scraper] 打开浏览器，访问视频: {real_url}")
            try:
                page.goto(real_url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                logger.warning(f"[douyin_scraper] 页面加载超时: {e}")

            page.wait_for_timeout(3000)

            # 检查是否遇到验证码
            if is_verification_page(page):
                logger.info("[douyin_scraper] 检测到验证码，请手动完成验证...")
                print("\n" + "="*50)
logger.debug("请在浏览器中完成验证后，回到终端按回车继续...")
                print("="*50 + "\n")
                input("完成后按回车继续...")
                page.wait_for_timeout(2000)

            # 使用 JavaScript 从页面提取视频信息
            try:
                js_result = page.evaluate(r'''
                    () => {
                        const result = {};

                        // 从页面标题获取标题
                        const pageTitle = document.title || '';
                        console.log('页面标题:', pageTitle);
                        // 抖音视频标题格式: "视频标题 - 作者昵称 - 抖音"
                        const titleMatch = pageTitle.match(/^(.+?)(?:\s*-\s*.+?)?\s*-\s*抖音/);
                        if (titleMatch && titleMatch[1]) {
                            result.title = titleMatch[1].trim();
                        }

                        // 从页面元数据获取
                        const ogTitle = document.querySelector('meta[property="og:title"]');
                        if (ogTitle && ogTitle.content) {
                            result.ogTitle = ogTitle.content;
                        }

                        const ogDesc = document.querySelector('meta[property="og:description"]');
                        if (ogDesc && ogDesc.content) {
                            result.description = ogDesc.content;
                        }

                        // 尝试获取作者信息
                        const authorMatch = pageTitle.match(/-\s*(.+?)(?:\s*-\s*抖音|$)/);
                        if (authorMatch && authorMatch[1]) {
                            result.author = authorMatch[1].trim();
                        }

                        // 尝试获取视频描述/文案
                        const descSelectors = [
                            '[class*="video-info-detail"]',
                            '[class*="video-desc"]',
                            '[class*="desc"]',
                            '[class*="video-info"]',
                            'span[class*="content"]'
                        ];
                        for (const sel of descSelectors) {
                            const el = document.querySelector(sel);
                            if (el && el.textContent) {
                                const text = el.textContent.trim();
                                if (text && text.length > 0 && text.length < 1000) {
                                    result.video_desc = text;
                                    break;
                                }
                            }
                        }

                        // 尝试获取话题标签
                        const hashtags = [];
                        const hashElements = document.querySelectorAll('a[href*="/topic/"], span[class*="tag"]');
                        hashElements.forEach(el => {
                            const text = el.textContent?.trim();
                            if (text && text.startsWith('#')) {
                                hashtags.push(text);
                            }
                        });
                        if (hashtags.length > 0) {
                            result.hashtags = hashtags;
                        }

                        console.log('最终提取结果:', JSON.stringify(result));
                        return result;
                    }
                ''')

                logger.info(f"[douyin_scraper] JS返回视频结果: {js_result}")

                if js_result:
                    info = {
                        'title': js_result.get('title', ''),
                        'description': js_result.get('video_desc', '') or js_result.get('description', ''),
                        'author': js_result.get('author', ''),
                        'hashtags': js_result.get('hashtags', []),
                        'url': real_url
                    }
                    logger.info(f"[douyin_scraper] 浏览器提取视频成功: {info.get('title', 'unknown')}")
                    browser.close()
                    return info

            except Exception as e:
                logger.warning(f"[douyin_scraper] JS提取视频失败: {e}")

            browser.close()
            return None

    except Exception as e:
        logger.error(f"[get_douyin_video_with_browser] 浏览器模式失败: {e}")
        return None


def fetch_video_from_web_page(url):
    """从网页获取视频信息（无头模式）"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=10)
        html = response.text

        # 从 HTML 中提取信息
        info = extract_video_from_html(html)
        if info:
            info['url'] = url
            return info

        return None

    except Exception as e:
        logger.warning(f"[douyin_scraper] fetch_video_from_web_page 失败: {e}")
        return None


def extract_video_from_html(html):
    """从 HTML 中提取视频信息"""
    try:
        result = {}

        # 提取标题
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # 清理标题
            title = re.sub(r'\s*-\s*抖音\s*$', '', title)
            title = re.sub(r'\s*-\s*[^-]+$', '', title)
            result['title'] = title.strip()

        # 提取 og:title
        og_title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_title_match and not result.get('title'):
            result['title'] = og_title_match.group(1).strip()

        # 提取 og:description
        og_desc_match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_desc_match:
            result['description'] = og_desc_match.group(1).strip()

        # 提取话题标签
        hashtags = re.findall(r'#[\w\u4e00-\u9fa5]+', html)
        if hashtags:
            result['hashtags'] = list(set(hashtags))[:10]  # 最多10个

        logger.info(f"[extract_video_from_html] 提取结果: {result}")
        return result if result else None

    except Exception as e:
        logger.warning(f"[extract_video_from_html] 解析失败: {e}")
        return None


# 测试函数
if __name__ == '__main__':
    test_url = input("请输入抖音账号链接: ").strip()
    if test_url:
        info = get_douyin_account_info(test_url)
        if info:
logger.debug("\n=== 账号信息 ===")
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
logger.debug("获取账号信息失败")
    else:
logger.debug("未输入链接")
