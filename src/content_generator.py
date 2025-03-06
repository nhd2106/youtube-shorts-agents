from typing import TypedDict, List, Dict, Any, Optional
from openai import AsyncOpenAI
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import io
from PIL import Image
import uuid
import os
import json
import urllib.parse

class VideoFormat(TypedDict):
    type: str  # 'shorts' or 'normal'
    duration: str  # '60s' for shorts, 'flexible' for normal

class Content(TypedDict):
    script: str
    title: str
    hashtags: list[str]
    format: VideoFormat
    image_urls: list[str]  # Add this field for storing extracted image URLs

class ContentGenerator:
    def __init__(self):
        self.client = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        }

    def _init_client(self, api_keys: dict):
        """Initialize OpenAI client with API key"""
        if not api_keys.get('openai'):
            raise ValueError("OpenAI API key is required")
        self.client = AsyncOpenAI(api_key=api_keys['openai'])
        # Initialize Together AI
        if not api_keys.get('together'):
            raise ValueError("Together AI API key is required for image generation")
        import together
        together.api_key = api_keys['together']
        self.together_client = together

    async def _extract_images_from_url(self, url: str) -> List[str]:
        """Extract image URLs from webpage, focusing on main article content first"""
        try:
            # Disable SSL verification warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Create a session with custom headers and longer timeouts
            session = requests.Session()
            session.verify = False
            
            # Set longer timeouts (connect_timeout, read_timeout)
            adapter = requests.adapters.HTTPAdapter(
                max_retries=3,  # Retry 3 times
                pool_connections=10,
                pool_maxsize=10
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            # Update headers based on the site
            headers = self.headers.copy()
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc
            
            headers.update({
                'Host': domain,
                'Referer': f"{parsed_url.scheme}://{domain}/",
                'Origin': f"{parsed_url.scheme}://{domain}"
            })
            
            session.headers.update(headers)
            
            # Make the request with multiple encoding attempts and longer timeout
            try:
                response = session.get(url, timeout=(15, 30))  # (connect timeout, read timeout)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                print(f"Request timed out for {url}. Retrying with longer timeout...")
                # Retry once with even longer timeout
                response = session.get(url, timeout=(30, 60))
                response.raise_for_status()
            except requests.exceptions.SSLError:
                print(f"SSL Error for {url}. Retrying without verification...")
                response = session.get(url, verify=False, timeout=(15, 30))
                response.raise_for_status()
            
            # Try different encodings if content seems garbled
            content = None
            encodings = ['utf-8', 'utf-16', 'windows-1252', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    response.encoding = encoding
                    content = response.text
                    # Check if content seems valid (contains some common HTML tags)
                    if re.search(r'<html|<body|<div|<img', content, re.IGNORECASE):
                        break
                except UnicodeDecodeError:
                    continue
            
            if not content:
                print(f"Failed to decode content from {url} with any known encoding")
                return []
            
            # Parse with BeautifulSoup using different parsers
            soup = None
            parsers = ['html.parser', 'lxml', 'html5lib']
            
            for parser in parsers:
                try:
                    soup = BeautifulSoup(content, parser)
                    # Verify we got valid HTML
                    if soup.find(['body', 'div', 'img']):
                        break
                except Exception as e:
                    print(f"Parser {parser} failed: {str(e)}")
                    continue
            
            if not soup:
                print(f"Failed to parse HTML content from {url} with any available parser")
                return []
            
            # Remove unwanted elements that might interfere
            for element in soup.find_all(['script', 'style', 'noscript', 'iframe']):
                element.decompose()
            
            print(f"\nStarting image extraction for URL: {url}")
            image_urls = []  # Changed to list to maintain order
            
            # Try site-specific extraction first
            site_type = self._detect_site_type(url)
            print(f"Detected site type: {site_type}")
            
            if site_type != 'generic':
                try:
                    extractor_method = getattr(self, f'_extract_{site_type}_images')
                    site_images = extractor_method(soup, url)
                    image_urls.extend(reversed(site_images))  # Reverse site-specific images
                    print(f"Found {len(site_images)} images using {site_type} specific extractor")
                except Exception as e:
                    print(f"Error in site-specific extraction: {str(e)}")
            
            # If no images found or site is generic, try generic extraction
            if not image_urls:
                print("Trying generic extraction method")
                
                # Priority 1: Find the main article content container
                main_content_selectors = [
                    'article.content-detail',
                    'article.fck_detail',
                    'div.fck_detail',
                    'article.article-detail',
                    'div.article-body',
                    'div.article-content',
                    'div[itemprop="articleBody"]',
                    'div.detail-content',
                    '.article__body',
                    '.article__content',
                    '.post-content',
                    '.entry-content',
                    'article.post',
                    'main article',
                    '[role="main"] article',
                    '.main-content article',
                    '.content article',
                    '.articleDetail',
                    '.content-detail',
                    '.box-news'
                ]
                
                main_content = None
                for selector in main_content_selectors:
                    try:
                        main_content = soup.select_one(selector)
                        if main_content:
                            print(f"Found main content with selector: {selector}")
                            break
                    except Exception as e:
                        print(f"Error with selector {selector}: {str(e)}")
                
                if main_content:
                    # Extract images from main content in reverse order
                    temp_images = []
                    for img in main_content.find_all('img'):
                        for attr in ['data-src', 'src', 'data-original', 'data-lazy-src', 'data-lazy']:
                            try:
                                src = img.get(attr)
                                if src:
                                    src = self._clean_url(src, url)
                                    if self._is_valid_image_url(src) and src not in temp_images:
                                        temp_images.append(src)
                                        break
                            except Exception as e:
                                print(f"Error processing image attribute {attr}: {str(e)}")
                    
                    # Add images in reverse order
                    image_urls.extend(reversed(temp_images))
                
                # Try meta tags if still no images
                if not image_urls:
                    meta_selectors = {
                        'property': ['og:image', 'twitter:image', 'og:image:secure_url'],
                        'name': ['thumbnail', 'twitter:image:src', 'twitter:image'],
                        'itemprop': ['image']
                    }
                    
                    meta_images = []
                    for attr, values in meta_selectors.items():
                        for value in values:
                            try:
                                for meta in soup.find_all('meta', {attr: value}):
                                    content = meta.get('content')
                                    if content:
                                        src = self._clean_url(content, url)
                                        if self._is_valid_image_url(src) and src not in meta_images:
                                            meta_images.append(src)
                            except Exception as e:
                                print(f"Error processing meta tag {attr}={value}: {str(e)}")
                    
                    # Add meta images in reverse order
                    image_urls.extend(reversed(meta_images))
            
            print(f"Found {len(image_urls)} unique images from {url}")
            return image_urls
            
        except Exception as e:
            print(f"Error extracting images from URL: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []

    def _detect_site_type(self, url: str) -> str:
        """Detect the type of news site from URL"""
        if 'vnexpress.net' in url:
            return 'vnexpress'
        elif 'dantri.com.vn' in url:
            return 'dantri'
        elif 'nhandan.vn' in url:
            return 'nhandan'
        return 'generic'

    def _extract_vnexpress_images(self, soup: BeautifulSoup, base_url: str) -> list:
        """Extract images specifically from VnExpress"""
        image_urls = []
        try:
            # Find all figure elements with specific VnExpress classes in reverse order
            figures = list(reversed(soup.find_all(['figure', 'div'], class_=['fig-picture', 'item-news-common', 'image', 'pic'])))
            
            for fig in figures:
                # Try to find picture element first
                picture = fig.find('picture')
                if picture:
                    # Get source elements for highest quality image
                    sources = picture.find_all('source')
                    for source in sources:
                        srcset = source.get('srcset')
                        if srcset:
                            urls = [s.strip().split(' ')[0] for s in srcset.split(',')]
                            if urls:
                                src = self._clean_url(urls[-1], base_url)
                                if self._is_valid_image_url(src) and src not in image_urls:
                                    image_urls.append(src)
                
                # Try to find img element
                img = fig.find('img')
                if img:
                    for attr in ['data-src', 'src', 'data-original']:
                        src = img.get(attr)
                        if src:
                            src = self._clean_url(src, base_url)
                            if self._is_valid_image_url(src) and src not in image_urls:
                                image_urls.append(src)
                                break
            
            # Try to find images in specific VnExpress containers in reverse order
            containers = list(reversed(soup.find_all(['div', 'article'], class_=['fig-picture', 'fck_detail', 'content-detail'])))
            for container in containers:
                for img in reversed(container.find_all('img')):
                    for attr in ['data-src', 'src', 'data-original']:
                        src = img.get(attr)
                        if src:
                            src = self._clean_url(src, base_url)
                            if self._is_valid_image_url(src) and src not in image_urls:
                                image_urls.append(src)
                                break
        
        except Exception as e:
            print(f"Error extracting VnExpress images: {str(e)}")
        
        return image_urls

    def _extract_dantri_images(self, soup: BeautifulSoup, base_url: str) -> list:
        """Extract images specifically from Dan Tri"""
        image_urls = []
        try:
            # Find all figure elements with Dan Tri specific classes in reverse order
            figures = list(reversed(soup.find_all(['figure', 'div'], class_=['image', 'article-thumb', 'dt-image'])))
            for fig in figures:
                img = fig.find('img')
                if img:
                    for attr in ['data-src', 'src', 'data-original']:
                        src = img.get(attr)
                        if src:
                            src = self._clean_url(src, base_url)
                            if self._is_valid_image_url(src) and src not in image_urls:
                                image_urls.append(src)
                                break
        except Exception as e:
            print(f"Error extracting Dan Tri images: {str(e)}")
        return image_urls

    def _extract_nhandan_images(self, soup: BeautifulSoup, base_url: str) -> list:
        """Extract images specifically from Nhan Dan"""
        image_urls = []
        try:
            # Find all figure elements with Nhan Dan specific classes in reverse order
            figures = list(reversed(soup.find_all(['figure', 'div'], class_=['article-image', 'image', 'detail-image'])))
            for fig in figures:
                img = fig.find('img')
                if img:
                    for attr in ['data-src', 'src', 'data-original']:
                        src = img.get(attr)
                        if src:
                            src = self._clean_url(src, base_url)
                            if self._is_valid_image_url(src) and src not in image_urls:
                                image_urls.append(src)
                                break
        except Exception as e:
            print(f"Error extracting Nhan Dan images: {str(e)}")
        return image_urls

    def _clean_url(self, url: str, base_url: str) -> str:
        """Clean and normalize image URL"""
        if not url:
            return ""
            
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url
            
        # Handle relative URLs
        if not url.startswith(('http://', 'https://')):
            return urljoin(base_url, url)
            
        return url

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL points to a valid image"""
        try:
            # List of common image extensions
            image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
            
            # Exclude patterns for small or irrelevant images
            excluded_patterns = (
                'emoji',
                'button',
                'loading',
                'spinner',
                'pixel',
                'tracking'
            )
            
            url_lower = url.lower()
            
            # Basic checks
            if not url_lower or 'data:image' in url_lower:
                print(f"Invalid URL (empty or data URL): {url}")
                return False
            
            # Check file extension
            has_valid_extension = any(url_lower.endswith(ext) for ext in image_extensions)
            has_extension_in_path = any(ext in part for part in url_lower.split('/') for ext in image_extensions)
            
            if not (has_valid_extension or has_extension_in_path):
                print(f"Invalid URL (no valid image extension): {url}")
                return False
            
            # Check for excluded patterns
            if any(pattern in url_lower for pattern in excluded_patterns):
                print(f"Invalid URL (contains excluded pattern): {url}")
                return False
            
            # Check for dimensions in URL (if present)
            dimensions = re.findall(r'(\d+)x(\d+)', url_lower)
            if dimensions:
                width, height = map(int, dimensions[0])
                # Only reject very small images
                if width < 200 or height < 200:
                    print(f"Invalid URL (dimensions too small: {width}x{height}): {url}")
                    return False
            
            # Check for small image indicators in URL
            small_indicators = ['thumb', 'tiny', '50x', '100x']
            if any(indicator in url_lower for indicator in small_indicators):
                print(f"Invalid URL (contains small image indicator): {url}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating image URL {url}: {str(e)}")
            return False

    def _extract_images_from_json(self, data: Any, image_urls: set, base_url: str):
        """Recursively extract image URLs from JSON-LD data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['image', 'thumbnail', 'contentUrl'] and isinstance(value, str):
                    absolute_url = urljoin(base_url, value)
                    if self._is_valid_image_url(absolute_url):
                        image_urls.add(absolute_url)
                else:
                    self._extract_images_from_json(value, image_urls, base_url)
        elif isinstance(data, list):
            for item in data:
                self._extract_images_from_json(item, image_urls, base_url)

    async def _extract_content_from_url(self, url: str) -> Dict[str, Any]:
        print(url)
        print('-------------------------------- url ' )
        """Extract content and images from a URL"""
        try:
            # Create session with custom headers and longer timeouts
            session = requests.Session()
            session.verify = False
            
            # Set longer timeouts and retries
            adapter = requests.adapters.HTTPAdapter(
                max_retries=3,
                pool_connections=10,
                pool_maxsize=10
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            session.headers.update(self.headers)
            
            # Try to get content with multiple timeout settings
            try:
                response = session.get(url, timeout=(15, 30))  # (connect timeout, read timeout)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                print(f"Request timed out for {url}. Retrying with longer timeout...")
                response = session.get(url, timeout=(30, 60))
                response.raise_for_status()
            except requests.exceptions.SSLError:
                print(f"SSL Error for {url}. Retrying without verification...")
                response = session.get(url, verify=False, timeout=(15, 30))
                response.raise_for_status()
            
            # Try different encodings if content seems garbled
            content = None
            encodings = ['utf-8', 'utf-16', 'windows-1252', 'latin1', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    response.encoding = encoding
                    content = response.text
                    if re.search(r'<html|<body|<div', content, re.IGNORECASE):
                        break
                except UnicodeDecodeError:
                    continue
            
            if not content:
                raise ValueError("Could not decode content with any known encoding")
            
            # Parse with BeautifulSoup using different parsers
            soup = None
            parsers = ['html.parser', 'lxml', 'html5lib']
            
            for parser in parsers:
                try:
                    soup = BeautifulSoup(content, parser)
                    if soup.find(['body', 'div']):
                        break
                except Exception as e:
                    print(f"Parser {parser} failed: {str(e)}")
                    continue
            
            if not soup:
                raise ValueError("Could not parse HTML content")
            
            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string
            else:
                # Try common title selectors if <title> tag is missing
                title_selectors = [
                    'h1.title',
                    'h1.article-title',
                    'h1.entry-title',
                    '.article-header h1',
                    '.post-title',
                    'article h1'
                ]
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        break
            
            # Extract main content
            content = ""
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'noscript', 'iframe', 'header', 'footer', 'nav']):
                element.decompose()
            
            # Try to find main content using common selectors
            content_selectors = [
                 'article.content-detail',
                    'article.fck_detail',
                    'div.fck_detail',
                    'article.article-detail',
                    'div.article-body',
                    'div.article-content',
                    'div[itemprop="articleBody"]',
                    'div.detail-content',
                    '.article__body',
                    '.article__content',
                    '.post-content',
                    '.entry-content',
                    'article.post',
                    'main article',
                    '[role="main"] article',
                    '.main-content article',
                    '.content article',
                    '.articleDetail',
                    '.content-detail',
                    '.box-news'
            ]
            
            main_content = None
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    # Clean up the content
                    for tag in main_content.find_all(['script', 'style', 'iframe']):
                        tag.decompose()
                    content = main_content.get_text(separator='\n').strip()
                    break
            
            # If no content found with selectors, try to get content from article or main tags
            if not content:
                main_content = soup.find('article') or soup.find('main')
                if main_content:
                    content = main_content.get_text(separator='\n').strip()
            
            # Extract images
            image_urls = await self._extract_images_from_url(url)
            
            return {
                'title': title.strip() if title else '',
                'content': content.strip() if content else '',
                'image_urls': image_urls
            }
            
        except Exception as e:
            print(f"Error extracting content from URL: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {'title': '', 'content': '', 'image_urls': []}

    async def generate_content(self, idea: str, video_format: str = "shorts", api_keys: dict = None) -> Content:
        try:
            if not api_keys:
                raise ValueError("API keys are required")
            
            # Check if idea contains a URL
            url_pattern = re.compile(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            )
            urls = url_pattern.findall(idea)
            print(urls)
            
            extracted_content = None
            image_urls = []
            
            if urls:
                print(f"Found URL in idea: {urls[0]}")
                # Extract content and images from the first URL
                extracted_content = await self._extract_content_from_url(urls[0])
                image_urls = extracted_content['image_urls']
                print(f"Extracted {len(image_urls)} images from URL")
                
                # Update idea with extracted content
                if extracted_content['content']:
                    idea = f"{idea}\n\nExtracted content:\n{extracted_content['content']}"
            
            # Initialize OpenAI client with API key
            self._init_client(api_keys)

            # Define format specifications
            format_specs = {
                "shorts": {
                    "type": "shorts",
                    "duration": "70s",
                    "script_length": "70 - 85 seconds",
                    "style": "energetic and engaging",
                    "word_count": "250-300 words"
                },
                "normal": {
                    "type": "normal",
                    "duration": "flexible",
                    "script_length": "8-10 minutes",
                    "style": "detailed and comprehensive",
                    "word_count": "5000 - 6000 words"
                }
            }

            if video_format not in format_specs:
                raise ValueError(f"Invalid video format. Choose from: {list(format_specs.keys())}")

            format_spec = format_specs[video_format]

            # Update system prompt based on video format
            system_prompt = f'''You are a creative content specialist focused on creating engaging {video_format} videos.
You must respond in this exact format:
TITLE: [attention-grabbing title]
SCRIPT: [engaging script]
HASHTAGS: [relevant hashtags]

Guidelines for content creation:
1. Title Creation:
    - Ensure the title language matches the user input
    - Craft an attention-grabbing, unique title that sparks curiosity
    - Use relevant keywords for better discoverability
    - Keep it clear, concise, and compelling
    - Avoid clickbait - ensure the title accurately reflects content

2. Script rules:
    - Content Type Guidelines:
        • Historical: Include vivid storytelling elements to make dates and locations more engaging
        • Narrative: Focus on building relatable characters and a compelling plot
        • Factual: Use intriguing hooks to capture attention early on
        • Tutorial: Include interactive elements or visuals to aid understanding
        • Opinion: Balance opinions with compelling arguments and counterpoints to stimulate thought
    - Reference Guidelines:
        • when user paste url, you need Extract detailed information from the following article, including specific numbers, times, and key events:
            1. The main topic or purpose of the content.
            2. Key details, including dates, numbers, or statistics mentioned.
            3. Specific events, incidents, or actions described, if applicable.
            4. Any insights, arguments, or conclusions presented by the author.
            5. Notable quotes or statements from the text.
            6. Other relevant details that contribute to understanding the content.
            7. In case of user input has url, you need to extract detailed information from the url do not fabricate stories
            Provide a clear and concise summary of the extracted information, structured for readability.
        • Encourage the use of visuals or infographics when extracting detailed information
        • Summarize key points in bullet form for easier readability and retention
    - Content Requirements:
        • Consistently match the input language
        • don't seperate numbers by comma or dot, keep them together
        • Focus solely on the requested topic
        • Target length: {format_spec["word_count"]} for a {format_spec["script_length"]} video
        • Keep the tone {format_spec["style"]}
        • Maintain a consistent tone that aligns with the intended audience
        • Use storytelling techniques such as anecdotes or metaphors
        • For normal format: Include detailed examples, case studies, or real-world applications
        • For shorts: Keep it concise and immediately engaging, use punchy language and dynamic visuals
        • Conclude with: in English "If you found this helpful, like and subscribe for more!"  or in Vietnamese "Nếu bạn thấy hay, đừng quên bấm like và đăng ký để ủng hộ kênh" (Choose one based on the user input language)
    - Storytelling Framework - Select ONE:
        • Hero's Journey: Challenge → Struggle → Triumph
        • 7-Second Hook: Grab attention in the first 7 seconds
        • Problem-Solution-Benefit Structure
        • 5-Why Analysis: Deep dive into root causes
        • Dual-Perspective Story: Before/After format
        • 10-Second Engagement Rule
        • Rhythmic/Rhyming Pattern for memorability
        • Experiment with different frameworks to see which resonates best
        • Use the 7-Second Hook to grab attention immediately
    * Remember: Language must match with the user input language

3. Hashtag Strategy:
    - Blend English and topic-specific hashtags
    - Include trending, relevant tags
    - Ensure hashtag relevance to content
    - Optimal mix: 60% topic-specific, 40% general engagement
    - Regularly update hashtags to include trending topics
    - Analyze engagement metrics to refine hashtag usage

4. Quality Standards:
    - Prioritize accuracy and current information
    - Maintain educational or entertainment value
    - Focus on audience engagement and value delivery
    - Keep content concise and impactful
    - Avoid filler content or unnecessary details
    - For normal format: Include supporting details, examples, and deeper analysis
    - For shorts: Focus on key points and immediate value
    - Incorporate user feedback to improve content quality
    - Use analytics to identify best-performing content formats and topics

Note: Exclude emojis, icons, or special characters from the script content.'''
            
            # Make the API call
            print(f"Making API call with system prompt: {idea}")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-3.5-turbo" for lower cost
                messages=[
                    {"role": "assistant", "content": system_prompt},
                    {"role": "user", "content": f"Create a {video_format} video script about: {idea}"}
                ],
                temperature=0.7,
                max_tokens=10000
            )
            
            # Get the content
            content = response.choices[0].message.content
            print("\nDebug - Raw API Response:")
            
            # Parse the content
            parsed_content = self._parse_content(content, format_spec)
            
            # Add extracted image URLs to the content
            if image_urls:
                parsed_content["image_urls"] = image_urls
            
            return parsed_content
            
        except Exception as e:
            print(f"\nDebug - Error details: {str(e)}")
            raise

    def _parse_content(self, content: str, format_spec: dict) -> Content:
        """Helper method to parse the assistant's response"""
        title = ""
        script = ""
        hashtags = []
        current_section = None
        
        # Parse response line by line
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('TITLE:'):
                current_section = 'title'
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('SCRIPT:'):
                current_section = 'script'
                script = line.replace('SCRIPT:', '').strip()
            elif line.startswith('HASHTAGS:'):
                current_section = 'hashtags'
                hashtags_str = line.replace('HASHTAGS:', '').strip()
                hashtags = [tag.strip() for tag in hashtags_str.split(',')]
            elif current_section == 'script':
                # Append to script if we're in script section
                script += '\n' + line
        
        # Validate content
        if not title or not script or not hashtags:
            raise ValueError("Some content sections are missing")
        
        return {
            "title": title,
            "script": script,
            "hashtags": hashtags,
            "format": {
                "type": format_spec["type"],
                "duration": format_spec["duration"]
            },
            "image_urls": []
        }

    async def download_and_process_image(self, url: str, output_dir: str) -> Optional[str]:
        """Download and process an image from a URL"""
        try:
            import httpx
            
            # Create httpx client with SSL verification disabled
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                if response.status_code != 200:
                    print(f"Failed to download image: HTTP {response.status_code}")
                    return None
                
                image_data = response.content
                print(f"Successfully downloaded image: {url}")

            # Process image with PIL
            try:
                image = Image.open(io.BytesIO(image_data))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Get original dimensions for logging
                original_size = image.size
                
                # Check if image is too small
                if original_size[0] < 300 or original_size[1] < 300:
                    print(f"Image too small: {original_size}")
                    return None
                
                # Resize and crop to match video dimensions
                resized_image = self._resize_and_crop(image)
                
                # Generate unique filename
                filename = f"{uuid.uuid4()}.jpg"
                output_path = os.path.join(output_dir, filename)
                
                # Save processed image
                resized_image.save(output_path, 'JPEG', quality=95)
                
                print(f"Successfully processed image: {url}")
                print(f"Original size: {original_size}, Resized to: {resized_image.size}")
                return output_path
                
            except Exception as e:
                print(f"Error processing image data: {str(e)}")
                return None
                
        except Exception as e:
            print(f"Error downloading image from {url}: {str(e)}")
            return None

    def _resize_and_crop(self, image: Image.Image) -> Image.Image:
        """Resize image to match video dimensions while preserving content using letterboxing/pillarboxing"""
        if not hasattr(self, 'WIDTH') or not hasattr(self, 'HEIGHT'):
            raise ValueError("Video dimensions not set. Call set_format() first.")
            
        # Calculate target aspect ratio
        target_ratio = self.WIDTH / self.HEIGHT
        
        # Get current image dimensions
        width, height = image.size
        current_ratio = width / height
        
        # Calculate dimensions to fit image entirely within video frame
        if current_ratio > target_ratio:
            # Image is wider - fit to width
            new_width = self.WIDTH
            new_height = int(new_width / current_ratio)
        else:
            # Image is taller - fit to height
            new_height = self.HEIGHT
            new_width = int(new_height * current_ratio)
        
        # Resize using high-quality Lanczos resampling
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create new image with video dimensions and black background
        final_image = Image.new('RGB', (self.WIDTH, self.HEIGHT), (0, 0, 0))
        
        # Calculate position to center the resized image
        paste_x = (self.WIDTH - new_width) // 2
        paste_y = (self.HEIGHT - new_height) // 2
        
        # Paste resized image onto black background
        final_image.paste(resized_image, (paste_x, paste_y))
        
        return final_image